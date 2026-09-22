"""Forge3D geometry kernel — meshes, primitives, and mesh editing operations.

Conventions:
  * vertices: float64 ndarray (N, 3)
  * faces:    int64 ndarray (M, 3), triangles, CCW winding viewed from outside
  * normals point outward
"""
import numpy as np


class Mesh:
    def __init__(self, vertices, faces, name="mesh"):
        self.name = name
        self.vertices = np.asarray(vertices, dtype=float)
        self.faces = np.asarray(faces, dtype=np.int64)
        self.uvs = None          # optional (N, 2)
        self.colors = None       # optional (N, 3) vertex colors (bakes, tints)
        self.normals = None      # (N, 3), computed
        self.update_normals()

    # ------------------------------------------------------------------ info
    @property
    def vertex_count(self):
        return len(self.vertices)

    @property
    def face_count(self):
        return len(self.faces)

    def bounds(self):
        if len(self.vertices) == 0:
            return np.zeros(3), np.zeros(3)
        return self.vertices.min(axis=0), self.vertices.max(axis=0)

    def copy(self):
        m = Mesh(self.vertices.copy(), self.faces.copy(), self.name)
        m.uvs = None if self.uvs is None else self.uvs.copy()
        m.colors = None if self.colors is None else self.colors.copy()
        return m

    # --------------------------------------------------------------- normals
    def face_normals(self):
        tri = self.vertices[self.faces]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        area = np.linalg.norm(n, axis=1, keepdims=True)
        area[area < 1e-30] = 1.0
        return n / area

    def update_normals(self):
        if len(self.faces) == 0 or len(self.vertices) == 0:
            self.normals = np.zeros_like(self.vertices)
            return self.normals
        tri = self.vertices[self.faces]
        fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])  # area-weighted
        acc = np.zeros_like(self.vertices)
        for k in range(3):
            np.add.at(acc, self.faces[:, k], fn)
        ln = np.linalg.norm(acc, axis=1, keepdims=True)
        ln[ln < 1e-30] = 1.0
        self.normals = acc / ln
        return self.normals

    def face_areas(self):
        tri = self.vertices[self.faces]
        return 0.5 * np.linalg.norm(
            np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)

    def unindex(self):
        """Explode to per-face-corner vertices (needed for hard-edge UVs)."""
        fv = self.vertices[self.faces]
        n = len(self.faces)
        m = Mesh(fv.reshape(-1, 3),
                 np.arange(3 * n, dtype=np.int64).reshape(-1, 3), self.name)
        if self.colors is not None:
            m.colors = self.colors[self.faces].reshape(-1, 3)
        m.update_normals()
        return m


# ===================================================================== primitives
def ensure_outward(m):
    """Guarantee outward winding for closed meshes (positive signed volume)."""
    if len(m.faces) == 0:
        return m
    tri = m.vertices[m.faces]
    vol6 = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2]))
    if float(vol6.sum()) < 0:
        m.faces = m.faces[:, ::-1].copy()
        m.update_normals()
    return m


def make_box(sx=1.0, sy=1.0, sz=1.0):
    x, y, z = sx / 2.0, sy / 2.0, sz / 2.0
    v = []
    f = []

    def quad(a, b, c, d):
        base = len(v)
        v.extend([a, b, c, d])
        f.extend([[base, base + 1, base + 2], [base, base + 2, base + 3]])

    quad((-x, -y, +z), (+x, -y, +z), (+x, +y, +z), (-x, +y, +z))  # +Z
    quad((+x, -y, -z), (-x, -y, -z), (-x, +y, -z), (+x, +y, -z))  # -Z
    quad((+x, -y, +z), (+x, -y, -z), (+x, +y, -z), (+x, +y, +z))  # +X
    quad((-x, -y, -z), (-x, -y, +z), (-x, +y, +z), (-x, +y, -z))  # -X
    quad((-x, +y, +z), (+x, +y, +z), (+x, +y, -z), (-x, +y, -z))  # +Y
    quad((-x, -y, -z), (+x, -y, -z), (+x, -y, +z), (-x, -y, +z))  # -Y
    return Mesh(np.array(v, float), np.array(f, np.int64), "box")


