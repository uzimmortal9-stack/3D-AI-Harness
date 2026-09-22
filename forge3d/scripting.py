"""Forge3D scripting & logic environment.

Game scripts are plain Python files exposing optional hooks:

    def on_start(api):  ...      # called once before the loop
    def on_update(api, dt): ...  # called every fixed tick
    def on_end(api): ...         # called after the loop

`api` gives scripts controlled access to the scene:

    api.scene            # the Scene
    api.time             # simulation clock (s)
    api.input            # InputManager
    api.get("Name")      # node by name
    api.move(node, dx,dy,dz)
    api.set_pos(node, x,y,z)
    api.impulse(node, vx,vy,vz)     # nudges physics velocity if body exists
    api.play(sound_name)            # plays a declared sound
    api.log(msg)
    api.bodies           # name -> Body (live physics state)
"""
import os
import sys
import types


class ScriptAPI:
    def __init__(self, scene, world=None, sounds=None, quiet=False):
        self.scene = scene
        self.world = world
        self.sounds = sounds or {}
        self.time = 0.0
        self.input = None
        self.bodies = {}
        self.quiet = quiet
        self._played = []
        if world is not None:
            self.bodies = {b.node_name: b for b in world.bodies if not b.static}

    def get(self, name):
        return self.scene.get(name)

    def move(self, node, dx=0, dy=0, dz=0):
        node.position = node.position + _v3(dx, dy, dz)

    def set_pos(self, node, x, y, z):
        node.position = _v3(x, y, z)

    def rotate(self, node, dx=0, dy=0, dz=0):
        node.rotation = node.rotation + _v3(dx, dy, dz)

    def impulse(self, node, vx, vy, vz):
        b = self.bodies.get(node.name)
        if b is not None:
            b.velocity = b.velocity + _v3(vx, vy, vz)
        return b is not None

    def play(self, sound_name):
        cfg = self.sounds.get(sound_name)
        if cfg is None:
            return False
        self._played.append((sound_name, self.time))
        path = cfg.get("wav_path")
        if path and os.path.exists(path):
            from . import audio
            audio.play(path)
        return True

    def log(self, *msg):
        if not self.quiet:
            print("[script]", *msg)


def _v3(x, y, z):
    import numpy as np
    return np.array([x, y, z], float)


def load_script(path):
    """Loads a .py game script, returns dict of hook functions."""
    path = os.path.abspath(path)
    mod = types.ModuleType(os.path.splitext(os.path.basename(path))[0])
    mod.__dict__["__file__"] = path
    code = open(path, "r", encoding="utf-8").read()
    exec(compile(code, path, "exec"), mod.__dict__)
    hooks = {}
    for h in ("on_start", "on_update", "on_end"):
        fn = mod.__dict__.get(h)
        if callable(fn):
            hooks[h] = fn
    return hooks
