"""Forge3D — an AI-native real-time 3D creation platform.

Base version (v0.1). Local-first: no web, no cloud. Everything an AI agent
needs to build 3D scenes/games, verify its own work, and fix its mistakes.
"""
__version__ = "0.1.0"
__codename__ = "Basecamp"

from .mesh import (Mesh, make_box, make_sphere, make_cylinder, make_cone,
                   make_plane, make_grid, make_torus, make_capsule, lathe,
                   subdivide, mirror, twist, taper, noise_displace,
                   laplacian_smooth, weld_vertices, merge_meshes, PRIMITIVES)
from .scene import Scene, Node
from .material import Material, make_texture, hex_to_rgb, rgb_to_hex
from .raster import render_scene, multi_view, SoftwareRenderer
from .doctor import examine_mesh, examine_scene, report_text
from . import uv, exporter, baker, anim, physics, audio, math3d, pngio

__all__ = [k for k in dir() if not k.startswith("_")]
