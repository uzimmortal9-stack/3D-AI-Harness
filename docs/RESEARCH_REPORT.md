# Forge3D Research Report
## Why AI can't (yet) build perfect 3D models & games — and how Forge3D fixes it

Scope: comprehensive internet research (papers, benchmarks, engineering blogs,
community reports) performed 2026-09-22 as the foundation of the Forge3D
platform design. Every claim below is cited.

---

## Part 1 — Why AI-generated 3D "sucks" at geometry and looks

### 1.1 The training-data cliff: 3D has no internet
There are **billions of 2D images** online but only **millions of 3D models**,
and most public 3D generators train on Objaverse (~900k models) or Sketchfab
subsets, so out-of-distribution prompts fail [3D asset generation — The Neural
Base](https://theneuralbase.com/generative-ai-fundamentals/learn/advanced/3d-asset-generation/).
High-quality 3D captures need specialized equipment and involved pipelines,
which limits generalizability [Understanding TRELLIS —
dgwave](https://dgwave.net/blog/understanding-microsoft-trellis-3d-ai-model).
Because of the scarcity, most text-to-3D systems don't learn 3D at all: they
use 2D diffusion models as teachers (score distillation / SDS), so the 3D
generator **inherits 2D biases and failure modes** — it favors front-facing,
well-lit, typical views and struggles with rare or ambiguous objects [3D asset
generation — The Neural Base](https://theneuralbase.com/generative-ai-fundamentals/learn/advanced/3d-asset-generation/),
[Generative 3D appearance design survey — OUP
JCDE](https://academic.oup.com/jcde/article/13/1/1/8340357).

### 1.2 AI learns "looks", not "structure"
Models trained on 2D projections assemble what they *think* an object should
look like, not vertices/edge-loops/manifold volumes. A prompt for "a detailed
sword" can produce a **flat plane with a texture** giving the illusion of a
blade rather than a solid mesh [Overcoming AI's Lack of Spatial Awareness —
Tripo](https://www.tripo3d.ai/blog/explore/lack-of-spatial-awareness).
Generative systems optimize visual appearance over geometric structure, so
raw AI output shows: dense chaotic triangulation ("topology soup"), holes in
low-confidence/occluded regions, non-manifold edges shared by 3+ faces,
internal floating faces, floating mesh islands, fused fingers/limbs, mirrored
artifacts [Why AI 3D Models Have Bad Topology —
Tripo](https://www.tripo3d.ai/blog/why-ai-3d-models-have-bad-topology),
[How to Fix Holes and Self-Intersections —
Tripo](https://www.tripo3d.ai/blog/explore/how-to-fix-holes-and-self-intersections-from-ai-meshes),
[Solving the Uncanny Geometry Problem —
Tripo](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-and-the-uncanny-geometry-problem).

### 1.3 Representation mismatch: meshes are not token sequences
Direct autoregressive mesh generation (MeshGPT and successors) faces a hard
"face ceiling": naive face tokenization costs 9 tokens per triangle, limiting
models to **~800–4,000 faces** because of quadratic Transformer cost; better
tokenizers (TreeMeshGPT's 2 tokens/face, Mesh Silksong's layered adjacency
matrices) push to ~5k–8k faces but still show **success-rate decay with
sequence length** — compounding autoregressive error produces holes, missing
components and flipped normals [TreeMeshGPT —
alphaXiv](https://www.alphaxiv.org/abs/2503.11629), [Mesh Silksong —
arXiv](https://arxiv.org/pdf/2507.02477). Native quad generation
(QuadGPT) remains a research frontier and still suffers domain gap when
deployed on noisy AI-generated point clouds [QuadGPT —
arXiv](https://arxiv.org/html/2509.21420v2). Plain-text mesh output
(LLaMA-Mesh) unifies modalities but at low geometric fidelity [LLaMA-Mesh —
GitHub](https://github.com/nv-tlabs/LLaMa-Mesh). Implicit-field routes
(NeRF/SDS, 3DGS) avoid topology but introduce their own plague: the
**multi-face Janus problem** (the object's front face reappears on its back),
caused by canonical-view bias in 2D teachers — baselines showed Janus rates up
to **85.7%**, reduced to ~3.4% only by explicit view-debiasing research
[ConsDreamer — arXiv](https://arxiv.org/html/2504.02316), [RecDreamer —
ADS](https://ui.adsabs.harvard.edu/abs/2025arXiv250212640Z/abstract),
[Debiasing Scores and Prompts —
ADS](https://ui.adsabs.harvard.edu/abs/2023arXiv230315413H/abstract).

### 1.4 Real-time engines judge systems, not screenshots
AI models look fine in turntables but fail the moment a real engine evaluates
them **systemically**: uneven polygon distribution, no LOD strategy,
overlapping UV islands, inconsistent texel density, collision meshes reusing
render geometry, style drift across asset libraries, and cleanup debt that
compounds instead of scaling [Why Most AI-Generated 3D Models Fail in
Real-Time Engines —
alpha3d](https://www.alpha3d.io/news/why-most-ai-generated-3d-models-fail-in-real-time-engines).
Rigging collapses at joints, subdivision exaggerates flaws, UV unwrapping and
booleans break on non-manifold input [Why AI 3D Models Have Bad Topology —
Tripo](https://www.tripo3d.ai/blog/why-ai-3d-models-have-bad-topology),
[Why Your 3D Mesh Topology Gets Messy —
Tripo](https://www.tripo3d.ai/blog/explore/smart-mesh-common-causes-of-messy-topology).

---

## Part 2 — What current 3D platforms LACK (the missing factors)

### 2.1 API mismatch is the #1 agent failure mode
Benchmarking 12 frontier VLMs on procedural 3D modeling (3DCodeBench):
**failures mostly arise from API mismatches** — ~85% of errors on excluded
backbones were Blender version-drift errors (removed BSDF sockets, renamed
modifiers); even *successfully executed* scripts yield **disconnected or
floating geometry** because models lack physical-world understanding
[3DCodeBench — arXiv](https://arxiv.org/html/2606.01057v1), [3DCodeBench
review — Pith](https://pith.science/paper/2606.01057). Unreal's C++ API has
**100,000+ public members across 1,000+ modules — no AI model has that
memorized correctly**, so agents hallucinate includes, deprecated functions,
made-up parameters [unreal-api-mcp —
Reddit](https://www.reddit.com/r/UnrealEngine5/comments/1rh4cx7/unrealapimcp_because_your_ai_agent_can_never_get/).
Blueprints are binary — unreadable by agents [r/unrealengine —
Reddit](https://www.reddit.com/r/unrealengine/comments/1le6i6m/currently_what_is_the_best_ai_assistant_for/).
Agents burn whole context windows grepping giant headers [unreal-api-mcp —
Reddit](https://www.reddit.com/r/UnrealEngine5/comments/1rh4cx7/unrealapimcp_because_your_ai_agent_can_never_get/).

### 2.2 Blindness: platforms give AI no eyes and no stethoscope
The decisive difference between bad and good agentic 3D is a **closed visual
feedback loop**: SceneCraft renders the Blender scene, feeds the image to a
vision LLM, and iterates the script until constraints hold — a dual-loop
self-improving pipeline [SceneCraft —
arXiv](https://arxiv.org/html/2403.01248v1). dream-loop wraps Blender + image
generation + a **separate critic subagent** scoring live screenshots on a
gated 0–10 ladder [dream-loop —
GitHub](https://github.com/achimala/dream-loop), [dream-loop —
AlphaSignal](https://alphasignal.ai/news/dream-loop-gives-coding-agents-a-gated-critic-loop-for-aaa-3d-visuals).
Production agents that read *live scene state* (mesh statistics, normals, UVs,
modifier stacks), act, look at what changed and correct themselves are exactly
the loop that makes multi-step passes survive contact with a real file
[Mixar/Mixie — Blender agent](https://www.mixar.app/blender-agent). Voxel
benchmarks show **multi-turn refinement and deterministic execution feedback
significantly improve results** — i.e., one-shot generation is the wrong
paradigm [VoxelCodeBench — arXiv](https://arxiv.org/html/2604.02580v1),
[3DCodeBench — arXiv](https://arxiv.org/html/2606.01057v1).

### 2.3 No deterministic verification, no budgets, no machine-readable state
Engines evaluate frame budgets, draw calls, VRAM, LOD behavior — while
generators are evaluated only visually [Why Most AI-Generated 3D Models Fail
in Real-Time Engines —
alpha3d](https://www.alpha3d.io/news/why-most-ai-generated-3d-models-fail-in-real-time-engines).
Benchmarks themselves admit 2D metrics are blind to 3D flaws and that the
field lacks human-aligned, standardized evaluation [3DGen-Bench —
Lacuna](https://lacuna.tiptreesystems.com/work/3dgen-bench-comprehensive-benchmark-suite-for-3d-generative-models/wrk_aeabcc25f15c2fdedf515b30).
AutoUE mitigates Unreal's complexity with RAG over tool docs, game-design
patterns, engine constraints and **automated play-testing** — multi-agent
specialization plus runtime verification [AutoUE —
arXiv](https://arxiv.org/html/2603.07106v1). The pattern across all successful
systems: *small grounded tool surface + retrieval-augmented docs + execute →
observe → fix loop*.

---

## Part 3 — The Forge3D answer (design derived from findings)

| Research finding | Forge3D countermeasure (shipped in v0.1) |
|---|---|
| Huge/hallucinated engine APIs | **ForgeScript**: tiny deterministic language, ~40 keywords, full grammar in handbook; impossible to "version-drift" |
| AI can't see its work | **Vision Loop**: dependency-free CPU renderer → `observe` writes PNGs the AI can inspect; `multi_view` sheet (front/side/top/iso/back) kills Janus-style blind spots |
| No deterministic validation | **Doctor**: manifold/watertight/degenerate/duplicate/NaN/winding/island/budget checks with machine-readable JSON + fix hints |
| One-shot generation fails | **Agent orchestrator**: generate → compile → doctor → feed errors back → regenerate loop; then render and report |
| Disconnected/floating geometry | Physics bodies + doctor island checks; units/scale rules in handbook |
| Binary/unreadable assets | Everything is plain text (.forge, .json) — diffable, greppable, context-window friendly |
| Cleanup debt | Primitives+ops compose clean watertight topology by construction (verified by tests) |
| Model needs docs in-context | Handbook written as mandatory-checkpoint protocol; system prompt embedded in orchestrator |

The platform itself is **Python (CPython + NumPy core)** — a robust, mature
language, with an optional C-speed path later (see ROADMAP). It is **100%
local**: no web UI, no cloud round-trips; the software renderer and GLFW
viewport use the machine's full power.

---

## Part 4 — Source index (by topic)

- Topology defects: [holes & self-intersections](https://www.tripo3d.ai/blog/explore/how-to-fix-holes-and-self-intersections-from-ai-meshes), [bad topology](https://www.tripo3d.ai/blog/why-ai-3d-models-have-bad-topology), [uncanny geometry](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-and-the-uncanny-geometry-problem), [messy topology](https://www.tripo3d.ai/blog/explore/smart-mesh-common-causes-of-messy-topology)
- Real-time failure modes: [alpha3d](https://www.alpha3d.io/news/why-most-ai-generated-3d-models-fail-in-real-time-engines)
- Autoregressive mesh generation: [TreeMeshGPT](https://www.alphaxiv.org/abs/2503.11629), [QuadGPT](https://arxiv.org/html/2509.21420v2), [Mesh Silksong](https://arxiv.org/pdf/2507.02477), [LLaMA-Mesh](https://github.com/nv-tlabs/LLaMa-Mesh)
- Multi-view/Janus: [ConsDreamer](https://arxiv.org/html/2504.02316), [RecDreamer](https://ui.adsabs.harvard.edu/abs/2025arXiv250212640Z/abstract), [PerpNeg/debiasing](https://ui.adsabs.harvard.edu/abs/2023arXiv230315413H/abstract)
- Data scarcity & 2D-teacher bias: [Neural Base](https://theneuralbase.com/generative-ai-fundamentals/learn/advanced/3d-asset-generation/), [TRELLIS](https://dgwave.net/blog/understanding-microsoft-trellis-3d-ai-model), [OUP survey](https://academic.oup.com/jcde/article/13/1/1/8340357), [spatial awareness](https://www.tripo3d.ai/blog/explore/lack-of-spatial-awareness)
- Agentic procedural 3D: [3DCodeBench](https://arxiv.org/html/2606.01057v1), [VoxelCodeBench](https://arxiv.org/html/2604.02580v1), [3DGen-Bench](https://lacuna.tiptreesystems.com/work/3dgen-bench-comprehensive-benchmark-suite-for-3d-generative-models/wrk_aeabcc25f15c2fdedf515b30)
- Feedback-loop systems: [SceneCraft](https://arxiv.org/html/2403.01248v1), [dream-loop](https://github.com/achimala/dream-loop), [Mixar](https://www.mixar.app/blender-agent)
- Engine automation: [AutoUE](https://arxiv.org/html/2603.07106v1), [UE 5.8 MCP](https://explainx.ai/blog/unreal-engine-5-8-claude-codex-mcp-ai-integration-2026), [unreal-api-mcp](https://www.reddit.com/r/UnrealEngine5/comments/1rh4cx7/unrealapimcp_because_your_ai_agent_can_never_get/)
