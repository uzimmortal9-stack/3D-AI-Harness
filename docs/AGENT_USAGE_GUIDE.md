# Forge3D Agent Usage Guide
## How an AI agent operates this platform like a pro

This guide assumes you are an AI model with shell access to a machine that has
this repository. Forge3D is **local-first**: you talk to it through the CLI and
text files; it talks back through deterministic reports and PNG images you can
read. No GUI required, no network required.

## 0. The operating loop (memorize)
```
PLAN  → WRITE(.forge) → COMPILE(doctor) → OBSERVE(render+views) → FIX → SHIP
```
Every pro session is this loop. Never declare success between WRITE and
OBSERVE.

## 1. Environment setup (once)
```bash
pip install -r requirements.txt        # numpy is the only hard dep
python -m forge3d.cli selftest         # green = platform healthy
python -m forge3d.cli new myscene      # scaffold
```

## 2. Building a scene
1. Read `docs/FORGE_LANGUAGE_HANDBOOK.md` completely (§0→§7 protocol).
2. Write `myscene.forge` following the handbook's HARD RULES.
3. `python -m forge3d.cli doctor myscene.forge` — fix every `error`.
4. `python -m forge3d.cli observe myscene.forge -o out/obs`
5. **Read** `out/obs/observe_render.png` with your vision. Compare against
   intent. `python -m forge3d.cli views myscene.forge -o out/v` and read the
   five angles to catch Janus-style blind spots.
6. Edit, repeat until doctor score ≥ 90 and images match intent.

## 3. The one-command agent pipeline
`python -m forge3d.cli agent "a cozy campfire with three logs and a kettle" \
  --provider openai --model gpt-4o-mini --iterations 3`
The orchestrator runs the generate→compile→doctor→fix loop automatically and
drops `agent_scene.forge`, `agent_render.png`, `agent_report.json` in
`out/agent/`. Inspect all three before trusting it.

## 4. Chatting with your own model (testing/iteration)
```bash
python -m forge3d.cli chat
you> /provider openai          # or anthropic | openrouter | ollama
you> /model gpt-4o
you> /key sk-...               # stored ONLY in config/forge3d.config.json
you> make a stone bridge over a dry creek
```
The chat auto-compiles and auto-renders every script the model emits, so you
see exactly what your model does on this platform. `ollama` works fully
offline with a local model — ideal for private iteration.

## 5. Games & logic
- Attach logic: `script "logic.py"` in the scene; hooks `on_start/on_update/on_end(api)`.
- Physics bodies: `body sphere { mass 1 ; restitution 0.6 ; velocity 0 2 0 }`.
- Headless test: `python -m forge3d.cli play scene.forge --seconds 5`.
- Human play (needs glfw/PyOpenGL): `python -m forge3d.cli gui scene.forge`.

## 6. Baking, export, delivery
```bash
python -m forge3d.cli bake scene.forge --mode ao --rays 16 -o out/baked.json
python -m forge3d.cli export scene.forge --format obj|stl|gltf -o out/x.*
```
`gltf` opens in any engine (Unity/Unreal/Godot/Blender). `stl` is 3D-print ready
(only watertight solids!). `obj` carries materials.

## 7. Pro habits
- One object = one mesh block; compose, don't boolean.
- Keep triangle counts honest; check `doctor --json` stats.
- Use `include "library.forge"` to build a personal asset library and reuse it.
- When doctor warns `OPEN_MESH` on terrain — expected; on a prop — bug.
- Screenshots are ground truth. If the render looks wrong, the scene IS wrong,
  regardless of what the file "says".
- Commit `.forge` sources; treat `out/` as scratch (gitignored).

## 8. Error triage cheat-sheet
| output | meaning | action |
|---|---|---|
| `ForgeSyntaxError L<n>` | grammar mistake at line n | consult handbook §1 |
| `material 'X' is not defined` | HR-3 violated | declare material first |
| doctor `score <80` | structural issues | read hints, fix, re-run |
| render all background | camera aimed at void | fix look_at/position |
| chat `LLM ERROR: No API key` | BYO key not set | §4 `/key` |