def make_sphere(radius=1.0, rings=12, segments=24):
    rings, segments = max(3, int(rings)), max(3, int(segments))
    v, f = [], []
    v.append([0, radius, 0])
    for i in range(1, rings):
        phi = np.pi * i / rings
        for j in range(segments):
            theta = 2 * np.pi * j / segments
            v.append([radius * np.sin(phi) * np.cos(theta),
                      radius * np.cos(phi),
                      radius * np.sin(phi) * np.sin(theta)])
    v.append([0, -radius, 0])
    top, bot = 0, len(v) - 1
    for j in range(segments):
        f.append([top, 1 + (j + 1) % segments, 1 + j])
    for i in range(rings - 2):
        r0 = 1 + i * segments
        r1 = r0 + segments
        for j in range(segments):
            j2 = (j + 1) % segments
            f.append([r0 + j, r0 + j2, r1 + j2])
            f.append([r0 + j, r1 + j2, r1 + j])
    rb = 1 + (rings - 2) * segments
    for j in range(segments):
        f.append([rb + j, rb + (j + 1) % segments, bot])
    return Mesh(np.array(v, float), np.array(f, np.int64), "sphere")


def make_cylinder(radius=1.0, height=1.0, segments=24, caps=True):
    segments = max(3, int(segments))
    v, f = [], []
    h2 = height / 2.0
    for i in range(segments):
        t = 2 * np.pi * i / segments
        c, s = np.cos(t), np.sin(t)
        v.append([radius * c, -h2, radius * s])
        v.append([radius * c, +h2, radius * s])
    for i in range(segments):
        j = (i + 1) % segments
        f.append([2 * i, 2 * j, 2 * j + 1])
        f.append([2 * i, 2 * j + 1, 2 * i + 1])
    if caps:
        bc = len(v); v.append([0, -h2, 0])
        tc = len(v); v.append([0, +h2, 0])
        for i in range(segments):
            j = (i + 1) % segments
            f.append([bc, 2 * j, 2 * i])
            f.append([tc, 2 * i + 1, 2 * j + 1])
    return ensure_outward(Mesh(np.array(v, float), np.array(f, np.int64), "cylinder"))


def make_cone(radius=1.0, height=1.0, segments=24, caps=True):
    segments = max(3, int(segments))
    v, f = [], []
    v.append([0, height / 2.0, 0])  # apex
    ring = []
    for i in range(segments):
        t = 2 * np.pi * i / segments
        p = [radius * np.cos(t), -height / 2.0, radius * np.sin(t)]
        ring.append(len(v))
        v.append(p)
    for i in range(segments):
        j = (i + 1) % segments
        f.append([0, ring[j], ring[i]])
    if caps:
        bc = len(v); v.append([0, -height / 2.0, 0])
        for i in range(segments):
            j = (i + 1) % segments
            f.append([bc, ring[i], ring[j]])
    return ensure_outward(Mesh(np.array(v, float), np.array(f, np.int64), "cone"))


def make_plane(size=1.0, subdivisions=1):
    return make_grid(int(subdivisions), int(subdivisions), size, size)


def make_grid(nx=4, nz=4, sx=1.0, sz=1.0):
    nx, nz = max(1, int(nx)), max(1, int(nz))
    v = []
    for j in range(nz + 1):
        for i in range(nx + 1):
            v.append([sx * (i / nx - 0.5), 0.0, sz * (j / nz - 0.5)])
    f = []
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            b = a + 1
            c = a + nx + 2
            d = a + nx + 1
            f.append([a, b, c])
            f.append([a, c, d])
    return Mesh(np.array(v, float), np.array(f, np.int64), "plane")


def make_torus(radius=1.0, tube=0.35, radial=24, tubular=12):
    radial, tubular = max(3, int(radial)), max(3, int(tubular))
    v, f = [], []
    for i in range(radial):
        u = 2 * np.pi * i / radial
        cu, su = np.cos(u), np.sin(u)
        for j in range(tubular):
            t = 2 * np.pi * j / tubular
            ct, st = np.cos(t), np.sin(t)
            v.append([(radius + tube * ct) * cu, tube * st, (radius + tube * ct) * su])
    for i in range(radial):
        for j in range(tubular):
            i2, j2 = (i + 1) % radial, (j + 1) % tubular
            a = i * tubular + j
            b = i2 * tubular + j
            c = i2 * tubular + j2
            d = i * tubular + j2
            f.append([a, b, c])
            f.append([a, c, d])
    return ensure_outward(Mesh(np.array(v, float), np.array(f, np.int64), "torus"))


