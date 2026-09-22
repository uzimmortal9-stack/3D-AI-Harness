"""Forge3D scene graph & asset management."""
import numpy as np

from .math3d import mat4_compose
from .material import Material, DEFAULT_MATERIAL


class Node:
    __slots__ = ("name", "kind", "parent", "children", "position", "rotation",
                 "scale", "mesh", "material", "extra", "visible")

    def __init__(self, name, kind="mesh"):
        self.name = name
        self.kind = kind          # mesh | camera | light | sound | group | empty
        self.parent = None
        self.children = []
        self.position = np.zeros(3)
        self.rotation = np.zeros(3)   # degrees XYZ
        self.scale = np.ones(3)
        self.mesh = None              # Mesh
        self.material = None          # Material
        self.extra = {}               # camera/light/sound/body/script payload
        self.visible = True

    def local_matrix(self):
        return mat4_compose(self.position, self.rotation, self.scale)


class Scene:
    def __init__(self, name="scene"):
        self.name = name
        self.nodes = []
        self.materials = {}
        self.background = np.array([0.07, 0.08, 0.10])
        self.ambient = 0.30
        self.active_camera = None
        self.gravity = -9.81
        self.metadata = {}

    # ------------------------------------------------------------- node mgmt
    def add_node(self, node, parent=None):
        if parent is not None:
            node.parent = parent
            parent.children.append(node)
        self.nodes.append(node)
        return node

    def remove_node(self, node):
        if node.parent:
            node.parent.children.remove(node)
        self.nodes.remove(node)

    def get(self, name):
        for n in self.nodes:
            if n.name == name:
                return n
        return None

    def unique_name(self, base):
        names = {n.name for n in self.nodes}
        if base not in names:
            return base
        i = 1
        while f"{base}.{i:03d}" in names:
            i += 1
        return f"{base}.{i:03d}"

    def mesh_nodes(self):
        return [n for n in self.nodes if n.kind == "mesh" and n.mesh is not None]

    def cameras(self):
        return [n for n in self.nodes if n.kind == "camera"]

    def lights(self):
        return [n for n in self.nodes if n.kind == "light"]

    def get_material(self, name):
        return self.materials.get(name)

    def ensure_material(self, mat):
        self.materials[mat.name] = mat
        return mat

    def world_matrix(self, node):
        stack = []
        n = node
        while n is not None:
            stack.append(n)
            n = n.parent
        m = np.eye(4)
        for n in reversed(stack):
            m = m @ n.local_matrix()
        return m

    def default_camera(self):
        cams = self.cameras()
        if self.active_camera:
            for c in cams:
                if c.name == self.active_camera:
                    return c
        if cams:
            return cams[0]
        cam = Node("AutoCamera", "camera")
        cam.position = np.array([6.0, 4.5, 8.0])
        cam.extra = {"fov": 50.0, "look_at": np.array([0.0, 0.8, 0.0])}
        self.add_node(cam)
        return cam

    def default_light(self):
        ls = self.lights()
        if ls:
            return ls[0]
        sun = Node("AutoSun", "light")
        sun.extra = {"type": "sun", "direction": np.array([-0.45, -1.0, -0.35]),
                     "color": np.array([1.0, 0.97, 0.9]), "intensity": 1.15}
        self.add_node(sun)
        return sun

    def bounds(self):
        pts = []
        for n in self.mesh_nodes():
            lo, hi = n.mesh.bounds()
            w = self.world_matrix(n)
            for c in [(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (lo[0], hi[1], lo[2]),
                      (hi[0], hi[1], lo[2]), (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]),
                      (lo[0], hi[1], hi[2]), (hi[0], hi[1], hi[2])]:
                p = w @ np.array([c[0], c[1], c[2], 1.0])
                pts.append(p[:3])
        if not pts:
            return np.zeros(3), np.zeros(3)
        pts = np.array(pts)
        return pts.min(axis=0), pts.max(axis=0)

    def stats(self):
        tris = sum(n.mesh.face_count for n in self.mesh_nodes())
        verts = sum(n.mesh.vertex_count for n in self.mesh_nodes())
        return {"nodes": len(self.nodes), "meshes": len(self.mesh_nodes()),
                "vertices": int(verts), "triangles": int(tris),
                "materials": len(self.materials),
                "cameras": len(self.cameras()), "lights": len(self.lights())}

    # ------------------------------------------------------------ serialization
    def to_dict(self):
        def node_d(n):
            d = {"name": n.name, "kind": n.kind,
                 "position": list(map(float, n.position)),
                 "rotation": list(map(float, n.rotation)),
                 "scale": list(map(float, n.scale)),
                 "visible": n.visible}
            if n.parent:
                d["parent"] = n.parent.name
            if n.material:
                d["material"] = n.material.name
            if n.mesh is not None:
                d["mesh"] = {"vertices": n.mesh.vertices.tolist(),
                             "faces": n.mesh.faces.tolist()}
                if n.mesh.uvs is not None:
                    d["mesh"]["uvs"] = n.mesh.uvs.tolist()
            d["extra"] = {k: (v.tolist() if isinstance(v, np.ndarray) else v)
                          for k, v in n.extra.items()}
            return d
        return {
            "name": self.name,
            "background": list(map(float, self.background)),
            "ambient": self.ambient,
            "gravity": self.gravity,
            "active_camera": self.active_camera,
            "materials": {k: m.to_dict() for k, m in self.materials.items()},
            "nodes": [node_d(n) for n in self.nodes],
        }

    @staticmethod
    def from_dict(d):
        from .mesh import Mesh
        s = Scene(d.get("name", "scene"))
        s.background = np.array(d.get("background", [0.07, 0.08, 0.10]), float)
        s.ambient = float(d.get("ambient", 0.3))
        s.gravity = float(d.get("gravity", -9.81))
        s.active_camera = d.get("active_camera")
        for mk, mv in d.get("materials", {}).items():
            from .material import hex_to_rgb
            m = Material(mk, hex_to_rgb(mv.get("base_color", "#cccccc")),
                         mv.get("metallic", 0), mv.get("roughness", 0.6),
                         mv.get("emission", 0))
            s.materials[mk] = m
        by_name = {}
        for nd in d.get("nodes", []):
            n = Node(nd["name"], nd.get("kind", "mesh"))
            n.position = np.array(nd.get("position", [0, 0, 0]), float)
            n.rotation = np.array(nd.get("rotation", [0, 0, 0]), float)
            n.scale = np.array(nd.get("scale", [1, 1, 1]), float)
            if "mesh" in nd:
                m = Mesh(np.array(nd["mesh"]["vertices"], float),
                         np.array(nd["mesh"]["faces"], np.int64), nd["name"])
                if "uvs" in nd["mesh"]:
                    m.uvs = np.array(nd["mesh"]["uvs"], float)
                n.mesh = m
            if "material" in nd and nd["material"] in s.materials:
                n.material = s.materials[nd["material"]]
            ex = nd.get("extra", {})
            for k, v in ex.items():
                n.extra[k] = np.array(v, float) if isinstance(v, list) else v
            by_name[n.name] = n
            s.add_node(n)
        for nd in d.get("nodes", []):
            if "parent" in nd and nd["parent"] in by_name:
                child = by_name[nd["name"]]
                child.parent = by_name[nd["parent"]]
                by_name[nd["parent"]].children.append(child)
        return s
