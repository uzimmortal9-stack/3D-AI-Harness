# Forge3D Architecture (v0.1 "Basecamp")

```
┌────────────────────────────  AI / human layer  ───────────────────────────┐
│  agent/llm.py (BYO-key clients) · agent/orchestrator.py (fix loop)        │
│  agent/chat.py (REPL)  ·  docs/FORGE_LANGUAGE_HANDBOOK.md (in-context)    │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │ ForgeScript (.forge, plain text)
┌──────────────────────────────────▼───────────────────────────────────────┐
│ forge_lang/: lexer → parser → interpreter                                 │
│   tiny deterministic grammar ⇒ no API-hallucination surface               │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │ Scene graph (scene.py)
        ┌──────────┬───────────┬───┴────┬───────────┬───────────────────┐
        ▼          ▼           ▼        ▼           ▼          ▼         ▼
   geometry     uv.py     material   baker.py   anim.py   physics.py  audio.py
   mesh.py   (unwrappers) .py        (AO/shadow) (tracks,  (rigid      (synth,
   (prims,   shaders in raster/gl    bakes)     skeletons, bodies,     wav mix,
   ops)                                                   impulses)    playback)
        │                                     │
        ▼                                     ▼
  raster.py — CPU software renderer (THE EYES: headless screenshots)
  glview.py — GLFW+OpenGL interactive viewport (human mode)
  runtime.py — fixed-tick loop wiring logic(scripting.py)+physics+render
        │
        ▼
  exporter.py — OBJ+MTL / binary STL / glTF 2.0 / scene JSON
  doctor.py   — deterministic health checks (manifold, degen, NaN, winding,
                islands, budgets) → JSON + human report + score
  cli.py      — the single machine interface: new/doctor/render/views/
                observe/export/bake/sim/play/synth/audio/agent/chat/gui/
                selftest
```

## Design principles (from the research)
1. **Text is the interface.** Scenes, reports and docs are greppable text —
   context-window friendly, diffable, versionable. (Binary formats were a
   top agent blocker in engines.)
2. **Deterministic verification over vibes.** Doctor makes "is this mesh
   broken?" a machine question, closing the loop that SceneCraft/dream-loop
   showed is decisive.
3. **Renderer independence.** The CPU rasterizer guarantees the AI can always
   see its work, even on machines without GPU/display; the GL viewport is an
   optional human front-end.
4. **Small surface, big composition.** ~9 primitives + 7 ops + PBR-lite
   materials cover prototyping without version-drift hallucinations.
5. **Python core, C-speed later.** v0.1 prioritizes correctness and
   iteration speed; hot paths (rasterizer, raycaster) are isolated in single
   modules so a C/Rust rewrite (ROADMAP) drops in without API change.

## Module map (files → responsibility)
| file | responsibility |
|---|---|
| `math3d.py` | vectors, 4×4 matrices, look_at/perspective/orbit |
| `mesh.py` | Mesh struct, 9 primitives, 8 ops, ensure_outward |
| `uv.py` | planar/box/cylinder unwrappers (seam-free, unindexed) |
| `material.py` | PBR-lite params + procedural texture kitchen |
| `scene.py` | node graph, parenting, materials, serialization |
| `raster.py` | z-buffer CPU rasterizer, multi_view sheet |
| `baker.py` | vertex AO + sun-shadow baking (vectorized M-T rays) |
| `anim.py` | keyframe tracks, skeletons, rigid skinning |
| `physics.py` | semi-implicit Euler, sphere/box/plane contacts |
| `audio.py` | synth → mix → WAV → OS playback |
| `inputmgr.py` | action-map input abstraction |
| `scripting.py` | game-script hooks & safe-ish API object |
| `runtime.py` | headless + interactive fixed-tick loops |
| `glview.py` | GLFW/OpenGL viewport (optional deps) |
| `exporter.py` | OBJ/STL/glTF/JSON pipeline |
| `doctor.py` | health checks & scoring |
| `forge_lang/*` | lexer/parser/interpreter |
| `agent/*` | LLM clients, orchestrator fix-loop, chat |
| `cli.py` | command surface |

## Performance notes (Lenovo LOQ class hardware: R7 7435HS / 24 GB / RTX4050 6GB)
- Software renderer: ~0.2 s/frame at 640×480 for ≤5k tris (agent use).
- GL viewport: immediate-mode legacy GL — trivially within 4050 budget;
  v0.2 switches to VBO-based core profile for 60 FPS on 100k+ tris.
- Doctor/baker are O(V·F·rays): keep bakes ≤ 20k tris in v0.1 (flag exists).
