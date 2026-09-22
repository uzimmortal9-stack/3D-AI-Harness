"""Forge3D Doctor — deterministic geometry & scene health checks.

This is the machine-verifiable feedback channel that lets AI agents see and
fix their own mistakes: `forge3d doctor scene.forge --json`.
"""
import numpy as np


def _edge_keys(faces):
    e = np.concatenate([
        faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]
    ], axis=0)
    e = np.sort(e, axis=1)
    return e


def examine_mesh(mesh, name="mesh"):
    """Returns dict with metrics + issue list."""
    issues = []
    r = {"name": name, "vertices": int(mesh.vertex_count),
         "triangles": int(mesh.face_count), "watertight": False,
         "has_uvs": mesh.uvs is not None, "has_vertex_colors": mesh.colors is not None}

    v, f = mesh.vertices, mesh.faces
    if len(v) == 0 or len(f) == 0:
        issues.append(("error", "EMPTY_MESH", "Mesh has no geometry",
                       "Use a primitive or check your ForgeScript mesh body."))
        r["issues"] = issues
        return r

    # NaNs / inf
    bad = int(np.isfinite(v).sum() != v.size)
    nan_count = int((~np.isfinite(v)).any(axis=1).sum())
    if nan_count:
        issues.append(("error", "NON_FINITE_VERTICES",
                       f"{nan_count} vertices contain NaN/inf",
                       "Caused by divide-by-zero in an op. Reduce taper/twist magnitudes."))

    # degenerate triangles
    areas = mesh.face_areas()
    degen = int((areas < 1e-12).sum())
    if degen:
        issues.append(("error", "DEGENERATE_TRIANGLES",
                       f"{degen} zero-area triangles",
                       "Merge duplicate vertices or avoid `noise 0` / zero-size primitives."))

    # duplicate faces
    sorted_f = np.sort(f, axis=1)
    dup = int(len(sorted_f) - len(np.unique(sorted_f, axis=0)))
    if dup:
        issues.append(("warn", "DUPLICATE_FACES", f"{dup} duplicated triangles",
                       "Remove duplicated geometry; check for double `include` or merges."))

    # edge manifold analysis on a WELDED copy (hard-edge meshes like boxes
    # duplicate verts per face; topology must be judged after welding)
    from .mesh import weld_vertices
    wm = mesh.copy()
    weld_vertices(wm, 1e-6)
    wf = wm.faces
    edges = _edge_keys(wf)
    uniq, counts = np.unique(edges, axis=0, return_counts=True)
    boundary = int((counts == 1).sum())
    nonmanifold = int((counts > 2).sum())
    r["boundary_edges"] = boundary
    r["nonmanifold_edges"] = nonmanifold
    r["watertight"] = (boundary == 0 and nonmanifold == 0 and degen == 0 and nan_count == 0)
    if nonmanifold:
        issues.append(("error", "NON_MANIFOLD", f"{nonmanifold} edges shared by 3+ faces",
                       "Geometry intersects itself. Separate overlapping parts."))
    elif boundary:
        issues.append(("warn", "OPEN_MESH", f"{boundary} boundary (open) edges",
                       "Surface is not closed; fine for terrain/planes, bad for solids "
                       "that need baking/3D-print/physics."))

    # zero-length edges
    e0, e1, e2 = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    lens = np.concatenate([np.linalg.norm(e1 - e0, axis=1),
                           np.linalg.norm(e2 - e1, axis=1),
                           np.linalg.norm(e0 - e2, axis=1)])
    zero_edges = int((lens < 1e-9).sum())
    if zero_edges:
        issues.append(("error", "ZERO_LENGTH_EDGES", f"{zero_edges} zero-length edges",
                       "Weld vertices with a small epsilon."))

    # winding consistency: each undirected edge should be traversed equally
    # in both directions on a consistently-oriented surface
    de = np.concatenate([wf[:, [0, 1]], wf[:, [1, 2]], wf[:, [2, 0]]], axis=0)
    fwd = {}
    for a, b in de:
        key = (int(a), int(b)) if a < b else (int(b), int(a))
        dirv = 1 if a < b else -1
        fwd.setdefault(key, [0, 0])[0 if dirv > 0 else 1] += 1
    inconsistent = sum(1 for c in fwd.values() if c[0] != c[1] and
                       (c[0] > 0 and c[1] > 0))
    r["inconsistent_edges"] = int(inconsistent)
    tri = v[f]
    vol6 = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2]))
    inside_out = r["watertight"] and float(vol6.sum()) < 0
    r["inverted_faces"] = int(inconsistent) + (len(f) if inside_out else 0)
    if inside_out:
        issues.append(("error", "INSIDE_OUT",
                       "Closed mesh has inward-facing winding everywhere",
                       "Faces were built in reverse order; rebuild or mirror again."))
    elif inconsistent:
        issues.append(("warn", "INCONSISTENT_WINDING",
                       f"{inconsistent} edges have conflicting face directions",
                       "Mixed winding breaks shading/baking; rebuild the affected part."))

    # connected components (islands) on the welded mesh
    nv = len(wm.vertices)
    parent = np.arange(nv)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in uniq:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    used = set(wf.ravel().tolist())
    roots = {find(i) for i in used}
    r["islands"] = len(roots)

    # budgets
    if len(f) > 250_000:
        issues.append(("warn", "HIGH_POLY", f"{len(f)} triangles is heavy for real-time",
                       "Use fewer segments/subdivisions, or split into LODs."))
    lo, hi = mesh.bounds()
    ext = hi - lo
    if ext.max() > 500:
        issues.append(("warn", "HUGE_SCALE", f"Object spans {ext.max():.0f} units",
                       "Keep scenes in a sane scale (1 unit = 1 m) for physics and camera."))
    if ext.max() > 0 and ext.min() / max(ext.max(), 1e-9) < 1e-4 and mesh.face_count > 12:
        issues.append(("warn", "FLAT_OBJECT", "Object is nearly 2D (one axis ~0)",
                       "If you meant a solid, give it thickness."))

    r["issues"] = issues
    return r


