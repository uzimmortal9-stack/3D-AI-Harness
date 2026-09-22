"""Forge3D baking engine — ambient occlusion & sun-shadow baked to vertex colors.

Ray-cast based (vectorized Möller–Trumbore). Deterministic and dependency-free.
Bake time scales with verts x triangles x rays — keep `rays` modest on dense
meshes (16–32 is plenty for prototypes).
"""
import numpy as np


def _row_normalize(a):
    n = np.linalg.norm(a, axis=1, keepdims=True)
    n[n < 1e-12] = 1.0
    return a / n


def _any_hit(origins, dirs, tri, max_dist):
    """For each ray i, True if ray i hits any triangle within max_dist."""
    v0, v1, v2 = tri[:, 0], tri[:, 1], tri[:, 2]
    e1, e2 = v1 - v0, v2 - v0
    R, T = origins.shape[0], tri.shape[0]
    blocked = np.zeros(R, bool)
    chunk = max(1, 4_000_000 // max(T, 1))
    for s in range(0, R, chunk):
        rr = slice(s, s + chunk)
        d = dirs[rr][:, None, :]                       # (r, 1, 3)
        hs = np.cross(d, e2[None, :, :])               # (r, T, 3)
        a2 = np.einsum("tj,rtj->rt", e1, hs)
        f = 1.0 / np.where(np.abs(a2) > 1e-9, a2, 1e9)
        sv = origins[rr][:, None, :] - v0[None, :, :]
        u = f * np.einsum("rtj,rtj->rt", sv, hs)
        q = np.cross(sv, e1[None, :, :])
        vv = f * np.einsum("rtj,rtj->rt", d, q)
        t = f * np.einsum("rtj,tj->rt", hs, e2)
        ok = (np.abs(a2) > 1e-9) & (u >= 0) & (u <= 1) & (vv >= 0) & \
             (u + vv <= 1) & (t > 1e-4) & (t < max_dist)
        blocked[rr] = ok.any(axis=1)
    return blocked


def bake_vertex_ao(mesh, rays=24, seed=1):
    """Bakes ambient occlusion into mesh.colors (renderer multiplies it in)."""
    v = mesh.vertices
    n = mesh.normals if mesh.normals is not None else mesh.update_normals()
    tri = v[mesh.faces]
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(rays, 3))
    base[:, 2] = np.abs(base[:, 2]) + 0.35
    base = _row_normalize(base)
    extent = float(np.linalg.norm(mesh.bounds()[1] - mesh.bounds()[0]))
    max_dist = extent * 2.0 + 1.0
    orig = v + n * 1e-4
    dirs = _row_normalize((n[:, None, :] * 0.6 + base[None, :, :]).reshape(-1, 3)) \
        .reshape(len(v), rays, 3)
    ao = np.zeros(len(v))
    for r in range(rays):
        ao += _any_hit(orig, dirs[:, r], tri, max_dist).astype(float)
    ao = np.clip(0.25 + 0.75 * (1.0 - ao / rays), 0, 1)
    mesh.colors = np.stack([ao] * 3, axis=1)
    return mesh


def bake_sun_shadow(scene):
    """Bakes binary sun visibility into vertex colors of all meshes."""
    from .math3d import transform_points, normalize
    sun = scene.default_light()
    d = normalize(np.asarray(sun.extra.get("direction", [-0.45, -1, -0.35]), float))
    wmeshes = []
    for n in scene.mesh_nodes():
        m = n.mesh.copy()
        m.vertices = transform_points(scene.world_matrix(n), m.vertices)
        m.update_normals()
        wmeshes.append((n, m))
    all_tri = np.vstack([m.vertices[m.faces] for _, m in wmeshes])
    for n, m in wmeshes:
        orig = m.vertices + m.normals * 1e-4
        blocked = _any_hit(orig, np.tile(-d, (len(orig), 1)), all_tri, 500.0)
        shade = np.where(blocked, 0.45, 1.0)
        n.mesh.colors = np.stack([shade] * 3, axis=1)
    return scene
