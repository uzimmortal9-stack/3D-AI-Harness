"""Forge3D rigging & animation — keyframe tracks, skeletons, rigid skinning."""
import numpy as np


class Track:
    """Keyframe track for one node channel ('position'|'rotation'|'scale')."""

    def __init__(self, node_name, channel="position", times=(), values=(),
                 ease="linear"):
        self.node_name = node_name
        self.channel = channel
        self.times = np.asarray(times, float)
        self.values = np.asarray(values, float)
        self.ease = ease  # linear | smooth

    def add(self, t, value):
        self.times = np.append(self.times, t)
        self.values = np.vstack([self.values, np.asarray(value, float)]) \
            if len(self.values) else np.asarray([value], float)
        order = np.argsort(self.times)
        self.times = self.times[order]
        self.values = self.values[order]

    def sample(self, t):
        if len(self.times) == 0:
            return None
        if t <= self.times[0]:
            return self.values[0].copy()
        if t >= self.times[-1]:
            return self.values[-1].copy()
        i = int(np.searchsorted(self.times, t)) - 1
        t0, t1 = self.times[i], self.times[i + 1]
        f = (t - t0) / max(t1 - t0, 1e-9)
        if self.ease == "smooth":
            f = f * f * (3 - 2 * f)
        return self.values[i] * (1 - f) + self.values[i + 1] * f

    @property
    def duration(self):
        return float(self.times[-1]) if len(self.times) else 0.0


class Bone:
    def __init__(self, name, parent=None, offset=(0, 0, 0)):
        self.name = name
        self.parent = parent
        self.offset = np.asarray(offset, float)


class Skeleton:
    def __init__(self, name="rig"):
        self.name = name
        self.bones = []

    def add_bone(self, name, parent=None, offset=(0, 0, 0)):
        b = Bone(name, parent, offset)
        self.bones.append(b)
        return b

    def bone_matrices(self, local_rot=None):
        """Returns list of 4x4 world matrices; local_rot: name -> euler degrees."""
        from .math3d import mat4_compose
        mats, by_name = {}, {}
        local_rot = local_rot or {}
        for b in self.bones:
            rot = np.asarray(local_rot.get(b.name, [0, 0, 0]), float)
            local = mat4_compose(b.offset, rot)
            if b.parent and b.parent in by_name:
                mats[b.name] = mats[b.parent] @ local
            else:
                mats[b.name] = local
            by_name[b.name] = b
        return [mats[b.name] for b in self.bones]


def rigid_bind(mesh, skeleton):
    """Assigns each vertex to its nearest bone (base-version skinning).

    Returns weights: int array (N,) of bone indices.
    """
    from .math3d import transform_points
    mats = skeleton.bone_matrices()
    centers = np.array([m[:3, 3] for m in mats])
    d = np.linalg.norm(mesh.vertices[:, None, :] - centers[None, :, :], axis=2)
    return np.argmin(d, axis=1)


def skin_pose(mesh, skeleton, weights, local_rot=None):
    """Returns a NEW mesh posed with per-bone rotations."""
    from .math3d import transform_points
    mats = skeleton.bone_matrices(local_rot)
    out = mesh.copy()
    new_v = np.zeros_like(mesh.vertices)
    for bi, m in enumerate(mats):
        sel = weights == bi
        if sel.any():
            new_v[sel] = transform_points(m, mesh.vertices[sel])
    out.vertices = new_v
    out.update_normals()
    return out


class Animator:
    def __init__(self):
        self.tracks = []
        self.loop = True

    def add_track(self, track):
        self.tracks.append(track)
        return track

    @property
    def duration(self):
        return max([t.duration for t in self.tracks], default=0.0)

    def apply(self, scene, t):
        if self.duration > 0 and self.loop:
            t = t % self.duration
        for tr in self.tracks:
            node = scene.get(tr.node_name)
            if node is None:
                continue
            v = tr.sample(t)
            if v is None:
                continue
            if tr.channel == "position":
                node.position = v
            elif tr.channel == "rotation":
                node.rotation = v
            elif tr.channel == "scale":
                node.scale = v
