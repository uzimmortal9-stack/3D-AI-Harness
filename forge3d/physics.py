"""Forge3D physics engine — rigid body lite (spheres, AABB boxes, ground plane).

Semi-implicit Euler integration with impulse-based collision response.
Bodies attach to scene nodes by name; `simulate()` can bake the result into
animation tracks so renders can show motion.
"""
import numpy as np

from .anim import Animator, Track


class Body:
    def __init__(self, node_name, shape="sphere", mass=1.0, radius=0.5,
                 half_extents=(0.5, 0.5, 0.5), restitution=0.4, friction=0.5,
                 static=False):
        self.node_name = node_name
        self.shape = shape            # sphere | box | plane
        self.mass = 0.0 if static else float(mass)
        self.radius = float(radius)
        self.half_extents = np.asarray(half_extents, float)
        self.restitution = float(restitution)
        self.friction = float(friction)
        self.static = static or self.mass == 0
        self._position = np.zeros(3)
        self._velocity = np.zeros(3)

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, v):
        self._position = np.asarray(v, float)

    @property
    def velocity(self):
        return self._velocity

    @velocity.setter
    def velocity(self, v):
        self._velocity = np.asarray(v, float)


class PhysicsWorld:
    def __init__(self, gravity=-9.81):
        self.gravity = float(gravity)
        self.bodies = []

    def add(self, body):
        self.bodies.append(body)
        return body

    @staticmethod
    def from_scene(scene):
        w = PhysicsWorld(scene.gravity)
        ground = Body("__ground", "plane", static=True, restitution=0.4)
        ground.position = np.array([0.0, 0.0, 0.0])
        w.add(ground)
        for n in scene.mesh_nodes():
            b = n.extra.get("body")
            if not b:
                continue
            shape = b.get("shape", "box")
            if shape == "auto":
                lo, hi = n.mesh.bounds()
                ext = (hi - lo) / 2.0
                shape = "sphere" if np.allclose(ext, ext[0], rtol=0.15) else "box"
                radius = float(ext.max())
                he = ext
            else:
                lo, hi = n.mesh.bounds()
                full = hi - lo
                radius = b.get("radius", float(full.min() / 2.0))
                he = full / 2.0
            body = Body(n.name, shape, mass=b.get("mass", 1.0), radius=radius,
                        half_extents=he, restitution=b.get("restitution", 0.4),
                        static=b.get("static", False))
            body.position = np.asarray(n.position, float).copy()
            body.velocity = np.asarray(b.get("velocity", [0, 0, 0]), float).copy()
            w.add(body)
        return w

    def step(self, dt):
        g = np.array([0, self.gravity, 0])
        for b in self.bodies:
            if b.static:
                continue
            b.velocity += g * dt
            b.position += b.velocity * dt
        # ground collisions
        ground_y = None
        for b in self.bodies:
            if b.shape == "plane":
                ground_y = b.position[1]
        if ground_y is not None:
            for b in self.bodies:
                if b.static:
                    continue
                if b.shape == "sphere":
                    pen = ground_y - (b.position[1] - b.radius)
                else:
                    pen = ground_y - (b.position[1] - b.half_extents[1])
                if pen > 0:
                    b.position[1] += pen
                    if b.velocity[1] < 0:
                        b.velocity[1] = -b.velocity[1] * b.restitution
                        if abs(b.velocity[1]) < 0.08:
                            b.velocity[1] = 0.0
                    b.velocity[0] *= (1.0 - min(1.0, b.friction * dt * 4))
                    b.velocity[2] *= (1.0 - min(1.0, b.friction * dt * 4))
        # pairwise collisions
        dyn = [b for b in self.bodies if not b.static]
        for i in range(len(dyn)):
            for j in range(i + 1, len(dyn)):
                self._collide(dyn[i], dyn[j])

    def _collide(self, a, b):
        if a.shape == "sphere" and b.shape == "sphere":
            n = b.position - a.position
            d = np.linalg.norm(n)
            r = a.radius + b.radius
            if d < r and d > 1e-9:
                n = n / d
                pen = r - d
                a.position -= n * pen / 2
                b.position += n * pen / 2
                rel = np.dot(b.velocity - a.velocity, n)
                if rel < 0:
                    e = min(a.restitution, b.restitution)
                    jimp = -(1 + e) * rel / (1 / a.mass + 1 / b.mass)
                    a.velocity -= n * (jimp / a.mass)
                    b.velocity += n * (jimp / b.mass)
        else:
            # AABB overlap positional correction (boxes & mixed)
            ea = np.full(3, a.radius) if a.shape == "sphere" else a.half_extents
            eb = np.full(3, b.radius) if b.shape == "sphere" else b.half_extents
            delta = b.position - a.position
            overlap = (ea + eb) - np.abs(delta)
            if (overlap > 0).all():
                axis = int(np.argmin(overlap))
                sign = np.sign(delta[axis]) or 1.0
                push = np.zeros(3)
                push[axis] = sign * overlap[axis] / 2
                if not a.static and not b.static:
                    a.position -= push
                    b.position += push
                    rel = b.velocity[axis] - a.velocity[axis]
                    if rel * sign < 0:
                        # symmetric elastic-ish bounce
                        va, vb = a.velocity[axis], b.velocity[axis]
                        a.velocity[axis] = (va * (a.mass - b.mass) + 2 * b.mass * vb) \
                            / (a.mass + b.mass)
                        b.velocity[axis] = (vb * (b.mass - a.mass) + 2 * a.mass * va) \
                            / (a.mass + b.mass)
                elif a.static:
                    b.position += push * 2
                    if b.velocity[axis] * sign < 0:
                        b.velocity[axis] *= -b.restitution
                elif b.static:
                    a.position -= push * 2
                    if a.velocity[axis] * -sign < 0:
                        a.velocity[axis] *= -a.restitution


def simulate(scene, seconds=3.0, fps=30, apply=True):
    """Runs physics; returns {node_name: [(t, position), ...]}. Optionally
    writes final positions back into the scene and bakes animation tracks."""
    world = PhysicsWorld.from_scene(scene)
    frames = {b.node_name: [] for b in world.bodies if not b.static}
    steps = max(1, int(seconds * fps))
    dt = 1.0 / fps
    anim = Animator()
    for name in frames:
        anim.add_track(Track(name, "position"))
    for s in range(steps + 1):
        t = s * dt
        for b in world.bodies:
            if not b.static:
                frames[b.node_name].append((t, b.position.copy()))
        if s < steps:
            world.step(dt)
    if apply:
        for b in world.bodies:
            node = scene.get(b.node_name)
            if node is not None and not b.static:
                node.position = b.position.copy()
        # attach tracks properly
        for tr in anim.tracks:
            for (tt, pp) in frames.get(tr.node_name, []):
                tr.add(tt, pp)
    return frames, anim
