# ForgeScript Handbook (v0.1)
## The un-skippable reference for AI modelers

> ┌─────────────────────────────────────────────────────────────────────────┐
> │ **MANDATORY READING PROTOCOL — follow in order, no section may be      │
> │ skipped. After EACH § checkpoint you MUST restate, in one line, the     │
> │ rules you just read, before continuing. If you catch yourself about to  │
> │ write ForgeScript before finishing §7, STOP and finish §7 first.        │
> │ Writing code that violates a HARD RULE (HR-n) is a failed task.         │
> └─────────────────────────────────────────────────────────────────────────┘

Table of contents: §0 mental model · §1 lexical rules · §2 blocks ·
§3 mesh ops · §4 HARD RULES · §5 failure table · §6 verification loop ·
§7 self-test · §8 worked example · §9 quick card.

---

## §0 — Mental model  [CHECKPOINT C0]
Forge3D scenes are **composed, not sculpted**: you place watertight
primitives, transform them, apply a few global deformers, assign materials,
and let the **Doctor** prove the result healthy. Y is UP. Units are METERS.
Everything is deterministic: same file ⇒ same scene, same render, same report.

*C0 restate:* scenes are composed from primitives; Y-up; meters; Doctor verifies.

---

## §1 — Lexical rules  [CHECKPOINT C1]
1. Statements end with `;` **or a newline** (both legal; pick one style).
2. Comments: `// ...` (or `#` at line start only; `#rrggbb` is a color).
3. Strings: double quotes. Numbers: plain decimals, negatives allowed.
4. Colors: `#rgb` or `#rrggbb`.
5. Identifiers: names for blocks; use semantic CamelCase (`KitchenTable`).
6. Blocks: `kind Name { ... }`. Nesting allowed only where specified
   (`scene` may nest `camera`/`light`; `mesh` may nest `body`).
7. Unknown property = warning (ignored); in `--strict` mode = hard error.
   The grammar in this handbook is COMPLETE: **never invent syntax**.

*C1 restate:* terminator `;`/newline; comments `//`; colors `#hex`; complete grammar.

---

## §2 — Block reference  [CHECKPOINT C2]

### scene
```
scene Name {
  background #10141a        // hex or 3 floats
  ambient 0.3               // 0..1 hemisphere fill
  gravity -9.81             // physics, m/s^2 (negative = down)
  camera Main               // activate a camera by name
}
```
### camera
```
camera Name { position x y z ; look_at x y z ; fov 50 ; active true }
```
Rule of framing: distance ≈ 2.2 × the scene's largest dimension; look_at the
cluster center; fov 45–60.

### light
```
light Name {
  type sun | point
  direction -0.45 -1 -0.35  // sun: direction light travels
  position x y z            // point light position
  color #fff2dd ; intensity 1.2
}
```
Always at least one light (else an auto-sun is injected and you lose control).

### material
```
material Name {
  base_color #hex | r g b   // 0..1 floats or hex
  metallic 0.0              // 0 = dielectric, 1 = metal
  roughness 0.6             // 0 = mirror-ish, 1 = matte
  emission 0.0              // >0 glows (neon, lava, screens)
  texture checker|stripes|noise|brick|gradient [SIZE] [CELLS]
  texture_file "path.png"
}
```
Materials MUST be declared BEFORE any mesh that references them.
`texture*` is only visible if the mesh also declares `uv ...`.

### mesh  (the core)
```
mesh Name {
  primitive box|sphere|cylinder|cone|plane|grid|torus|capsule
  // per-primitive params:
  //   box:      size x y z
  //   sphere:   radius r ; rings n ; segments n
  //   cylinder: radius r ; height h ; segments n
  //   cone:     radius r ; height h ; segments n
  //   plane:    size s ; subdivisions n
  //   grid:     size x z ; subdivisions n
  //   torus:    radius r ; tube t ; segments n ; rings n
  //   capsule:  radius r ; height h ; rings n ; segments n
  position x y z
  rotation x y z            // degrees
  scale x y z
  material Name
  uv box|planar|cylinder [axis]
  // deform ops, executed top-to-bottom:
  subdivide n ; mirror x|y|z ; twist axis deg_per_unit ;
  taper axis factor ; noise amp seed ; smooth iters factor ; weld eps
  body sphere|box { mass f ; restitution f ; static true|false ; velocity x y z }
  script "relative/path.py"
}
```

### sound
```
sound Name { synth sine|square|saw|noise|chord FREQ SECONDS ; volume 0.8 ; loop false }
sound Name { file "assets/x.wav" ; volume 0.8 }
```

### group / include / script
```
group Name { position ... ; child "Other" ; child "Third" }
include "other_file.forge"
script "game_logic.py"       // top-level logic script
```

*C2 restate:* know all 9 block kinds and their exact property names.

---

## §3 — Mesh ops semantics  [CHECKPOINT C3]
| op | exact effect | danger |
|---|---|---|
| `subdivide n` | ×4 triangles per level | n=3 → 64× faces; keep n ≤ 2 |
| `mirror axis` | reflect + flip winding (safe) | mirroring twice ≠ original vertex order (fine) |
| `twist axis deg` | rotate cross-sections by deg×coordinate | >180/unit makes pretzels |
| `taper axis f` | scale 1→f along axis | f=0 collapses to a line (degenerate) |
| `noise amp seed` | displace along normals, gaussian | amp > 10% of size ⇒ lumpy garbage |
| `smooth iters f` | laplacian shrink-smooth | many iters shrink objects |
| `weld eps` | merge near-duplicate verts | destroys per-face UVs |

Ops run in the order written, after primitive creation, before node transform.

