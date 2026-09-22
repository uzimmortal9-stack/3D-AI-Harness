"""Forge3D base-version test suite. Run: python -m forge3d.cli selftest"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import forge3d as f3
from forge3d import audio, baker, doctor, exporter, pngio
from forge3d.anim import Animator, Track
from forge3d.forge_lang import (ForgeLangError, ForgeSyntaxError, Interpreter,
                                parse)
from forge3d.inputmgr import InputManager
from forge3d.material import Material, hex_to_rgb, make_texture
from forge3d.mesh import (Mesh, make_box, make_capsule, make_cone,
                          make_cylinder, make_plane, make_sphere, make_torus,
                          merge_meshes, mirror, noise_displace, subdivide,
                          taper, twist, weld_vertices)
from forge3d.physics import Body, PhysicsWorld
from forge3d.raster import render_scene
from forge3d.scene import Node, Scene
from forge3d.uv import unwrap


class TestGeometry(unittest.TestCase):
    PRIMS = [("box", make_box()), ("sphere", make_sphere(1, 8, 16)),
             ("cylinder", make_cylinder()), ("cone", make_cone()),
             ("torus", make_torus()), ("capsule", make_capsule())]

    def test_primitives_watertight(self):
        for name, m in self.PRIMS:
            r = doctor.examine_mesh(m, name)
            self.assertTrue(r["watertight"], f"{name} not watertight: {r['issues']}")

    def test_subdivide_quadruples(self):
        m = make_box()
        n0 = m.face_count
        subdivide(m, 1)
        self.assertEqual(m.face_count, n0 * 4)

    def test_mirror_weld(self):
        m = make_box()
        mirror(m, "x")
        r = doctor.examine_mesh(m)
        self.assertTrue(r["watertight"])
        w = weld_vertices(m.copy(), 1e-6)
        self.assertEqual(w.vertex_count, 8)

    def test_deformers_finite(self):
        m = make_sphere(1, 8, 16)
        twist(m, "y", 60); taper(m, "y", 0.5)
        noise_displace(m, 0.05, seed=3)
        self.assertTrue(np.isfinite(m.vertices).all())

    def test_merge(self):
        m = merge_meshes([make_box(), make_sphere(0.5, 6, 12)])
        self.assertEqual(m.face_count, 12 + make_sphere(0.5, 6, 12).face_count)

    def test_uv_unwrap_range(self):
        for method in ("box", "planar", "cylinder"):
            u = unwrap(make_box(), method)
            self.assertTrue(np.all(u.uvs >= 0) and np.all(u.uvs <= 1))

    def test_textures(self):
        for kind in ("checker", "stripes", "noise", "brick", "gradient"):
            t = make_texture(kind, 32)
            self.assertEqual(t.shape, (32, 32, 3))
            self.assertEqual(t.dtype, np.uint8)

    def test_colors_hex(self):
        c = hex_to_rgb("#ff0000")
        self.assertAlmostEqual(c[0], 1.0)
        self.assertAlmostEqual(c[1], 0.0)


class TestDoctor(unittest.TestCase):
    def test_flags_degenerate(self):
        m = make_box()
        m.vertices[1] = m.vertices[0]  # zero-area triangles
        r = doctor.examine_mesh(m)
        codes = [i[1] for i in r["issues"]]
        self.assertIn("DEGENERATE_TRIANGLES", codes)

    def test_flags_nan(self):
        m = make_box()
        m.vertices[0, 0] = float("nan")
        r = doctor.examine_mesh(m)
        codes = [i[1] for i in r["issues"]]
        self.assertIn("NON_FINITE_VERTICES", codes)

    def test_scene_score(self):
        s = Scene()
        n = Node("a", "mesh"); n.mesh = make_box(); s.add_node(n)
        rep = doctor.examine_scene(s)
        self.assertGreaterEqual(rep["score"], 80)


class TestRender(unittest.TestCase):
    def _scene(self):
        s = Scene("t")
        n = Node("m", "mesh"); n.mesh = make_sphere(0.8, 10, 18)
        n.position = np.array([0.0, 0.8, 0.0])
        n.material = Material("red", (0.9, 0.2, 0.2))
        s.add_node(n)
        return s

    def test_render_produces_image(self):
        img = render_scene(self._scene(), 128, 96)
        self.assertEqual(img.shape, (96, 128, 3))
        self.assertGreater(img.mean(), 5)

    def test_png_roundtrip(self):
        img = render_scene(self._scene(), 64, 48)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.png")
            pngio.write_png(p, img)
            back = pngio.read_png(p)
        self.assertTrue(np.array_equal(back, img))


class TestExport(unittest.TestCase):
    def _scene(self):
        s = Scene("t")
        n = Node("m", "mesh"); n.mesh = make_box(); n.material = Material("mm")
        s.add_node(n)
        return s

    def test_obj(self):
        with tempfile.TemporaryDirectory() as d:
            out = exporter.export_obj(self._scene(), os.path.join(d, "a.obj"))
            txt = open(out[0]).read()
            self.assertIn("v ", txt)
            self.assertIn("f ", txt)
            self.assertTrue(os.path.exists(out[1]))

    def test_stl_binary(self):
        with tempfile.TemporaryDirectory() as d:
            out = exporter.export_stl(self._scene(), os.path.join(d, "a.stl"))
            size = os.path.getsize(out[0])
            self.assertEqual(size, 84 + 12 * 50)

    def test_gltf(self):
        with tempfile.TemporaryDirectory() as d:
            out = exporter.export_gltf(self._scene(), os.path.join(d, "a.gltf"))
            g = json.load(open(out[0]))
            self.assertEqual(g["asset"]["version"], "2.0")
            self.assertGreaterEqual(len(g["meshes"]), 1)

    def test_json_roundtrip(self):
        s = self._scene()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            exporter.export_scene_json(s, p)
            s2 = Scene.from_dict(json.load(open(p)))
            self.assertEqual(len(s2.mesh_nodes()), 1)


class TestLanguage(unittest.TestCase):
    def test_parse_error_line(self):
        with self.assertRaises(ForgeSyntaxError):
            parse("mesh X {\n primitive box\n", "t")

    def test_unknown_primitive(self):
        with self.assertRaises(ForgeLangError):
            Interpreter(".").run_text("mesh X { primitive blob }")

    def test_build_scene(self):
        src = """
        material M { base_color #33aa55 ; roughness 0.5 }
        mesh A { primitive sphere ; radius 0.5 ; segments 12 ; rings 8 ;
                 position 0 1 0 ; material M ; subdivide 1 ; uv box }
        camera C { position 4 3 5 ; look_at 0 1 0 }
        light L { type sun ; intensity 1.0 }
        """
        scene, rep = Interpreter(".").run_text(src)
        self.assertEqual(len(scene.mesh_nodes()), 1)
        m = scene.mesh_nodes()[0].mesh
        self.assertEqual(m.face_count, make_sphere(0.5, 8, 12).face_count * 4)
        self.assertIsNotNone(m.uvs)
        self.assertEqual(scene.mesh_nodes()[0].material.name, "M")

    def test_material_before_use(self):
        with self.assertRaises(ForgeLangError):
            Interpreter(".").run_text("mesh A { primitive box ; material Nope }")


class TestPhysics(unittest.TestCase):
    def test_ball_falls_and_rests(self):
        w = PhysicsWorld(-9.81)
        w.add(Body("g", "plane", static=True))
        b = Body("b", "sphere", mass=1, radius=0.5)
        b.position = np.array([0, 5.0, 0])
        w.add(b)
        for _ in range(240):
            w.step(1 / 60)
        self.assertLess(abs(b.position[1] - 0.5), 0.05)

    def test_two_balls_collide(self):
        w = PhysicsWorld(-9.81)
        a = Body("a", "sphere", mass=1, radius=0.5)
        a.position = np.array([0, 2, 0]); a.velocity = np.array([2, 0, 0])
        b = Body("b", "sphere", mass=1, radius=0.5)
        b.position = np.array([2, 2, 0])
        w.add(a); w.add(b)
        for _ in range(120):
            w.step(1 / 60)
        self.assertGreater(b.position[0], 2.0)  # momentum transferred


class TestAnim(unittest.TestCase):
    def test_track_interpolation(self):
        s = Scene()
        n = Node("n", "mesh"); n.mesh = make_box(); s.add_node(n)
        an = Animator()
        t = an.add_track(Track("n", "position", [0, 1], [[0, 0, 0], [2, 0, 0]]))
        an.apply(s, 0.5)
        self.assertAlmostEqual(n.position[0], 1.0)

    def test_skinning(self):
        from forge3d.anim import Skeleton, rigid_bind, skin_pose
        sk = Skeleton()
        sk.add_bone("root")
        sk.add_bone("top", "root", (0, 1, 0))
        m = make_sphere(0.5, 6, 10)
        wts = rigid_bind(m, sk)
        posed = skin_pose(m, sk, wts, {"top": (0, 0, 45)})
        self.assertEqual(posed.vertex_count, m.vertex_count)


class TestAudio(unittest.TestCase):
    def test_synth_wav(self):
        s = audio.synth(440, 0.2, "sine")
        self.assertEqual(len(s), int(22050 * 0.2))
        with tempfile.TemporaryDirectory() as d:
            p = audio.write_wav(os.path.join(d, "t.wav"), s)
            back, rate = audio.read_wav(p)
            self.assertEqual(rate, 22050)
            self.assertGreater(len(back), 0)

    def test_mix(self):
        a = audio.synth(440, 0.1); b = audio.synth(880, 0.1)
        m = audio.mix([(a, 0.0), (b, 0.05)])
        self.assertGreater(len(m), len(a))


class TestInput(unittest.TestCase):
    def test_actions(self):
        im = InputManager()
        im.key_down("w")
        self.assertTrue(im.is_down("forward"))
        self.assertTrue(im.was_pressed("forward"))
        im.end_frame()
        self.assertFalse(im.was_pressed("forward"))
        im.key_up("w")
        self.assertFalse(im.is_down("forward"))


class TestBaker(unittest.TestCase):
    def test_ao_bake(self):
        m = make_sphere(0.5, 6, 10)
        baker.bake_vertex_ao(m, rays=4)
        self.assertIsNotNone(m.colors)
        self.assertTrue(np.all(m.colors >= 0) and np.all(m.colors <= 1))

    def test_shadow_bake(self):
        s = Scene()
        n = Node("m", "mesh"); n.mesh = make_box(); s.add_node(n)
        n.position = np.array([0.0, 1.0, 0.0])
        floor = Node("f", "mesh"); floor.mesh = make_plane(4, 2); s.add_node(floor)
        baker.bake_sun_shadow(s)
        self.assertIsNotNone(n.mesh.colors)


class TestEndToEnd(unittest.TestCase):
    def test_mini_game(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        interp = Interpreter(here)
        scene, rep = interp.run_file(os.path.join(here, "examples/mini_game.forge"))
        self.assertGreaterEqual(len(scene.mesh_nodes()), 6)
        from forge3d.runtime import run_headless
        api, log = run_headless(scene, rep["scripts"], 2.0, 30, quiet=True)
        self.assertAlmostEqual(api.time, 60 / 30, delta=0.2)


if __name__ == "__main__":
    unittest.main()
