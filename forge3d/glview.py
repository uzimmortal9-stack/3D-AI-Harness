"""Forge3D interactive OpenGL viewport (legacy GL for maximum driver compat).

Optional dependency stack: `pip install glfw PyOpenGL`. The headless software
renderer is the fallback and what agents use; this is for humans.

Controls: LMB drag orbit, wheel zoom, MMB pan, F5 reload, F9 screenshot,
ESC close.
"""
import os

import numpy as np

try:
    import glfw
    from OpenGL.GL import (glBegin, glClear, glClearColor, glColor3f, glEnd,
                           glLightfv, glEnable, glLoadIdentity, glMatrixMode,
                           glMultMatrixf, glNormal3f, glPopMatrix, glPushMatrix,
                           glVertex3f, glViewport, GL_AMBIENT, GL_COLOR_BUFFER_BIT,
                           GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_DIFFUSE,
                           GL_LIGHT0, GL_LIGHTING, GL_MODELVIEW, GL_POSITION,
                           GL_PROJECTION, GL_SPECULAR, GL_TRIANGLES)
    HAVE_GL = True
except ImportError:  # pragma: no cover
    HAVE_GL = False

from .math3d import look_at, perspective


class GLViewer:
    def __init__(self, scene, width=1280, height=800, title="Forge3D"):
        if not HAVE_GL:
            raise RuntimeError(
                "Interactive mode needs `pip install glfw PyOpenGL`. "
                "Use `render`/`observe` commands for headless output.")
        if not glfw.init():
            raise RuntimeError("GLFW init failed")
        glfw.window_hint(glfw.SAMPLES, 4)
        self.win = glfw.create_window(width, height, title, None, None)
        if not self.win:
            glfw.terminate()
            raise RuntimeError("window creation failed")
        glfw.make_context_current(self.win)
        glfw.swap_interval(1)
        self.scene = scene
        self.input = None
        self.alive = True
        self.yaw, self.pitch, self.dist = 45.0, 22.0, 12.0
        self.target = np.array([0.0, 1.0, 0.0])
        lo, hi = scene.bounds()
        if (hi - lo).max() > 0:
            self.target = (lo + hi) / 2
            self.dist = float(np.linalg.norm(hi - lo)) * 1.2
        self._last_mouse = None
        self.reload_cb = None
        glfw.set_mouse_button_callback(self.win, self._on_mouse)
        glfw.set_scroll_callback(self.win, self._on_scroll)
        glfw.set_key_callback(self.win, self._on_key)

    # ------------------------------------------------------------------ events
    def _on_mouse(self, win, button, action, mods):
        pass  # orbit handled per-frame from mouse state

    def _on_scroll(self, win, dx, dy):
        self.dist = max(1.0, self.dist * (1.0 - 0.1 * dy))

    def _on_key(self, win, key, sc, action, mods):
        if action == glfw.RELEASE:
            return
        if key == glfw.KEY_ESCAPE:
            self.alive = False
        elif key == glfw.KEY_F5 and self.reload_cb:
            self.reload_cb()
        elif key == glfw.KEY_F9:
            self.screenshot("forge3d_screenshot.png")

    def poll_events(self):
        glfw.poll_events()
        if glfw.window_should_close(self.win):
            self.alive = False
        if not self.alive or self.input is None:
            return
        rot = 0.0
        if glfw.get_mouse_button(self.win, glfw.MOUSE_BUTTON_LEFT) == glfw.PRESS:
            self.yaw += 0.4
        if glfw.get_mouse_button(self.win, glfw.MOUSE_BUTTON_RIGHT) == glfw.PRESS:
            self.pitch = max(-5, min(85, self.pitch + 0.4))
        if self.input.is_down("forward"):
            self.dist = max(1.0, self.dist - 0.2)
        if self.input.is_down("back"):
            self.dist = min(80.0, self.dist + 0.2)

    # ------------------------------------------------------------------ draw
    def draw(self, dt):
        w, h = glfw.get_framebuffer_size(self.win)
        glViewport(0, 0, w, h)
        bg = self.scene.background
        glClearColor(bg[0] * 0.8, bg[1] * 0.8, bg[2] * 0.8, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        import ctypes
        proj = perspective(50, w / max(1, h), 0.05, 500.0)
        _load(proj)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        from .math3d import orbit_camera
        eye = orbit_camera(self.target, self.yaw, self.pitch, self.dist)
        _load(look_at(eye, self.target))

        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        sun = self.scene.default_light()
        d = np.asarray(sun.extra.get("direction", [-0.45, -1, -0.35]), float)
        glLightfv(GL_LIGHT0, GL_POSITION, np.array([d[0], d[1], d[2], 0.0], "f"))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, np.array([1, 0.97, 0.9, 1], "f"))
        glLightfv(GL_LIGHT0, GL_SPECULAR, np.array([0.3, 0.3, 0.3, 1], "f"))
        glLightfv(GL_LIGHT0, GL_AMBIENT, np.array([0.25, 0.25, 0.28, 1], "f"))

        for node in self.scene.mesh_nodes():
            if not node.visible:
                continue
            c = node.material.base_color if node.material else np.array([0.8] * 3)
            glPushMatrix()
            m = self.scene.world_matrix(node)
            _load(m, multiply=True)
            glColor3f(c[0], c[1], c[2])
            mesh = node.mesh
            glBegin(GL_TRIANGLES)
            if mesh.normals is not None:
                for f in mesh.faces:
                    for vi in f:
                        nrm = mesh.normals[vi]
                        glNormal3f(nrm[0], nrm[1], nrm[2])
                        v = mesh.vertices[vi]
                        glVertex3f(v[0], v[1], v[2])
            glEnd()
            glPopMatrix()

        glDisable(GL_LIGHTING)
        glfw.swap_buffers(self.win)

    def screenshot(self, path):
        from OpenGL.GL import glReadPixels
        from .pngio import write_png
        w, h = glfw.get_framebuffer_size(self.win)
        buf = glReadPixels(0, 0, w, h, 6408, 5121)
        img = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, :3][::-1]
        write_png(path, img)
        print(f"[forge3d] screenshot -> {path}")

    def close(self):
        try:
            glfw.destroy_window(self.win)
            glfw.terminate()
        except Exception:
            pass


def _load(m, multiply=False):
    import ctypes
    arr = (ctypes.c_float * 16)(*m.T.ravel())
    if multiply:
        glMultMatrixf(arr)
    else:
        glLoadMatrixf(arr)