*C3 restate:* ops are ordered; subdivide explodes counts; taper 0 and big noise break meshes.

---

## §4 — HARD RULES (violation = failed task)  [CHECKPOINT C4]
- **HR-1** Every object that should sit on the floor has its bottom at y=0:
  for a primitive of height h centered at origin, `position y = h/2`.
- **HR-2** No two solids may interpenetrate unless intentional (joints).
- **HR-3** Define materials before use; every visible mesh gets a material.
- **HR-4** Keep the scene inside ~±10 m; one unit = one meter (physics & cameras
  assume it).
- **HR-5** Total triangles < 100k for real-time on a laptop GPU/CPU.
- **HR-6** Give every scene: ≥1 camera with framing per §2, ≥1 light,
  1 ground (grid/plane) unless the subject is a floating object study.
- **HR-7** Name objects semantically; never `mesh m1`.
- **HR-8** Physics bodies: use `body box { static true }` for architecture,
  dynamic `body sphere` only for round-ish things.
- **HR-9** After writing the file you MUST run the verification loop (§6)
  and fix every `error`-level doctor finding before declaring success.
- **HR-10** Output ONE fenced ```forge block per scene file; no prose inside.

*C4 restate:* I can recite HR-1..HR-10.

---

## §5 — Failure table (symptom → cause → fix)  [CHECKPOINT C5]
| symptom (doctor / render) | cause | fix |
|---|---|---|
| `DEGENERATE_TRIANGLES` | zero-size primitive / `taper … 0` / duplicate verts | give real sizes; `weld` |
| `NON_MANIFOLD` | two solids merged into one mesh occupying same space | keep parts as separate mesh blocks |
| `OPEN_MESH` on a solid | primitive is plane/grid by mistake | use box with thickness |
| `FLIPPED/INSIDE_OUT` | hand-built mesh reversed | rebuild via primitive |
| black faces in render | winding/normal corruption | rebuild; don't stack `mirror` |
| object floating | HR-1 violation | y = h/2 |
| object invisible | outside camera frustum | re-check §2 framing |
| texture not visible | `texture` without `uv` | add `uv box` |
| `HIGH_POLY` warn | subdivide/segments too big | reduce; LODs later |

*C5 restate:* I will consult this table whenever the doctor complains.

---

## §6 — Verification (Vision) loop  [CHECKPOINT C6]
You are not done when the file parses. You are done when:
```
python -m forge3d.cli doctor  FILE.forge            # score ≥ 80, zero errors
python -m forge3d.cli observe FILE.forge -o out/obs # then READ observe_render.png
python -m forge3d.cli views   FILE.forge -o out/v   # READ vs_*.png, check all sides
```
If any view shows intersection/floating/missing objects → edit → re-run.
This loop replaces "screen sharing": the renders ARE your screen.

*C6 restate:* doctor + observe + views, read images, iterate until clean.

---

## §7 — Pre-code self-test  [CHECKPOINT C7]
Before emitting ForgeScript, answer silently (and obey):
1. Did I plan a ground, a light, a camera? (§2, HR-6)
2. Is every resting object's y = h/2? (HR-1)
3. Are materials declared before meshes? (HR-3)
4. Is triangle budget respected? (HR-5; sphere 16×28 ≈ 864 tris)
5. Did I avoid invented properties? (§1.7)
6. Will I run doctor+observe+views after? (HR-9)

*C7 restate:* all six answered yes, otherwise I fix the plan now.

---

## §8 — Worked example (gold standard)
```
scene Teapot_Study {
  background #14181f
  ambient 0.28
  camera Hero { position 5.5 3.6 6.5 ; look_at 0 0.9 0 ; fov 50 ; active true }
}

light Key  { type sun ; direction -0.5 -1 -0.4 ; color #ffe9c4 ; intensity 1.2 }
light Fill { type point ; position 6 3 -4 ; color #7fa0ff ; intensity 0.5 }

material Ceramic { base_color #cfd6df ; roughness 0.25 ; metallic 0.05 }
material Walnut  { base_color #6b4a2f ; roughness 0.7 ; texture stripes 64 12 }

mesh Floor { primitive grid ; size 12 12 ; subdivisions 10 ; material Walnut ; uv planar }

mesh Body {
  primitive sphere ; radius 0.8 ; rings 18 ; segments 30
  position 0 0.9 0
  scale 1 0.75 1
  material Ceramic
}

mesh Lid {
  primitive sphere ; radius 0.34 ; rings 12 ; segments 20
  position 0 1.52 0
  scale 1 0.6 1
  material Ceramic
}

mesh Handle {
  primitive torus ; radius 0.34 ; tube 0.07 ; segments 24 ; rings 10
  position 0.82 0.95 0
  rotation 90 0 0
  material Ceramic
}

mesh Spout {
  primitive cone ; radius 0.14 ; height 0.7 ; segments 14
  position -0.75 1.0 0
  rotation 0 0 115
  material Ceramic
}
```
Note: parts interpenetrate ONLY at joints (HR-2 "unless intentional"), every
height is hand-computed (HR-1), budget ≈ 2.5k tris (HR-5).

---

## §9 — Quick card (memorize)
```
primitive box size x y z | sphere radius rings segments | cylinder radius height segments
cone radius height segments | plane size subdivisions | grid size x z subdivisions
torus radius tube segments rings | capsule radius height rings segments
position/rotation/scale (deg) | material M | uv box|planar|cylinder
subdivide|mirror|twist|taper|noise|smooth|weld | body … {…} | script "f.py"
```
END OF HANDBOOK. You may now write ForgeScript.
