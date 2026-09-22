"""Forge3D agent orchestrator — the self-correcting build loop.

prompt -> LLM writes ForgeScript -> interpreter compiles -> doctor validates
-> errors fed back -> LLM fixes -> render -> report. The agent literally looks
at its own work (screenshots + deterministic health metrics) and corrects
itself, which is the fix for the 'AI can't see what it's doing' root cause.
"""
import json
import os
import re

import forge3d
from forge3d.forge_lang import Interpreter, ForgeSyntaxError, ForgeLangError
from forge3d.doctor import examine_scene, report_text

AGENT_SYSTEM = """You are Forge3D's resident 3D artist-engineer. You write
ForgeScript, a small deterministic scene language. OUTPUT ONLY ForgeScript
inside a ```forge fenced block, nothing else.

LANGUAGE GRAMMAR (complete and final — do NOT invent syntax):
  Blocks: scene NAME { }, camera NAME { }, light NAME { }, material NAME { },
          mesh NAME { }, sound NAME { }, group NAME { }
  Statements end with ';' OR newline. Comments: // ...
  scene { background #hex ; ambient 0.3 ; gravity -9.81 ; camera NAME }
  camera { position x y z ; look_at x y z ; fov 50 ; active true }
  light { type sun|point ; direction x y z ; position x y z ;
          color #hex ; intensity 1.2 }
  material { base_color #hex ; metallic 0..1 ; roughness 0..1 ; emission 0..1 ;
             texture checker|stripes|noise|brick|gradient SIZE CELLS }
  mesh { primitive box|sphere|cylinder|cone|plane|grid|torus|capsule
         size x y z | radius r | tube r | height h | segments n | rings n |
         subdivisions n
         position x y z ; rotation x y z ; scale x y z
         material NAME ; uv box|planar|cylinder
         ops (in order): subdivide n ; mirror x|y|z ; twist AXIS deg ;
         taper AXIS factor ; noise amp seed ; smooth iters factor ; weld eps
         body sphere|box { mass f ; restitution f ; static true|false ;
                           velocity x y z }
  sound NAME { synth sine|square|saw|noise|chord FREQ DUR ; volume 0.8 }
  units are METERS. Y is UP. Keep object scales 0.1..20.
RULES (hard constraints):
 1. Every mesh: place it so it does NOT intersect the floor: bottom at y>=0.
 2. Materials must be DEFINED before meshes use them.
 3. Prefer few well-placed primitives over many; name objects semantically.
 4. Ground plane: `mesh Floor { primitive grid ; size 12 12 ; subdivisions 8 ; material M }`.
 5. Never output raw vertex data; compose from primitives + ops.
 6. After writing, mentally render: camera must see the objects
     (position ~ (6,5,9), look_at the object cluster center)."""


def _extract_script(text):
    m = re.search(r"```(?:forge|fs)?\s*\n(.*?)```", text, re.S)
    return m.group(1) if m else text


def agent_build(prompt, provider=None, model=None, iterations=3,
                outdir="out/agent"):
    from . import llm
    os.makedirs(outdir, exist_ok=True)
    scene_file = os.path.join(outdir, "agent_scene.forge")
    render_file = os.path.join(outdir, "agent_render.png")
    report_file = os.path.join(outdir, "agent_report.json")

    messages = [{"role": "user", "content":
                 f"Build this as a ForgeScript scene: {prompt}"}]
    history = []
    last_script, last_err = "", None
    for it in range(max(1, iterations)):
        reply = llm.chat(messages, system=AGENT_SYSTEM, provider=provider,
                         model=model)
        script = _extract_script(reply)
        last_script = script
        with open(scene_file, "w") as f:
            f.write(script)
        interp = Interpreter(outdir)
        try:
            scene, rep = interp.run_file(scene_file)
            last_err = None
        except (ForgeSyntaxError, ForgeLangError) as e:
            last_err = str(e)
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content":
                             f"COMPILER ERROR:\n{e}\nFix the script and "
                             "output the corrected FULL ForgeScript only."})
            continue
        report = examine_scene(scene)
        errs = [i for i in report["issues"] if i["level"] == "error"]
        if errs:
            txt = report_text(report)
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content":
                             f"DOCTOR REPORT (errors to fix):\n{txt}\nOutput "
                             "the corrected FULL ForgeScript only."})
            last_err = txt
            continue
        # healthy: render the eyes
        from forge3d.raster import render_scene
        from forge3d.pngio import write_png
        img = render_scene(scene, 640, 480)
        write_png(render_file, img)
        result = {"status": "ok", "iterations": it + 1,
                  "scene": scene_file, "render": render_file,
                  "report": report_file, "doctor_score": report["score"],
                  "stats": scene.stats()}
        with open(report_file, "w") as f:
            json.dump(report, f, indent=1)
        return result
    # exhausted iterations
    result = {"status": "failed_after_iterations", "iterations": iterations,
              "scene": scene_file, "last_error": last_err,
              "last_script": last_script}
    with open(report_file, "w") as f:
        json.dump(result, f, indent=1)
    return result
