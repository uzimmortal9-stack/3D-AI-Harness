"""Forge3D materials, shading parameters, and procedural texture preparation."""
import numpy as np


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], float) / 255.0


def rgb_to_hex(c):
    c = np.clip(np.asarray(c, float), 0, 1)
    return "#%02x%02x%02x" % (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))


class Material:
    """Principled-lite shading model (maps to glTF PBR on export)."""

    def __init__(self, name="material", base_color=(0.8, 0.8, 0.8), metallic=0.0,
                 roughness=0.6, emission=0.0, texture=None, texture_file=None,
                 alpha=1.0):
        self.name = name
        self.base_color = np.asarray(base_color, float)
        self.metallic = float(metallic)
        self.roughness = float(roughness)
        self.emission = float(emission)
        self.alpha = float(alpha)
        self.texture = texture            # uint8 (H,W,3)
        self.texture_file = texture_file  # loaded lazily by renderer

    def to_dict(self):
        return {
            "name": self.name,
            "base_color": rgb_to_hex(self.base_color),
            "metallic": self.metallic,
            "roughness": self.roughness,
            "emission": self.emission,
            "alpha": self.alpha,
            "texture_file": self.texture_file,
        }


DEFAULT_MATERIAL = Material("default", (0.75, 0.75, 0.78), 0.0, 0.7)


# ------------------------------------------------------------ procedural textures
def make_texture(kind="checker", size=64, seed=0, color_a=(0.9, 0.9, 0.9),
                 color_b=(0.25, 0.25, 0.3), cells=8):
    """Returns uint8 (size, size, 3)."""
    size = int(size)
    rng = np.random.default_rng(seed)
    a, b = np.array(color_a) * 255, np.array(color_b) * 255
    ys, xs = np.mgrid[0:size, 0:size]
    u, v = xs / size, ys / size
    if kind == "checker":
        m = ((u * cells).astype(int) + (v * cells).astype(int)) % 2 == 0
        img = np.where(m[:, :, None], a, b)
    elif kind == "stripes":
        m = ((u * cells).astype(int)) % 2 == 0
        img = np.where(m[:, :, None], a, b)
    elif kind == "brick":
        row = (v * cells).astype(int)
        shift = (row % 2) * 0.5
        m = (((u + shift) * cells).astype(int)) % cells < cells - 1
        rowline = (v * cells) % 1 < 0.08
        colline = ((u + shift) * cells) % 1 < 0.08
        img = np.where((m & ~rowline & ~colline)[:, :, None], a, b)
    elif kind == "noise":
        n = rng.normal(0.5, 0.25, (size, size))
        n = np.clip(n, 0, 1)
        img = b[None, None, :] + (a - b)[None, None, :] * n[:, :, None]
    elif kind == "gradient":
        img = b[None, None, :] + (a - b)[None, None, :] * v[:, :, None]
    else:
        img = np.full((size, size, 3), a)
    return np.clip(img, 0, 255).astype(np.uint8)
