"""Forge3D command-line interface — the machine (and human) interface.

Usage: python -m forge3d.cli <command> [args]
Run `python -m forge3d.cli --help` for the full command list.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import forge3d
from forge3d.forge_lang import Interpreter, ForgeLangError, ForgeSyntaxError


def _load(file):
    f = os.path.abspath(file)
    return Interpreter(os.path.dirname(f)).run_file(f)


def _out_path(path, default):
    return path or default


# ---------------------------------------------------------------- commands
def cmd_new(args):
    path = args.name if args.name.endswith(".forge") else args.name + ".forge"
    starter = '''// %s — Forge3D starter scene
scene Starter {
  background #161a21
  camera Main { position 6 4 8 ; look_at 0 1 0 ; fov 50 }
}

light Key { type sun ; direction -0.45 -1 -0.35 ; color #fff2dd ; intensity 1.2 }

material Base { base_color #c0c6cf ; roughness 0.6 ; metallic 0.1 }

mesh Hero {
  primitive box
  size 1 1 1
  position 0 0.5 0
  material Base
  subdivide 1
  smooth 1 0.2
}

mesh Floor {
  primitive grid
  size 10 10
  subdivisions 10
  material Base
}
''' % args.name
    with open(path, "w") as f:
        f.write(starter)
    print(f"[forge3d] created {path}  (try: python -m forge3d.cli observe {path})")


def cmd_doctor(args):
    scene, rep = _load(args.file)
    from forge3d.doctor import examine_scene, report_text
    report = examine_scene(scene)
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(report_text(report))
    sys.exit(0 if report["score"] >= 80 else 2)


def cmd_render(args):
    scene, rep = _load(args.file)
    from forge3d.raster import render_scene
    from forge3d.pngio import write_png
    out = _out_path(args.out, os.path.splitext(args.file)[0] + "_render.png")
    img = render_scene(scene, args.width, args.height, wire=args.wire)
    write_png(out, img)
    print(f"[forge3d] rendered {args.width}x{args.height} -> {out}")
    if rep["warnings"]:
        for w in rep["warnings"]:
            print("  warning:", w)


def cmd_views(args):
    scene, _ = _load(args.file)
    from forge3d.raster import multi_view
    from forge3d.pngio import write_png
    prefix = _out_path(args.out, os.path.splitext(args.file)[0])
    views = multi_view(scene, args.size)
    for name, img in views.items():
        p = f"{prefix}_{name}.png"
        write_png(p, img)
        print(f"[forge3d] view {name} -> {p}")


def cmd_observe(args):
    """The agent's eyes+stethoscope in ONE command: render + doctor + stats."""
    scene, rep = _load(args.file)
    from forge3d.raster import render_scene, multi_view
    from forge3d.pngio import write_png
    from forge3d.doctor import examine_scene
    outdir = args.out or os.path.dirname(os.path.abspath(args.file))
    os.makedirs(outdir, exist_ok=True)
    img = render_scene(scene, args.width, args.height)
    shot = os.path.join(outdir, "observe_render.png")
    write_png(shot, img)
    views = multi_view(scene, args.viewsize)
    vshot = os.path.join(outdir, "observe_views_iso.png")
    write_png(vshot, views["iso"])
    report = examine_scene(scene)
    rpath = os.path.join(outdir, "observe_report.json")
    with open(rpath, "w") as f:
        json.dump(report, f, indent=1)
    from forge3d.doctor import report_text
    print(report_text(report))
    print(f"[forge3d] eyes: {shot} + {vshot}; report: {rpath}")


def cmd_export(args):
    scene, _ = _load(args.file)
    from forge3d import exporter
    fmt = args.format
    out = _out_path(args.out, os.path.splitext(args.file)[0] + "." +
                    ("gltf" if fmt == "gltf" else fmt))
    files = exporter.EXPORTERS[fmt](scene, out)
    print("[forge3d] exported:", ", ".join(files))


