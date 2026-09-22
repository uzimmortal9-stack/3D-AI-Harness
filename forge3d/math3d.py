"""Forge3D math core — 4x4 matrices (column-vector convention: p' = M @ [x,y,z,1])."""
import math
import numpy as np


def vec3(x=0.0, y=0.0, z=0.0):
    return np.array([x, y, z], dtype=float)


def normalize(v):
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        return np.array([0.0, 0.0, 1.0])
    return v / n


def mat4_identity():
    return np.eye(4, dtype=float)


def mat4_translation(x, y, z):
    m = np.eye(4)
    m[0:3, 3] = [x, y, z]
    return m


def mat4_scale(sx, sy, sz):
    m = np.eye(4)
    m[0, 0], m[1, 1], m[2, 2] = sx, sy, sz
    return m


def mat4_rotation_x(deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], float)


def mat4_rotation_y(deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], float)


def mat4_rotation_z(deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], float)


def mat4_from_euler(rx, ry, rz):
    """Degrees. Order: Rz @ Ry @ Rx (matches Blender-ish intuition)."""
    return mat4_rotation_z(rz) @ mat4_rotation_y(ry) @ mat4_rotation_x(rx)


def mat4_compose(position=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
    p = np.asarray(position, float)
    s = np.asarray(scale, float)
    m = mat4_from_euler(*rotation)
    m[0:3, 0:3] = m[0:3, 0:3] * s[None, :]
    m[0:3, 3] = p
    return m


def transform_points(m, pts):
    pts = np.asarray(pts, float)
    if pts.size == 0:
        return pts.copy()
    return pts @ m[0:3, 0:3].T + m[0:3, 3]


def transform_directions(m, dirs):
    dirs = np.asarray(dirs, float)
    if dirs.size == 0:
        return dirs.copy()
    return dirs @ m[0:3, 0:3].T


def look_at(eye, target, up=(0, 1, 0)):
    """View matrix (world -> camera space, camera looks down -Z)."""
    eye, target, up = np.asarray(eye, float), np.asarray(target, float), np.asarray(up, float)
    f = normalize(target - eye)
    s = normalize(np.cross(f, up))
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, 0:3] = s
    m[1, 0:3] = u
    m[2, 0:3] = -f
    m[0:3, 3] = [-np.dot(s, eye), -np.dot(u, eye), np.dot(f, eye)]
    return m


def perspective(fov_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4))
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def orbit_camera(target, yaw_deg, pitch_deg, distance):
    """Eye position orbiting around target. Used by GUI and multi-view renders."""
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    pitch = max(-1.55, min(1.55, pitch))
    off = np.array([
        math.cos(pitch) * math.sin(yaw),
        math.sin(pitch),
        math.cos(pitch) * math.cos(yaw),
    ]) * distance
    return np.asarray(target, float) + off
