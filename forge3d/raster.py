"""Forge3D CPU software rasterizer — the AI's eyes.

Renders a Scene to an RGB image with zero GPU dependency, so any AI agent can
inspect what it built (Vision Loop: build -> render -> observe -> fix) on any
machine, including headless ones. Gouraud shading, z-buffer, perspective
correct UVs, near-plane clipping, wireframe overlay.
"""
import numpy as np

from .math3d import look_at, perspective, transform_points, transform_directions, normalize


def _bg_gradient(color, h, w):
    top = np.clip(color * 1.6 + 0.06, 0, 1)
    bot = np.clip(color * 0.55, 0, 1)
    ramp = np.linspace(1, 0, h)[:, None, None]
    img = (bot[None, None, :] + (top - bot)[None, None, :] * ramp)
    return np.repeat(img, w, axis=1)


def _clip_triangle_near(vp, attrs, near):
    """Sutherland-Hodgman clip against view-space near plane (z <= -near)."""
    out_v, out_a = [], []
    n = 3
    for i in range(n):
        j = (i + 1) % n
        vi, vj = vp[i], vp[j]
        ai, aj = attrs[i], attrs[j]
        di, dj = -vi[2] - near, -vj[2] - near  # >0 means inside
        if di >= 0:
            out_v.append(vi); out_a.append(ai)
        if (di >= 0) != (dj >= 0):
            t = di / (di - dj)
            out_v.append(vi + t * (vj - vi))
            out_a.append(ai + t * (aj - ai))
    if len(out_v) < 3:
        return []
    tris = []
    for i in range(1, len(out_v) - 1):
        tris.append((np.array([out_v[0], out_v[i], out_v[i + 1]]),
                     np.array([out_a[0], out_a[i], out_a[i + 1]])))
    return tris


