"""ForgeScript interpreter — compiles .forge files into a live Scene.

Design goal: a tiny, stable, deterministic API surface so AI agents never
hallucinate a wrong call (the #1 failure mode measured in 3DCodeBench).
"""
import os

import numpy as np

from .lexer import ForgeSyntaxError
from .parser import parse, Block, Prop
from .. import mesh as M
from ..material import Material, hex_to_rgb, make_texture
from ..scene import Node, Scene
from ..uv import unwrap


class ForgeLangError(Exception):
    def __init__(self, msg, line=0, path=""):
        super().__init__(f"{path}:{line}: {msg}" if path else f"line {line}: {msg}")
        self.line = line


AXES = {"x": "x", "y": "y", "z": "z"}


def _vec(args, line, path, want=3, name="vector"):
    if len(args) == 1 and want == 3:
        args = [args[0]] * 3
    if len(args) != want:
        raise ForgeLangError(f"{name} needs {want} numbers", line, path)
    return np.array([float(a) for a in args], float)


def _color(args, line, path):
    if any(isinstance(a, str) for a in args):
        return hex_to_rgb(args[0])  # values from COLOR tokens are raw hex
    return np.array([float(a) for a in args[:3]], float)


def _num(args, line, path, name):
    if len(args) != 1:
        raise ForgeLangError(f"{name} needs exactly 1 number", line, path)
    return float(args[0])