def make_capsule(radius=0.5, height=1.0, rings=6, segments=16):
    """Rings per hemisphere (excluding equator/poles). Built as ordered rings
    so winding matches the sphere convention everywhere."""
    rings, segments = max(2, int(rings)), max(3, int(segments))
    h2 = max(0.0, height) / 2.0
    v, f = [], []
    ring_ids = []  # list of lists of vertex ids; None for poles

    def add_ring(theta):  # theta from +Y pole: 0..pi
        ids = []
        st, ct = np.sin(theta), np.cos(theta)
        for j in range(segments):
            phi = 2 * np.pi * j / segments
            ids.append(len(v))
            v.append([radius * st * np.cos(phi),
                      (h2 if theta <= np.pi / 2 else -h2) + radius * ct
                      if abs(theta - np.pi / 2) > 1e-9 else 0.0,
                      radius * st * np.sin(phi)])
        ring_ids.append(ids)

    top_pole = len(v)
    v.append([0, h2 + radius, 0])
    for i in range(1, rings):
        add_ring((np.pi / 2) * i / rings)
    add_ring(np.pi / 2)          # cylinder top ring
    add_ring(np.pi / 2 + 1e-9)   # cylinder bottom ring (same theta, other y)
    # fix cylinder ring y values explicitly
    n_seg = segments
    for vid in ring_ids[-2]:
        v[vid][1] = h2
    for vid in ring_ids[-1]:
        v[vid][1] = -h2
    for i in range(1, rings):
        add_ring(np.pi / 2 + (np.pi / 2) * i / rings)
    bot_pole = len(v)
    v.append([0, -h2 - radius, 0])

    def band(r0, r1):
        for j in range(segments):
            j2 = (j + 1) % segments
            f.append([r0[j], r0[j2], r1[j2]])
            f.append([r0[j], r1[j2], r1[j]])

    for j in range(segments):  # top pole fan
        f.append([top_pole, ring_ids[0][(j + 1) % segments], ring_ids[0][j]])
    for i in range(len(ring_ids) - 1):
        band(ring_ids[i], ring_ids[i + 1])
    lb = ring_ids[-1]
    for j in range(segments):  # bottom pole fan
        f.append([lb[j], lb[(j + 1) % segments], bot_pole])
    return Mesh(np.array(v, float), np.array(f, np.int64), "capsule")


PRIMITIVES = {
    "box": make_box, "cube": make_box, "sphere": make_sphere,
    "cylinder": make_cylinder, "cone": make_cone, "plane": make_plane,
    "grid": make_grid, "torus": make_torus, "capsule": make_capsule,
}


# ===================================================================== ops
def translate(m, x, y, z):
    m.vertices = m.vertices + np.array([x, y, z], float)
    return m


def scale_mesh(m, sx, sy, sz):
    m.vertices = m.vertices * np.array([sx, sy, sz], float)
    m.update_normals()
    return m


def transform_mesh(m, mat):
    from .math3d import transform_points
    m.vertices = transform_points(mat, m.vertices)
    m.update_normals()
    return m


def subdivide(m, levels=1):
    """Midpoint subdivision (loop-ish positions, no smoothing)."""
    for _ in range(max(0, int(levels))):
        verts = [tuple(v) for v in m.vertices]
        idx = {v: i for i, v in enumerate(verts)}
        edge_cache = {}
        new_faces = []

        def mid(a, b):
            key = (a, b) if a < b else (b, a)
            if key not in edge_cache:
                p = ((np.array(verts[a]) + np.array(verts[b])) / 2.0)
                edge_cache[key] = len(verts)
                verts.append(tuple(p))
            return edge_cache[key]

        for a, b, c in m.faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new_faces.extend([[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]])
        m.vertices = np.array(verts, float)
        m.faces = np.array(new_faces, np.int64)
    m.update_normals()
    return m


def mirror(m, axis="x"):
    ax = {"x": 0, "y": 1, "z": 2}[axis]
    m.vertices[:, ax] *= -1.0
    m.faces = m.faces[:, ::-1].copy()  # flip winding
    m.update_normals()
    return m


