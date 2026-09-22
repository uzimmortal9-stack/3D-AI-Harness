# Forge3D — AI-native, local-first 3D creation platform

> v0.1 "Basecamp" — the working base version. Built from research into why AI
> fails at 3D (see `docs/RESEARCH_REPORT.md`) and designed so AI agents can
> **build, see, verify and fix** their own 3D work on a normal laptop.

Forge3D is **not a website**. It is a local application: a Python engine with a
CPU renderer (AI's eyes), an OpenGL viewport (human's eyes), a tiny
deterministic scene language (**ForgeScript**), a geometry **Doctor**, a
self-correcting **agent loop**, physics, audio, baking, rigging-lite, and a
full export pipeline.

Runs comfortably on: Lenovo LOQ / R7 7435HS / 24 GB RAM / RTX 4050 6 GB /
Windows 11 (and any Linux/mac with Python 3.9+).

## Install
```bash
git clone <this repo> && cd 3D-AI-Harness
pip install -r requirements.txt     # numpy (core); glfw+PyOpenGL (optional GUI)
python -m forge3d.cli selftest      # 31 tests green
```

## 60-second tour
```bash
# 1. see the showcase scene through the AI's eyes
python -m forge3d.cli render examples/first_scene.forge -o out/see.png

# 2. health-check any scene
python -m forge3d.cli doctor examples/mini_game.forge

# 3. play a physics game headless (logic scripts run)
python -m forge3d.cli play examples/mini_game.forge --seconds 5

# 4. export to any engine
python -m forge3d.cli export examples/first_scene.forge --format gltf

# 5. interactive window (needs glfw + PyOpenGL)
python -m forge3d.cli gui examples/mini_game.forge
```

## For AI agents
Start at **`docs/AGENT_USAGE_GUIDE.md`**, then the un-skippable
**`docs/FORGE_LANGUAGE_HANDBOOK.md`**. Your operating loop:
`WRITE .forge → doctor → observe (read the PNG!) → fix → ship`.
The one-command pipeline:
```bash
python -m forge3d.cli agent "a lighthouse on a rocky island at dusk" \
    --provider ollama            # or openai / anthropic / openrouter
```

## For humans testing AI models
```bash
python -m forge3d.cli chat
you> /provider openai
you> /key sk-...        # stored locally in config/forge3d.config.json
you> /model gpt-4o
you> build a red barn with a silo
```
Every script the model emits is auto-compiled, auto-doctored and rendered to
`chat_render.png` — instant ground truth for platform improvements.

## Feature matrix (v0.1)
| subsystem | status |
|---|---|
| Asset creation (9 primitives, lathe, merge) | ✅ |
| Geometry manipulation (subdivide/mirror/twist/taper/noise/smooth/weld) | ✅ |
| UV unwrapping (planar/box/cylinder) | ✅ |
| Materials & shading (PBR-lite + procedural textures) | ✅ |
| Rigging & animation (keyframes, skeletons, rigid skinning) | ✅ |
| Baking engine (vertex AO, sun shadows) | ✅ |
| Export pipeline (OBJ+MTL, STL, glTF 2.0, scene JSON) | ✅ |
| Real-time rendering (CPU rasterizer always; GL viewport optional) | ✅ |
| Physics engine (gravity, sphere/box/plane, impulses) | ✅ |
| Scripting & logic (Python hooks, fixed tick loop) | ✅ |
| Audio engine (synth, mix, WAV, OS playback) | ✅ |
| Input management (action maps) | ✅ |
| Scene & asset management (graph, parenting, includes, serialization) | ✅ |
| AI eyes (observe/views) + doctor + agent fix-loop + BYO-key chat | ✅ |

## Docs
- `docs/RESEARCH_REPORT.md` — why AI fails at 3D and how this fixes it
- `docs/AGENT_USAGE_GUIDE.md` — pro operating guide for AI agents
- `docs/FORGE_LANGUAGE_HANDBOOK.md` — the un-skippable language reference
- `docs/ARCHITECTURE.md` — module map & design principles
- `docs/ROADMAP.md` — v0.2 → v1.0 plan (we keep grinding)

## Develop
```bash
python -m unittest discover -s tests   # or: python -m forge3d.cli selftest
```