class SoftwareRenderer:
    def __init__(self, width=640, height=480):
        self.width = int(width)
        self.height = int(height)

    def render(self, scene, camera=None, wire=False):
        w, h = self.width, self.height
        cam = camera or scene.default_camera()
        scene.default_light()
        look = cam.extra.get("look_at", np.array([0.0, 0.8, 0.0]))
        look = np.asarray(look, float)
        fov = float(cam.extra.get("fov", 50.0))
        view = look_at(cam.position, look)
        aspect = w / max(1, h)
        near, far = 0.05, 1000.0
        f = 1.0 / np.tan(np.radians(fov) / 2.0)

        frame = _bg_gradient(scene.background, h, w)
        depth = np.full((h, w), np.inf, float)

        # gather lights
        suns, points = [], []
        for ln in scene.lights():
            e = ln.extra
            if e.get("type", "sun") == "sun":
                d = normalize(np.asarray(e.get("direction", [-0.45, -1, -0.35]), float))
                suns.append((-d, np.asarray(e.get("color", [1, 1, 1]), float)
                             * float(e.get("intensity", 1.0))))
            else:
                points.append((np.asarray(ln.position, float),
                               np.asarray(e.get("color", [1, 1, 1]), float)
                               * float(e.get("intensity", 1.0))))
        if not suns:
            suns.append((normalize(np.array([0.45, 1, 0.35])), np.array([1.0, 0.97, 0.9]) * 1.15))

        for node in scene.mesh_nodes():
            if not node.visible:
                continue
            mesh = node.mesh
            world = scene.world_matrix(node)
            wpos = transform_points(world, mesh.vertices)
            if mesh.normals is not None:
                wn = transform_directions(world, mesh.normals)
                ln = np.linalg.norm(wn, axis=1, keepdims=True)
                ln[ln < 1e-12] = 1.0
                wnorm = wn / ln
            else:
                wnorm = np.zeros_like(wpos)
            mat = node.material
            base = mat.base_color if mat else np.array([0.8, 0.8, 0.8])
            emiss = mat.emission if mat else 0.0

            # ---------------- per-vertex lighting (Gouraud)
            light = np.full((len(wpos), 3), scene.ambient, float)
            for d, c in suns:
                ndl = np.clip(wnorm @ d, 0, None)
                light += ndl[:, None] * c[None, :]
            for ppos, pc in points:
                to_l = ppos[None, :] - wpos
                dist = np.linalg.norm(to_l, axis=1, keepdims=True)
                dist_s = np.maximum(dist, 1e-3)
                ndl = np.clip((wnorm * to_l / dist_s).sum(axis=1), 0, None)
                light += ndl[:, None] * (pc / (1.0 + 0.15 * dist_s[:, 0] ** 2))[:, None]
            shade = base[None, :] * light
            if emiss > 0:
                shade = shade + base[None, :] * emiss
            if mesh.colors is not None:
                shade = shade * mesh.colors
            shade = np.clip(shade, 0, 1.6)

            has_uv = mesh.uvs is not None and mat is not None and \
                (mat.texture is not None or getattr(mat, "_tex_cache", None) is not None)
            vview = transform_points(view, wpos)

            # per triangle: clip, project, rasterize
            tris = vview[mesh.faces]
            colors = shade[mesh.faces]
            uvs = mesh.uvs[mesh.faces] if has_uv else None
            self._rasterize_batch(frame, depth, tris, colors, uvs, mat,
                                  view, f, aspect, near, w, h)

        if wire:
            self._wireframe(frame, scene, view, f, aspect, near, w, h)

        img = np.clip(frame, 0, 1)
        # gamma
        img = np.power(img, 1 / 2.2)
        return (img * 255).astype(np.uint8)

    # ------------------------------------------------------------------
    def _rasterize_batch(self, frame, depth, tris, colors, uvs, mat,
                         view, f, aspect, near, w, h):
        for ti in range(len(tris)):
            vp = tris[ti]
            if uvs is not None:
                attrs = np.concatenate([colors[ti], uvs[ti]], axis=1)
            else:
                attrs = colors[ti]
            for cvp, cattr in _clip_triangle_near(vp, attrs, near):
                self._rasterize_one(frame, depth, cvp, cattr, mat, f, aspect, w, h)

    def _rasterize_one(self, frame, depth, vp, attr, mat, f, aspect, w, h):
        z = -vp[:, 2]
        inv_z = 1.0 / z
        sx = (vp[:, 0] * f / aspect) * inv_z
        sy = (vp[:, 1] * f) * inv_z
        px = ((sx + 1) * 0.5 * w)
        py = ((1 - sy) * 0.5 * h)
        minx = max(int(np.floor(px.min())), 0)
        maxx = min(int(np.ceil(px.max())), w - 1)
        miny = max(int(np.floor(py.min())), 0)
        maxy = min(int(np.ceil(py.max())), h - 1)
        if minx > maxx or miny > maxy:
            return
        xs = np.arange(minx, maxx + 1) + 0.5
        ys = np.arange(miny, maxy + 1) + 0.5
        X, Y = np.meshgrid(xs, ys)
        x0, y0, x1, y1, x2, y2 = px[0], py[0], px[1], py[1], px[2], py[2]
        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-12:
            return
        l0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / denom
        l1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / denom
        l2 = 1.0 - l0 - l1
        mask = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not mask.any():
            return
        zpix = 1.0 / (l0 * inv_z[0] + l1 * inv_z[1] + l2 * inv_z[2])
        ys_i, xs_i = np.where(mask)
        zz = zpix[mask]
        rows, cols = ys_i + miny, xs_i + minx
        cur = depth[rows, cols]
        visible = zz < cur
        if not visible.any():
            return
        rows, cols, zz = rows[visible], cols[visible], zz[visible]
        depth[rows, cols] = zz
        lam = np.stack([l0[mask][visible], l1[mask][visible], l2[mask][visible]])
        iz = inv_z[:, None] * lam
        wsum = iz.sum(axis=0)
        cols_n = attr.shape[1]
        vals = (attr.T @ iz) / np.maximum(wsum, 1e-12)
        rgb = vals[:3].T
        if mat is not None and cols_n > 3 and mat.texture is not None:
            tex = mat.texture
            th, tw = tex.shape[:2]
            uu = np.mod(vals[3], 1.0) * (tw - 1)
            vv = np.mod(vals[4], 1.0) * (th - 1)
            tcol = tex[vv.astype(int), uu.astype(int)].astype(float) / 255.0
            rgb = rgb * tcol
        frame[rows, cols] = np.clip(rgb, 0, 1.6)

    def _wireframe(self, frame, scene, view, f, aspect, near, w, h):
        seen = set()
        for node in scene.mesh_nodes():
            mesh = node.mesh
            world = scene.world_matrix(node)
            wpos = transform_points(world, mesh.vertices)
            vpos = transform_points(view, wpos)
            for a, b, c in mesh.faces:
                for i, j in ((a, b), (b, c), (c, a)):
                    key = (node.name, i, j) if i < j else (node.name, j, i)
                    if key in seen:
                        continue
                    seen.add(key)
                    p0, p1 = vpos[i], vpos[j]
                    if -p0[2] < near or -p1[2] < near:
                        continue
                    s0 = np.array([((p0[0] * f / aspect) / -p0[2] + 1) * 0.5 * w,
                                   (1 - (p0[1] * f) / -p0[2]) * 0.5 * h])
                    s1 = np.array([((p1[0] * f / aspect) / -p1[2] + 1) * 0.5 * w,
                                   (1 - (p1[1] * f) / -p1[2]) * 0.5 * h])
                    steps = int(max(abs(s1[0] - s0[0]), abs(s1[1] - s0[1])))
                    if steps <= 0 or steps > 2000:
                        continue
                    for t in np.linspace(0, 1, steps + 1):
                        x = int(s0[0] + t * (s1[0] - s0[0]))
                        y = int(s0[1] + t * (s1[1] - s0[1]))
                        if 0 <= x < w and 0 <= y < h:
                            frame[y, x] = np.array([0.1, 0.1, 0.1])


def render_scene(scene, width=640, height=480, camera=None, wire=False):
    return SoftwareRenderer(width, height).render(scene, camera=camera, wire=wire)


def multi_view(scene, size=320):
    """Render front/top/side/iso sheets — used by agents for self-checking."""
    lo, hi = scene.bounds()
    c = (lo + hi) / 2.0
    r = max(float(np.linalg.norm(hi - lo)) * 1.2, 2.0)
    from .scene import Node
    from .math3d import orbit_camera
    views = {}
    for name, yaw, pitch in [("front", 0, 12), ("back", 180, 12),
                             ("side", 90, 12), ("iso", 45, 28), ("top", 0.001, 85)]:
        cam = Node(f"__view_{name}", "camera")
        cam.position = orbit_camera(c, yaw, pitch, r)
        cam.extra = {"fov": 45.0, "look_at": c}
        views[name] = render_scene(scene, size, size, camera=cam)
    return views
