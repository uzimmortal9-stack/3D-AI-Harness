"""Forge3D standard export pipeline: OBJ (+MTL), STL, glTF 2.0 (embedded), scene JSON."""
import base64
import json
import os
import struct

import numpy as np

from .math3d import transform_points
from .material import rgb_to_hex


def _world_meshes(scene):
    out = []
    for n in scene.mesh_nodes():
        m = n.mesh.copy()
        m.vertices = transform_points(scene.world_matrix(n), m.vertices)
        m.update_normals()
        out.append((n, m))
    return out


def export_obj(scene, path):
    """Wavefront OBJ with materials. Bakes world transforms."""
    mtl_path = os.path.splitext(path)[0] + ".mtl"
    lines = [f"# Forge3D export — scene '{scene.name}'",
             f"mtllib {os.path.basename(mtl_path)}"]
    mtl = ["# Forge3D materials"]
    seen_mats = set()
    voff = 1
    for n, m in _world_meshes(scene):
        lines.append(f"o {n.name}")
        for p in m.vertices:
            lines.append(f"v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}")
        for p in (m.normals if m.normals is not None else []):
            lines.append(f"vn {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}")
        mat = n.material
        if mat is not None:
            if mat.name not in seen_mats:
                seen_mats.add(mat.name)
                c = mat.base_color
                mtl += [f"newmtl {mat.name}",
                        f"Kd {c[0]:.4f} {c[1]:.4f} {c[2]:.4f}",
                        f"Ka {c[0] * 0.2:.4f} {c[1] * 0.2:.4f} {c[2] * 0.2:.4f}",
                        f"Ks {0.5:.2f} {0.5:.2f} {0.5:.2f}",
                        f"Ns {max(2.0, (1.0 - mat.roughness) * 256):.1f}",
                        f"d {mat.alpha}"]
            lines.append(f"usemtl {mat.name}")
        for f in m.faces:
            a, b, c = f[0] + voff, f[1] + voff, f[2] + voff
            lines.append(f"f {a}//{a} {b}//{b} {c}//{c}")
        voff += len(m.vertices)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(mtl_path, "w") as f:
        f.write("\n".join(mtl) + "\n")
    return [path, mtl_path]


def export_stl(scene, path):
    """Binary STL (for 3D printing)."""
    tris = []
    for n, m in _world_meshes(scene):
        fn = m.face_normals()
        tri = m.vertices[m.faces]
        tris.append(np.concatenate([fn[:, None, :], tri], axis=1))
    data = np.vstack(tris) if tris else np.zeros((0, 4, 3))
    with open(path, "wb") as f:
        f.write(b"\0" * 80)
        f.write(struct.pack("<I", len(data)))
        for t in data:
            n, v0, v1, v2 = t
            f.write(struct.pack("<12fH", *n, *v0, *v1, *v2, 0))
    return [path]


def export_gltf(scene, path):
    """Minimal glTF 2.0 with embedded buffer (single file, importable anywhere)."""
    buffers, buffer_views, accessors, meshes, nodes = [], [], [], [], []
    mat_ids, mat_defs = {}, []

    def push(arr, target):
        data = np.ascontiguousarray(arr).tobytes()
        offset = sum(len(b) for b in buffers)
        pad = (4 - len(data) % 4) % 4
        buffers.append(data + b"\0" * pad)
        buffer_views.append({"buffer": 0, "byteOffset": offset,
                             "byteLength": len(data), "target": target})
        return len(buffer_views) - 1

    def mat_index(mat):
        if mat is None:
            return None
        if mat.name not in mat_ids:
            mat_ids[mat.name] = len(mat_defs)
            mat_defs.append({
                "name": mat.name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [float(mat.base_color[0]),
                                        float(mat.base_color[1]),
                                        float(mat.base_color[2]),
                                        float(mat.alpha)],
                    "metallicFactor": float(mat.metallic),
                    "roughnessFactor": float(mat.roughness)}})
        return mat_ids[mat.name]

    for n in scene.mesh_nodes():
        m = n.mesh
        pos = m.vertices.astype(np.float32)
        nrm = (m.normals if m.normals is not None else np.zeros_like(pos)).astype(np.float32)
        pos_v = push(pos, 34962)
        nrm_v = push(nrm, 34962)
        accessors.append({"bufferView": pos_v, "componentType": 5126,
                          "count": len(pos), "type": "VEC3",
                          "min": pos.min(axis=0).tolist(),
                          "max": pos.max(axis=0).tolist()})
        pos_acc = len(accessors) - 1
        accessors.append({"bufferView": nrm_v, "componentType": 5126,
                          "count": len(nrm), "type": "VEC3"})
        nrm_acc = len(accessors) - 1
        prim = {"attributes": {"POSITION": pos_acc, "NORMAL": nrm_acc},
                "mode": 4}
        if m.uvs is not None:
            uv_v = push(m.uvs.astype(np.float32), 34962)
            accessors.append({"bufferView": uv_v, "componentType": 5126,
                              "count": len(m.uvs), "type": "VEC2"})
            prim["attributes"]["TEXCOORD_0"] = len(accessors) - 1
        idx = m.faces.astype(np.uint32 if len(pos) > 65535 else np.uint16)
        ctype = 5125 if idx.dtype == np.uint32 else 5123
        idx_v = push(idx, 34963)
        accessors.append({"bufferView": idx_v, "componentType": ctype,
                          "count": idx.size, "type": "SCALAR"})
        prim["indices"] = len(accessors) - 1
        mi = mat_index(n.material)
        if mi is not None:
            prim["material"] = mi
        meshes.append({"name": n.name, "primitives": [prim]})
        nodes.append({
            "name": n.name, "mesh": len(meshes) - 1,
            "translation": [float(x) for x in n.position],
            "rotation": _quat_from_euler(n.rotation),
            "scale": [float(x) for x in n.scale]})

    blob = b"".join(buffers)
    gltf = {
        "asset": {"version": "2.0", "generator": "Forge3D"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes, "meshes": meshes, "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(blob),
                     "uri": "data:application/octet-stream;base64,"
                            + base64.b64encode(blob).decode()}],
        "materials": mat_defs,
    }
    with open(path, "w") as f:
        json.dump(gltf, f)
    return [path]


def _quat_from_euler(e):
    import math
    rx, ry, rz = [math.radians(x) / 2 for x in e]
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    # Rz @ Ry @ Rx
    w = cz * cy * cx + sz * sy * sx
    x = cz * cy * sx - sz * sy * cx
    y = cz * sy * cx + sz * cy * sx
    z = sz * cy * cx - cz * sy * sx
    return [x, y, z, w]


def export_scene_json(scene, path):
    with open(path, "w") as f:
        json.dump(scene.to_dict(), f, indent=1)
    return [path]


EXPORTERS = {"obj": export_obj, "stl": export_stl, "gltf": export_gltf,
             "json": export_scene_json}
