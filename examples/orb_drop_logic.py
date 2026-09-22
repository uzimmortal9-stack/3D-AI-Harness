"""Forge3D game logic example — 'Orb Drop'.

Demonstrates the scripting & logic environment hooks.
"""
import math

_spun = {"t": 0.0}


def on_start(api):
    api.log("Orb Drop started — two orbs fall into the arena.")


def on_update(api, dt):
    _spun["t"] += dt
    arch = api.get("Arch")
    if arch is not None:
        arch.rotation = arch.rotation + [0, 40 * dt, 0]  # spin the golden arch
    for name in ("Ball1", "Ball2"):
        b = api.bodies.get(name)
        if b is not None and b.position[1] < 0.6 and abs(b.velocity[1]) < 0.1:
            if not _spun.get("landed_" + name):
                _spun["landed_" + name] = True
                api.log(name, "landed at", tuple(round(x, 2) for x in b.position))
                api.play("Bounce")
    if _spun.get("landed_Ball1") and _spun.get("landed_Ball2"):
        if not _spun.get("won"):
            _spun["won"] = True
            api.log("Both orbs landed — YOU WIN")
            api.play("Win")


def on_end(api):
    api.log("Orb Drop finished at t=%.2f" % api.time)