def cmd_bake(args):
    scene, _ = _load(args.file)
    from forge3d import baker
    if args.mode == "ao":
        for n in scene.mesh_nodes():
            if n.mesh.face_count <= args.max_tris:
                baker.bake_vertex_ao(n.mesh, rays=args.rays)
                print(f"[forge3d] baked AO on {n.name}")
    else:
        baker.bake_sun_shadow(scene)
        print("[forge3d] baked sun shadows")
    out = _out_path(args.out, os.path.splitext(args.file)[0] + "_baked.json")
    from forge3d.exporter import export_scene_json
    export_scene_json(scene, out)
    print("[forge3d] baked scene saved ->", out)


def cmd_sim(args):
    scene, rep = _load(args.file)
    from forge3d.physics import simulate
    frames, anim = simulate(scene, args.seconds, args.fps)
    print(f"[forge3d] simulated {args.seconds}s @ {args.fps}fps")
    for name, seq in frames.items():
        print(f"  {name}: start={seq[0][1].round(2)} end={seq[-1][1].round(2)}")
    if args.out:
        from forge3d.exporter import export_scene_json
        export_scene_json(scene, args.out)
        print("[forge3d] final state ->", args.out)


def cmd_play(args):
    scene, rep = _load(args.file)
    sounds = _materialize_sounds(rep.get("sounds", {}))
    from forge3d.runtime import run_headless
    api, log = run_headless(scene, rep.get("scripts", []), args.seconds,
                            args.fps, sounds)
    print("[forge3d] play (headless) done; ticks:", len(log))


def _materialize_sounds(sounds):
    from forge3d import audio
    for name, cfg in sounds.items():
        if "synth" in cfg and "wav_path" not in cfg:
            os.makedirs("out/sounds", exist_ok=True)
            kind = cfg["synth"][0]
            freq = float(cfg["synth"][1]) if len(cfg["synth"]) > 1 else 440.0
            dur = float(cfg["synth"][2]) if len(cfg["synth"]) > 2 else 0.5
            path = f"out/sounds/{name}.wav"
            audio.write_wav(path, audio.synth(freq, dur, kind, cfg["volume"]))
            cfg["wav_path"] = path
    return sounds


def cmd_synth(args):
    from forge3d import audio
    s = audio.synth(args.freq, args.dur, args.kind, args.volume)
    out = _out_path(args.out, f"{args.kind}_{int(args.freq)}.wav")
    audio.write_wav(out, s)
    print("[forge3d] synthesized", out)


def cmd_audio(args):
    scene, rep = _load(args.file)
    sounds = _materialize_sounds(rep.get("sounds", {}))
    for name, cfg in sounds.items():
        print("[forge3d] sound", name, "->",
              cfg.get("wav_path", cfg.get("file", "?")))


def cmd_gui(args):
    scene, rep = _load(args.file)
    from forge3d.runtime import run_interactive
    run_interactive(scene, rep.get("scripts", []), rep.get("sounds"))


def cmd_agent(args):
    from forge3d.agent.orchestrator import agent_build
    res = agent_build(args.prompt, provider=args.provider, model=args.model,
                      iterations=args.iterations, outdir=args.out or "out/agent")
    print(json.dumps(res, indent=1))


def cmd_chat(args):
    from forge3d.agent.chat import chat_loop
    chat_loop(provider=args.provider, model=args.model)


def cmd_selftest(args):
    import unittest
    loader = unittest.TestLoader()
    suite = loader.discover("tests", top_level_dir=".")
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


def cmd_version(args):
    print(f"Forge3D v{forge3d.__version__} '{forge3d.__codename__}'")


