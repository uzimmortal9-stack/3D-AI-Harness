"""Forge3D UV unwrapping systems: planar, box (dominant-axis), cylindrical.

The unwrappers work on an *unindexed* copy of the mesh so every face gets its
own seam-free UV space (simple and robust for baking/prototyping).
"""
import numpy as np


def unwrap(mesh, method="box", axis="y"):
    m = mesh.unindex()
    fn = m.face_normals()
    ax = {"x": 0, "y": 1, "z": 2}.get(axis, 1)
    uv = np.zeros((len(m.vertices), 2), float)
    v3 = m.vertices

    if method == "planar":
        axes = [i for i in range(3) if i != ax]
        uv[:, 0] = v3[:, axes[0]]
        uv[:, 1] = v3[:, axes[1]]
    elif method == "cylinder":
        theta = np.arctan2(v3[:, 2], v3[:, 0])
        uv[:, 0] = theta / (2 * np.pi) + 0.5
        y = v3[:, 1]
        lo, hi = y.min(), y.max()
        uv[:, 1] = (y - lo) / ((hi - lo) or 1.0)
    else:  # box projection: pick dominant axis per face
        best = np.argmax(np.abs(fn), axis=1)
        for dom in range(3):
            sel = np.where(best == dom)[0]
            if len(sel) == 0:
                continue
            axes = [i for i in range(3) if i != dom]
            corner_ids = m.faces[sel].reshape(-1)
            uv[corner_ids, 0] = v3[corner_ids, axes[0]]
            uv[corner_ids, 1] = v3[corner_ids, axes[1]]

    # normalize to 0..1 with small padding
    if len(uv):
        lo = uv.min(axis=0)
        hi = uv.max(axis=0)
        span = np.maximum(hi - lo, 1e-9)
        uv = (uv - lo) / span
        uv = 0.05 + uv * 0.90
    m.uvs = uv
    return m