def examine_scene(scene):
    report = {"scene": scene.name, "stats": scene.stats(), "meshes": [],
              "issues": [], "score": 100}
    for n in scene.mesh_nodes():
        mr = examine_mesh(n.mesh, n.name)
        report["meshes"].append(mr)
        for lvl, code, msg, hint in mr["issues"]:
            report["issues"].append({"level": lvl, "code": code, "object": n.name,
                                     "message": msg, "hint": hint})
        if n.material is None:
            report["issues"].append({"level": "warn", "code": "NO_MATERIAL",
                                     "object": n.name,
                                     "message": "Mesh has no material assigned",
                                     "hint": "Add `material <name>` to the mesh block."})
    if not scene.cameras():
        report["issues"].append({"level": "warn", "code": "NO_CAMERA", "object": "-",
                                 "message": "No camera defined (auto camera used)",
                                 "hint": "Add a `camera` block to control framing."})
    if not scene.lights():
        report["issues"].append({"level": "warn", "code": "NO_LIGHT", "object": "-",
                                 "message": "No light defined (auto sun used)",
                                 "hint": "Add a `light` block to shape the mood."})

    penalty = 0
    for i in report["issues"]:
        penalty += 20 if i["level"] == "error" else 5
    report["score"] = max(0, 100 - penalty)
    report["clean"] = report["score"] >= 95
    return report


def report_text(report):
    lines = [f"FORGE DOCTOR — scene '{report['scene']}'  "
             f"score {report['score']}/100  ({'CLEAN' if report['clean'] else 'ISSUES FOUND'})"]
    st = report["stats"]
    lines.append(f"  nodes={st['nodes']} meshes={st['meshes']} "
                 f"verts={st['vertices']} tris={st['triangles']}")
    if not report["issues"]:
        lines.append("  All checks passed.")
    for i in report["issues"]:
        lines.append(f"  [{i['level'].upper():5}] {i['code']} ({i['object']}): {i['message']}")
        lines.append(f"          fix: {i['hint']}")
    return "\n".join(lines)
