# Forge3D Roadmap — trial & error, ship-then-fix philosophy

v0.1 "Basecamp" (this release) is the working base: engine core, language,
doctor, vision loop, exports, physics-lite, audio-lite, agent loop, docs.
Everything below is ordered by user value and will be built, tested on the
reference laptop (LOQ R7 7435HS / 24 GB / RTX 4050), bug-fixed, and released
iteratively with the user as QA.

## v0.2 — "Feel" (interactivity & rendering quality)
- [ ] VBO/VAO core-profile renderer (60 FPS @ 100k+ tris on RTX 4050)
- [ ] PBR shading: GGX specular, IBL approximation, gamma-correct pipeline
- [ ] Shadow maps (sun) in GL viewport; PCF
- [ ] Real skinning (linear blend, weight painting via nearest-2 bones)
- [ ] OBJ/glTF import (asset pipeline completes the loop)
- [ ] Texture atlas packer + island padding (proper UVs for baking)

## v0.3 — "World" (game-making power)
- [ ] Physics upgrade: capsule colliders, friction cones, sleep states,
      broadphase (spatial hash) — or integrate a proven native lib via FFI
- [ ] Collision events into scripting API (`on_collide(api, a, b)`)
- [ ] Tileable terrain heightfields + `terrain` ForgeScript block
- [ ] LOD generator (decimation + doctor-verified)
- [ ] Normal-map baking high→low poly (real bake engine v2)
- [ ] Audio: 3D positional panning, mixer thread, OGG support

## v0.4 — "Brain" (agent superpowers)
- [ ] Vision critic mode: render → VLM compares to target → auto-edit
      (dream-loop pattern, generalized)
- [ ] Asset library learning: compiled reusable ForgeScript snippets
      (SceneCraft's skill-library idea)
- [ ] `repair` command: import ANY obj/gltf → doctor → auto-fix suggestions
- [ ] Multi-agent scenes: planner / modeler / critic roles over one file
- [ ] Procedural texture language (node graph in text form)

## v0.5 — "Metal" (the own-language / own-runtime ambition)
- [ ] ForgeScript JIT: compile .forge → typed IR → C backend (`forgecc`)
      fulfilling the "create our own programming language" endgame with a
      real optimizing compiler and native codegen
- [ ] C core rewrite of rasterizer/raycaster behind the same Python API
- [ ] ECS (entity-component-system) for logic at scale
- [ ] Saved game format + hot reload of scripts while playing

## v1.0 — "Shippable product"
- [ ] Installer for Windows (pyinstaller → single exe)
- [ ] Qt or native UI editor (outliner, properties, material editor)
- [ ] Documentation site generated from handbook
- [ ] Benchmark suite vs. reference scenes; regression renders per release

## Working agreement (how we'll iterate with the user)
1. Every release = base works + `selftest` green + renders inspected.
2. User tests on real laptop; bugs filed as GitHub issues on branch
   `arena/01a0c982-3d-ai-harness`.
3. We fix → add features → repeat. No time limit; quality gates over dates.