class Interpreter:
    def __init__(self, workspace=".", strict=False):
        self.workspace = os.path.abspath(workspace)
        self.strict = strict
        self.scene = Scene("scene")
        self.report = {"errors": [], "warnings": [], "built": [],
                       "scripts": [], "sounds": {}}
        self._included = set()
        self._pending_ops = []

    # ------------------------------------------------------------- public
    def run_file(self, path):
        path = path if os.path.isabs(path) else os.path.join(self.workspace, path)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return self.run_text(text, path)

    def run_text(self, text, path="<forge>"):
        prog = parse(text, path)
        self._exec(prog, os.path.dirname(path))
        return self.scene, self.report

    # ------------------------------------------------------------ internals
    def _warn(self, msg, line, path):
        if self.strict:
            raise ForgeLangError(msg, line, path)
        self.report["warnings"].append(f"{path}:{line}: {msg}")

    def _exec(self, prog, base_dir):
        # pass 1: materials; pass 2: everything else (in file order so
        # mesh transforms compose predictably)
        for b in prog.blocks:
            if b is None:
                continue
            if isinstance(b, Block) and b.kind == "material":
                self._material(b, prog.path)
        for b in prog.blocks:
            if b is None:
                continue
            if isinstance(b, Block) and b.kind == "material":
                continue  # handled in pass 1
            if isinstance(b, Prop) and b.name == "include":
                self._include(b, base_dir)
            elif isinstance(b, Block):
                handler = getattr(self, "_b_" + b.kind, None)
                if handler is None:
                    raise ForgeLangError(
                        f"unknown block kind '{b.kind}'. Valid kinds: scene, "
                        "camera, light, material, mesh, sound, group",
                        b.line, prog.path)
                handler(b, prog.path)
            elif isinstance(b, Prop) and b.name == "script":
                self.report["scripts"].append(os.path.join(base_dir, b.args[0]))

    def _include(self, prop, base_dir):
        rel = prop.args[0]
        path = os.path.normpath(os.path.join(base_dir, rel))
        if path in self._included:
            return
        self._included.add(path)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        prog = parse(text, path)
        self._exec(prog, os.path.dirname(path))

    # ------------------------------------------------------------- blocks
    def _material(self, b, path):
        if not b.name:
            raise ForgeLangError("material needs a name", b.line, path)
        m = Material(b.name)
        for p in b.props():
            a = p.args
            if p.name == "base_color":
                m.base_color = _color(a, p.line, path)
            elif p.name == "metallic":
                m.metallic = _num(a, p.line, path, "metallic")
            elif p.name == "roughness":
                m.roughness = _num(a, p.line, path, "roughness")
            elif p.name == "emission":
                m.emission = _num(a, p.line, path, "emission")
            elif p.name == "alpha":
                m.alpha = _num(a, p.line, path, "alpha")
            elif p.name == "texture":
                kind = a[0] if a else "checker"
                size = int(a[1]) if len(a) > 1 else 64
                cells = int(a[2]) if len(a) > 2 else 8
                m.texture = make_texture(kind, size, cells=cells)
            elif p.name == "texture_file":
                fp = a[0]
                if not os.path.isabs(fp):
                    fp = os.path.join(self.workspace, fp)
                from ..pngio import read_png
                m.texture = read_png(fp)
                m.texture_file = a[0]
            else:
                self._warn(f"material: unknown property '{p.name}'", p.line, path)
        self.scene.ensure_material(m)

    def _b_scene(self, b, path):
        if b.name:
            self.scene.name = b.name
        for p in b.props():
            if p.name == "background":
                self.scene.background = _color(p.args, p.line, path)
            elif p.name == "ambient":
                self.scene.ambient = _num(p.args, p.line, path, "ambient")
            elif p.name == "gravity":
                self.scene.gravity = _num(p.args, p.line, path, "gravity")
            elif p.name == "camera":
                self.scene.active_camera = p.args[0]
            else:
                self._warn(f"scene: unknown property '{p.name}'", p.line, path)
        for sub in b.blocks():
            if sub.kind == "camera":
                self._b_camera(sub, path)
            elif sub.kind == "light":
                self._b_light(sub, path)
            else:
                self._warn(f"scene: cannot nest block kind '{sub.kind}'",
                           sub.line, path)

    def _b_camera(self, b, path):
        n = Node(b.name or self.scene.unique_name("camera"), "camera")
        n.position = np.array([6, 4.5, 8], float)
        n.extra = {"fov": 50.0, "look_at": np.array([0.0, 0.8, 0.0])}
        for p in b.props():
            if p.name == "position":
                n.position = _vec(p.args, p.line, path)
            elif p.name == "look_at":
                n.extra["look_at"] = _vec(p.args, p.line, path)
            elif p.name == "fov":
                n.extra["fov"] = _num(p.args, p.line, path, "fov")
            elif p.name == "active":
                self.scene.active_camera = n.name
            else:
                self._warn(f"camera: unknown property '{p.name}'", p.line, path)
        self.scene.add_node(n)

    def _b_light(self, b, path):
        n = Node(b.name or self.scene.unique_name("light"), "light")
        n.extra = {"type": "sun", "direction": np.array([-0.45, -1, -0.35]),
                   "color": np.array([1.0, 0.97, 0.9]), "intensity": 1.15}
        for p in b.props():
            if p.name == "type":
                n.extra["type"] = p.args[0]
            elif p.name == "direction":
                n.extra["direction"] = _vec(p.args, p.line, path)
            elif p.name == "position":
                n.position = _vec(p.args, p.line, path)
            elif p.name == "color":
                n.extra["color"] = _color(p.args, p.line, path)
            elif p.name == "intensity":
                n.extra["intensity"] = _num(p.args, p.line, path, "intensity")
            else:
                self._warn(f"light: unknown property '{p.name}'", p.line, path)
        self.scene.add_node(n)

    def _b_sound(self, b, path):
        cfg = {"volume": 0.8, "loop": False}
        for p in b.props():
            if p.name == "file":
                cfg["file"] = p.args[0]
            elif p.name == "synth":
                cfg["synth"] = p.args  # kind freq dur
            elif p.name == "volume":
                cfg["volume"] = _num(p.args, p.line, path, "volume")
            elif p.name == "loop":
                cfg["loop"] = p.args[0] in ("true", "1", True, 1)
            else:
                self._warn(f"sound: unknown property '{p.name}'", p.line, path)
        self.report["sounds"][b.name or "sound"] = cfg

    def _b_group(self, b, path):
        g = Node(b.name or "group", "group")
        self.scene.add_node(g)
        self._apply_transform(b, g, path, "group")
        for p in b.props("child"):
            child = self.scene.get(p.args[0])
            if child is None:
                self._warn(f"group: child '{p.args[0]}' not found", p.line, path)
            else:
                if child.parent:
                    child.parent.children.remove(child)
                child.parent = g
                g.children.append(child)

    def _apply_transform(self, b, n, path, kind):
        for p in b.props():
            if p.name == "position":
                n.position = _vec(p.args, p.line, path)
            elif p.name == "rotation":
                n.rotation = _vec(p.args, p.line, path)
            elif p.name == "scale":
                n.scale = _vec(p.args, p.line, path)
            elif kind != "group" and p.name not in ("position", "rotation", "scale"):
                continue

    # ------------------------------------------------------------- meshes
    def _b_mesh(self, b, path):
        if not b.name:
            raise ForgeLangError("mesh needs a name", b.line, path)
        params = {}
        ops = []
        mat_name, uv_spec = None, None
        body = None
        scripts = []
        for it in b.items:
            if isinstance(it, Block) and it.kind == "body":
                body = it
            elif isinstance(it, Prop):
                if it.name == "position" or it.name == "rotation" or it.name == "scale":
                    continue
                elif it.name == "material":
                    mat_name = it.args[0]
                elif it.name == "uv":
                    uv_spec = it.args
                elif it.name in ("subdivide", "mirror", "twist", "taper", "noise",
                                 "smooth", "weld"):
                    ops.append(it)
                elif it.name == "script":
                    scripts.append(it.args[0])
                else:
                    params[it.name] = (it.args, it.line)

        prim = params.get("primitive", (["box"], b.line))[0][0]
        if prim not in M.PRIMITIVES:
            raise ForgeLangError(
                f"unknown primitive '{prim}'. Available: " +
                ", ".join(sorted(M.PRIMITIVES)), b.line, path)
        kwargs = {}
        get = lambda n: params[n][0] if n in params else None
        if prim in ("box", "cube"):
            if (s := get("size")): kwargs["sx"], kwargs["sy"], kwargs["sz"] = \
                ([float(x) for x in s] + [float(s[0])] * 3)[:3]
        elif prim == "sphere":
            if (r := get("radius")): kwargs["radius"] = float(r[0])
            if (r := get("rings")): kwargs["rings"] = int(r[0])
            if (s := get("segments")): kwargs["segments"] = int(s[0])
        elif prim == "cylinder":
            if (r := get("radius")): kwargs["radius"] = float(r[0])
            if (h := get("height")): kwargs["height"] = float(h[0])
            if (s := get("segments")): kwargs["segments"] = int(s[0])
        elif prim == "cone":
            if (r := get("radius")): kwargs["radius"] = float(r[0])
            if (h := get("height")): kwargs["height"] = float(h[0])
            if (s := get("segments")): kwargs["segments"] = int(s[0])
        elif prim in ("plane", "grid"):
            if (s := get("size")):
                if prim == "plane":
                    kwargs["size"] = float(s[0])
                else:
                    kwargs["sx"], kwargs["sz"] = float(s[0]), float(s[1]) if len(s) > 1 else float(s[0])
            if (x := get("subdivisions")):
                kwargs["subdivisions" if prim == "plane" else "nx"] = int(x[0])
                if prim == "grid": kwargs["nz"] = int(x[1]) if len(x) > 1 else int(x[0])
        elif prim == "torus":
            if (r := get("radius")): kwargs["radius"] = float(r[0])
            if (r := get("tube")): kwargs["tube"] = float(r[0])
            if (r := get("segments")): kwargs["radial"] = int(r[0])
            if (r := get("rings")): kwargs["tubular"] = int(r[0])
        elif prim == "capsule":
            if (r := get("radius")): kwargs["radius"] = float(r[0])
            if (h := get("height")): kwargs["height"] = float(h[0])
            if (r := get("rings")): kwargs["rings"] = int(r[0])
            if (s := get("segments")): kwargs["segments"] = int(s[0])
        # unknown params in strict mode
        known = {"primitive", "size", "radius", "tube", "height", "segments",
                 "rings", "sides", "subdivisions", "nx", "nz"}
        for k, (args, line) in params.items():
            if k not in known:
                self._warn(f"mesh: unknown param '{k}' ignored", line, path)

        msh = M.PRIMITIVES[prim](**kwargs)
        for op in ops:
            a = op.args
            if op.name == "subdivide":
                M.subdivide(msh, int(a[0]) if a else 1)
            elif op.name == "mirror":
                M.mirror(msh, (a[0] if a else "x"))
            elif op.name == "twist":
                M.twist(msh, a[0], float(a[1]) if len(a) > 1 else 45.0)
            elif op.name == "taper":
                M.taper(msh, a[0], float(a[1]) if len(a) > 1 else 0.5)
            elif op.name == "noise":
                M.noise_displace(msh, float(a[0]) if a else 0.05,
                                 int(a[1]) if len(a) > 1 else 0)
            elif op.name == "smooth":
                M.laplacian_smooth(msh, int(a[0]) if a else 1,
                                   float(a[1]) if len(a) > 1 else 0.5)
            elif op.name == "weld":
                M.weld_vertices(msh, float(a[0]) if a else 1e-6)
        if uv_spec:
            msh = unwrap(msh, uv_spec[0], uv_spec[1] if len(uv_spec) > 1 else "y")

        n = Node(b.name, "mesh")
        n.mesh = msh
        if mat_name:
            mat = self.scene.get_material(mat_name)
            if mat is None:
                raise ForgeLangError(f"material '{mat_name}' is not defined "
                                     "(define it before use)", b.line, path)
            n.material = mat
        self._apply_transform(b, n, path, "mesh")
        if body is not None:
            bd = {}
            if body.name:
                bd["shape"] = body.name
            for p in body.props():
                if p.name == "mass":
                    bd["mass"] = float(p.args[0])
                elif p.name == "restitution":
                    bd["restitution"] = float(p.args[0])
                elif p.name == "static":
                    bd["static"] = p.args[0] in ("true", "1", True, 1)
                elif p.name == "shape":
                    bd["shape"] = p.args[0]
                elif p.name == "velocity":
                    bd["velocity"] = [float(x) for x in p.args]
            n.extra["body"] = bd
        if scripts:
            n.extra["scripts"] = scripts
            base = os.path.dirname(path) or self.workspace
            self.report["scripts"].extend(
                [s if os.path.isabs(s) else os.path.join(base, s)
                 for s in scripts])
        self.scene.add_node(n)
        self.report["built"].append(b.name)