def twist(m, axis="y", degrees_per_unit=45.0):
    ax = {"x": 0, "y": 1, "z": 2}[axis]
    others = [i for i in range(3) if i != ax]
    for i, p in enumerate(m.vertices):
        ang = np.radians(degrees_per_unit * p[ax])
        c, s = np.cos(ang), np.sin(ang)
        u, w = p[others[0]], p[others[1]]
        m.vertices[i, others[0]] = c * u - s * w
        m.vertices[i, others[1]] = s * u + c * w
    m.update_normals()
    return m


def taper(m, axis="y", factor=0.5):
    """Scale cross-section along axis: scale(t) = 1 + (factor-1)*t, t in [0,1]."""
    ax = {"x": 0, "y": 1, "z": 2}[axis]
    lo, hi = m.vertices[:, ax].min(), m.vertices[:, ax].max()
    span = (hi - lo) or 1.0
    t = (m.vertices[:, ax] - lo) / span
    s = 1.0 + (factor - 1.0) * t
    for i in range(3):
        if i != ax:
            m.vertices[:, i] *= s
    m.update_normals()
    return m


def noise_displace(m, amplitude=0.05, seed=0, along_normals=True):
    rng = np.random.default_rng(seed)
    d = rng.normal(0.0, amplitude, len(m.vertices))
    if along_normals:
        m.vertices = m.vertices + m.normals * d[:, None]
    else:
        m.vertices = m.vertices + rng.normal(0.0, amplitude, m.vertices.shape)
    m.update_normals()
    return m


def laplacian_smooth(m, iterations=1, factor=0.5):
    for _ in range(max(0, int(iterations))):
        acc = np.zeros_like(m.vertices)
        cnt = np.zeros(len(m.vertices))
        for k in range(3):
            np.add.at(acc, m.faces[:, k], m.vertices[m.faces[:, (k + 1) % 3]])
            np.add.at(acc, m.faces[:, k], m.vertices[m.faces[:, (k + 2) % 3]])
            np.add.at(cnt, m.faces[:, k], 2.0)
        cnt[cnt == 0] = 1.0
        target = acc / cnt[:, None]
        m.vertices = m.vertices + factor * (target - m.vertices)
    m.update_normals()
    return m


def weld_vertices(m, epsilon=1e-6):
    rounded = np.round(m.vertices / epsilon) * epsilon
    _, inv = np.unique(np.round(rounded, 9), axis=0, return_inverse=True)
    new_count = inv.max() + 1
    acc = np.zeros((new_count, 3))
    cnt = np.zeros(new_count)
    np.add.at(acc, inv, m.vertices)
    np.add.at(cnt, inv, 1.0)
    m.vertices = acc / cnt[:, None]
    m.faces = inv[m.faces]
    keep = (m.faces[:, 0] != m.faces[:, 1]) & (m.faces[:, 1] != m.faces[:, 2]) & \
           (m.faces[:, 0] != m.faces[:, 2])
    m.faces = m.faces[keep]
    m.uvs = None
    m.update_normals()
    return m


def merge_meshes(meshes, name="merged"):
    meshes = [m for m in meshes if m is not None]
    if not meshes:
        return make_box(0.001, 0.001, 0.001)
    verts, faces = [], []
    offset = 0
    for m in meshes:
        verts.append(m.vertices)
        faces.append(m.faces + offset)
        offset += len(m.vertices)
    out = Mesh(np.vstack(verts), np.vstack(faces), name)
    return out


def lathe(points, segments=24):
    """Revolve a 2D profile [(x, y), ...] around Y axis. Great for goblets, columns."""
    segments = max(3, int(segments))
    pts = np.asarray(points, float)
    v, f = [], []
    n = len(pts)
    for j in range(segments):
        t = 2 * np.pi * j / segments
        c, s = np.cos(t), np.sin(t)
        for x, y in pts:
            v.append([x * c, y, x * s])
    for j in range(segments):
        j2 = (j + 1) % segments
        for i in range(n - 1):
            a, b = j * n + i, j * n + i + 1
            c, d = j2 * n + i + 1, j2 * n + i
            f.append([a, b, c])
            f.append([a, c, d])
    return Mesh(np.array(v, float), np.array(f, np.int64), "lathe")