# ------------------------------------------------------------------- main
def main(argv=None):
    p = argparse.ArgumentParser(prog="forge3d", description="Forge3D CLI")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("new", help="scaffold a starter .forge scene")
    a.add_argument("name"); a.set_defaults(fn=cmd_new)

    a = sub.add_parser("doctor", help="validate scene health")
    a.add_argument("file"); a.add_argument("--json", action="store_true")
    a.set_defaults(fn=cmd_doctor)

    a = sub.add_parser("render", help="software-render scene to PNG")
    a.add_argument("file"); a.add_argument("-o", "--out")
    a.add_argument("--width", type=int, default=640)
    a.add_argument("--height", type=int, default=480)
    a.add_argument("--wire", action="store_true")
    a.set_defaults(fn=cmd_render)

    a = sub.add_parser("views", help="multi-view renders (front/side/top/iso/back)")
    a.add_argument("file"); a.add_argument("-o", "--out")
    a.add_argument("--size", type=int, default=320)
    a.set_defaults(fn=cmd_views)

    a = sub.add_parser("observe", help="AGENT EYES: render + views + health JSON")
    a.add_argument("file"); a.add_argument("-o", "--out")
    a.add_argument("--width", type=int, default=640)
    a.add_argument("--height", type=int, default=480)
    a.add_argument("--viewsize", type=int, default=256)
    a.set_defaults(fn=cmd_observe)

    a = sub.add_parser("export", help="export pipeline")
    a.add_argument("file"); a.add_argument("--format",
                 choices=["obj", "stl", "gltf", "json"], default="obj")
    a.add_argument("-o", "--out")
    a.set_defaults(fn=cmd_export)

    a = sub.add_parser("bake", help="baking engine: ao | shadow")
    a.add_argument("file"); a.add_argument("--mode", choices=["ao", "shadow"],
                 default="ao"); a.add_argument("--rays", type=int, default=16)
    a.add_argument("--max-tris", type=int, default=20000)
    a.add_argument("-o", "--out")
    a.set_defaults(fn=cmd_bake)

    a = sub.add_parser("sim", help="run physics simulation")
    a.add_argument("file"); a.add_argument("--seconds", type=float, default=3.0)
    a.add_argument("--fps", type=int, default=30); a.add_argument("-o", "--out")
    a.set_defaults(fn=cmd_sim)

    a = sub.add_parser("play", help="headless play (logic + physics)")
    a.add_argument("file"); a.add_argument("--seconds", type=float, default=3.0)
    a.add_argument("--fps", type=int, default=60)
    a.set_defaults(fn=cmd_play)

    a = sub.add_parser("synth", help="synthesize a WAV sound effect")
    a.add_argument("--kind", default="sine",
                 choices=["sine", "square", "saw", "noise", "chord"])
    a.add_argument("--freq", type=float, default=440.0)
    a.add_argument("--dur", type=float, default=0.5)
    a.add_argument("--volume", type=float, default=0.5)
    a.add_argument("-o", "--out")
    a.set_defaults(fn=cmd_synth)

    a = sub.add_parser("audio", help="materialize scene sounds to WAV")
    a.add_argument("file"); a.set_defaults(fn=cmd_audio)

    a = sub.add_parser("gui", help="interactive windowed mode")
    a.add_argument("file"); a.set_defaults(fn=cmd_gui)

    a = sub.add_parser("agent", help="AI agent builds a scene from a prompt")
    a.add_argument("prompt")
    a.add_argument("--provider", default=None)
    a.add_argument("--model", default=None)
    a.add_argument("--iterations", type=int, default=3)
    a.add_argument("-o", "--out", default=None)
    a.set_defaults(fn=cmd_agent)

    a = sub.add_parser("chat", help="interactive AI chat (bring your own key)")
    a.add_argument("--provider", default=None)
    a.add_argument("--model", default=None)
    a.set_defaults(fn=cmd_chat)

    a = sub.add_parser("selftest", help="run the test suite")
    a.set_defaults(fn=cmd_selftest)

    a = sub.add_parser("version"); a.set_defaults(fn=cmd_version)

    args = p.parse_args(argv)
    if not getattr(args, "fn", None):
        p.print_help()
        return 0
    try:
        args.fn(args)
    except (ForgeSyntaxError, ForgeLangError) as e:
        print(f"[forge3d] ERROR {e}", file=sys.stderr)
        return 1
    except Exception as e:
        if type(e).__name__ == "LLMError":
            print(f"[forge3d] LLM ERROR: {e}", file=sys.stderr)
            return 1
        raise
    except FileNotFoundError as e:
        print(f"[forge3d] ERROR file not found: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
