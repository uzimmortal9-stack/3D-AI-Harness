"""Forge3D real-time framework — the fixed-tick game loop.

Runs logic (scripts), physics, and rendering either headless (deterministic,
for agents/tests) or interactive (GLFW window, human play).
"""
import sys
import time as _time

from .physics import PhysicsWorld
from .scripting import ScriptAPI


def run_headless(scene, script_paths=(), seconds=3.0, fps=60, sounds=None,
                 quiet=False):
    world = PhysicsWorld.from_scene(scene) if any(
        n.extra.get("body") for n in scene.mesh_nodes()) else None
    api = ScriptAPI(scene, world, sounds, quiet=quiet)
    hooks = []
    from .scripting import load_script
    for p in script_paths:
        hooks.append(load_script(p))
    for h in hooks:
        if "on_start" in h:
            h["on_start"](api)
    steps = max(1, int(seconds * fps))
    dt = 1.0 / fps
    log = []
    for s in range(steps):
        api.time = s * dt
        for h in hooks:
            if "on_update" in h:
                h["on_update"](api, dt)
        if world is not None:
            world.step(dt)
            for name, b in api.bodies.items():
                node = scene.get(name)
                if node is not None:
                    node.position = b.position.copy()
        if s % fps == 0:
            log.append(f"t={api.time:.2f}")
    for h in hooks:
        if "on_end" in h:
            h["on_end"](api)
    return api, log


def run_interactive(scene, script_paths=(), sounds=None):
    """GLFW + OpenGL windowed play. Raises if dependencies missing."""
    from .glview import GLViewer
    viewer = GLViewer(scene)
    world = PhysicsWorld.from_scene(scene) if any(
        n.extra.get("body") for n in scene.mesh_nodes()) else None
    api = ScriptAPI(scene, world, sounds, quiet=False)
    from .inputmgr import InputManager
    api.input = InputManager()
    viewer.input = api.input
    hooks = [__import__("forge3d.scripting", fromlist=["load_script"])
             .load_script(p) for p in script_paths]
    for h in hooks:
        if "on_start" in h:
            h["on_start"](api)
    last = _time.perf_counter()
    while viewer.alive:
        now = _time.perf_counter()
        dt = min(0.05, now - last)
        last = now
        api.time += dt
        viewer.poll_events()
        for h in hooks:
            if "on_update" in h:
                h["on_update"](api, dt)
        if world is not None:
            world.step(dt)
            for name, b in api.bodies.items():
                node = scene.get(name)
                if node is not None:
                    node.position = b.position.copy()
        viewer.draw(dt)
        api.input.end_frame()
    for h in hooks:
        if "on_end" in h:
            h["on_end"](api)
    viewer.close()
    return api
