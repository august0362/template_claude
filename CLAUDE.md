# CLAUDE.md — Root Router & Session Engine

> This file is loaded automatically by Claude Code at the start of every session. It is a **router**, not a place for details. Details live in `docs/context/` (project state) and `.claude/agents/` (specialized roles). Do not duplicate the content of those files here.

---

## 1. Core Engineering Invariants

The invariants below apply to EVERY line of generated code, regardless of role. A violation means the code is rejected in the QA phase.

### 1.1 Zero-GC in the hot path

Hot path = `Update()`, `LateUpdate()`, `FixedUpdate()`, `IState.Tick/FixedTick`, `BTNode.Tick`, every Physics callback, and every function called from them.

| Forbidden in the hot path | Use instead |
|---|---|
| `new` class/array/`List<T>`/`Dictionary` | Pre-allocate in `Awake`/`OnSpawnFromPool`, reuse with `Clear()` |
| Boxing (`object`, non-generic `IComparable`, `string.Format` with value types, `enum.ToString()`, `enum.HasFlag` on older runtimes) | Generic constraint `where T : struct`, manual bit test `(flags & mask) != 0` |
| LINQ (`Where`, `Select`, `Any`, `ToList`, `OrderBy`) | `for` loop over `List<T>`/arrays, index-based |
| `foreach` over `IEnumerable<T>` / interfaces | `for` with an index, or `foreach` over `List<T>` (struct enumerator, no alloc) |
| String concatenation `"a" + b`, `$"..."`, `string.Format` | Cached `StringBuilder`, `TMP_Text.SetText(fmt, arg)`, or a cached `string[]` for small integers |
| Lambdas/anonymous delegates that capture variables (closures) | `static` lambda, a delegate cached in a field, or a method group cached once |
| `GetComponent<T>()`, `Camera.main`, `FindObjectOfType`, `GameObject.Find`, `tag ==` | Cache in `Awake`; use `CompareTag`; inject references |
| `Physics.RaycastAll`, `SphereCastAll`, `OverlapSphere` | `NonAlloc` versions with a pre-allocated buffer |
| `Vector3[]`/`Mesh.vertices`/`Mesh.normals` getters | `Mesh.GetVertices(List<Vector3>)`, `Mesh.AcquireReadOnlyMeshData` |
| Coroutine `yield return new WaitForSeconds(x)` | Cache the `WaitForSeconds` in a field; prefer a float timer in `Tick` |
| Unwrapped `Debug.Log` | `[Conditional("UNITY_EDITOR")]` or `[Conditional("ENABLE_LOG")]` wrapper |

Budget: **0 bytes of managed allocation per frame** in steady state (measured with the Profiler → GC Alloc column = 0 B).

### 1.2 Object Pooling is mandatory

Every dynamically spawned/destroyed entity must go through a pool and implement `IPoolable` (see `docs/context/CONTRACTS_ADR.md`):

- Projectiles, hit VFX, muzzle flash, damage popups, decals, one-shot SFX emitters.
- Enemies (even when a wave has < 10 — pooling is a rule, not a premature optimization).
- No `Instantiate`/`Destroy` in the gameplay loop. `Instantiate` is legal only in `Pool.Prewarm()` during loading.
- A pool must have a `maxSize`; on overflow: recycle the oldest entity (or reject the spawn), NEVER silently `Instantiate` more.

### 1.3 3D math

- **Rotation = `Quaternion`.** Never add/subtract `eulerAngles` to rotate continuously. Accumulate yaw/pitch as separate `float`s (pitch already `Clamp`ed), then build `Quaternion.AngleAxis(yaw, Vector3.up) * Quaternion.AngleAxis(pitch, Vector3.right)`.
- Directions: use `transform.forward/right/up`, `Vector3.Dot`, `Vector3.Cross`, `Vector3.SignedAngle`, `Quaternion.LookRotation`, `Quaternion.RotateTowards`, `Quaternion.Slerp` (or `SlerpUnclamped` when controlled).
- Compare distances with `sqrMagnitude`; call `magnitude`/`Distance` only when the real value is needed.
- Normalization: check `sqrMagnitude > 1e-8f` before `normalized` to avoid NaN/zero vectors. Use `Vector3.ClampMagnitude` and `Vector3.ProjectOnPlane` for planar movement.
- Never compare floats with `==`. Use `Mathf.Approximately` or an explicit epsilon.
- Framerate-independent movement: multiply by `Time.deltaTime` (Update) or `Time.fixedDeltaTime` (FixedUpdate); smooth lerps use `1f - Mathf.Exp(-k * dt)` instead of `Lerp(a, b, 0.1f)`.
- Physics: change `Rigidbody.velocity`/`MovePosition`/`AddForce` only in `FixedUpdate`. Never move the `Transform` of a non-kinematic `Rigidbody`.

### 1.4 Rendering budget

| Metric | Budget |
|---|---|
| Draw calls (SetPass + Batches) | **< 150** in the reference scene |
| Character triangles | ≤ 30k tris |
| Materials per character | ≤ 3 |
| Frame time | 16.6 ms (locked 60 FPS) |

Rules: enable the SRP Batcher (every shader must be compatible — `UnityPerMaterial` CBUFFER), GPU Instancing for repeated props (`#pragma multi_compile_instancing`), Static Batching for static environment, share materials, use texture atlases, LOD groups for assets > 5k tris. Never use `renderer.material` (creates an instance) — use `sharedMaterial` or `MaterialPropertyBlock` (weigh the SRP Batcher impact of property blocks; prefer per-instance `_BaseColor` through instancing).

---

## 2. Directory Mapping

```
/
├── CLAUDE.md                          ← this file (router, always loaded)
├── README.md                          ← template usage guide
├── .gitignore
├── .gitattributes                     ← LF normalization + Git LFS for binary assets
├── .claude/
│   ├── agents/
│   │   ├── SYSTEM_ORCHESTRATOR.md     ← 4-phase pipeline, handoff schema, conflict matrix
│   │   ├── 01_GAME_ARCHITECT.md       ← architecture, patterns, event bus
│   │   ├── 02_GAMEPLAY_ENGINEER.md    ← gameplay, controls, camera, combat, physics
│   │   ├── 03_TECH_ARTIST.md          ← shaders, Blender, FBX pipeline
│   │   ├── 04_AI_DESIGNER.md          ← FSM, Behavior Tree, NavMesh, perception
│   │   ├── 05_ECONOMY_BALANCER.md     ← stats, formulas, progression, config
│   │   └── 06_QA_PROFILER.md          ← profiling, GC, memory leaks, refactoring
│   ├── commands/
│   │   └── handover.md                ← slash command /handover
│   └── local/                         ← (gitignored) temporary AI logs
├── docs/context/
│   ├── PROJECT_CONTEXT.md             ← single source of truth (engine, budgets, conventions)
│   ├── SESSION_LOG.md                 ← external memory between sessions
│   ├── ROADMAP_BACKLOG.md             ← milestones + checklist + acceptance criteria
│   └── CONTRACTS_ADR.md               ← core interfaces + Architecture Decision Records
└── scripts/
    ├── verify.sh                      ← build/test/audit gate for the Self-Healing Loop
    ├── audit_hotpath.py               ← scans hot paths for Zero-GC violations (ERROR blocks merge)
    └── blender_export_unity.py        ← normalizes pivot, freezes transforms, exports Y-Up FBX
```

When you add a file to any directory above, update this map in the same commit.

---

## 3. Session Lifecycle Protocol

### 3.1 Session Start (mandatory, before handling any task)

Read in this exact order:

1. `docs/context/PROJECT_CONTEXT.md` — engine, budgets, conventions. This is the source of truth; if it conflicts with your memory, the file wins.
2. `docs/context/SESSION_LOG.md` — read the **newest** block (at the top) to learn the current branch, active milestone, technical debt and **Exact Next 3 Steps**.
3. `docs/context/ROADMAP_BACKLOG.md` — find the first `[ ]` task of the active milestone.

Then report to the user in exactly 4 lines: current branch · active milestone · next task · blocker (if any). Do not write code before this step is done.

If the task touches an interface/contract, also read `docs/context/CONTRACTS_ADR.md`.

### 3.2 Session End / Handover — the `/handover` command

The user types `/handover` (defined in `.claude/commands/handover.md`), or Claude does it on its own when it sees signs that the session is ending. Fixed sequence:

1. **Tick the checklist:** in `ROADMAP_BACKLOG.md`, change `[ ]` → `[x]` for each task whose Acceptance Criteria were verified with a real command/test. Do NOT tick a task whose metric has not been measured.
2. **Write the diff summary:** run `git diff --stat` and `git log --oneline` from the start of the session; summarize by file/module in *Work Completed in Session*.
3. **Record technical debt/bugs** discovered in *Technical Debt / Bugs Discovered* (with file:line).
4. **Write Exact Next 3 Steps:** 3 concrete actions, each small enough for one session, with a file path and a completion criterion.
5. **Add a new block at the top** of `SESSION_LOG.md` (never edit old blocks). Increment the session number.
6. Commit: `docs(session): handover session NN` and report the commit hash to the user.

### 3.3 Context maintenance rules

- Edit `PROJECT_CONTEXT.md` only when a project-level decision changes; record the reason in an ADR.
- `SESSION_LOG.md` is append-only by block (newest on top).
- Do not paste long code into `SESSION_LOG.md`; reference `path:line` or a commit hash only.

---

## 4. Dynamic Role Routing Table

**Hard rule:** before generating any line of code, identify the intent, **read the matching role file with the Read tool**, and only then work inside that role's framework. For a multi-intent task, read `SYSTEM_ORCHESTRATOR.md` first, then each role in pipeline order.

| Keywords / task context | Role file (read before coding) |
|---|---|
| architecture, design pattern, event bus, message broker, dependency injection, service locator, assembly definition, module boundary, save/load architecture, scene management | `.claude/agents/01_GAME_ARCHITECT.md` |
| gameplay, player controller, kinematic controller, controls, input, 3D camera, orbit camera, combat, hitbox, hurtbox, weapon trace, projectile, lead target, physics, raycast, collision, jump, dash | `.claude/agents/02_GAMEPLAY_ENGINEER.md` |
| shader, HLSL, ShaderGraph, toon, outline, material, Blender, bpy, rigging, skinning, FBX, pivot, LOD, texture atlas, import pipeline, VFX graph | `.claude/agents/03_TECH_ARTIST.md` |
| AI, enemy, FSM, behavior tree, NavMesh, NavMeshAgent, perception, sight cone, hearing, steering, pathfinding, aggro, squad | `.claude/agents/04_AI_DESIGNER.md` |
| stats, damage formula, armor, mitigation, progression, level curve, XP, loot table, config JSON, ScriptableObject data, balance, drop rate | `.claude/agents/05_ECONOMY_BALANCER.md` |
| profiling, profiler, memory leak, GC alloc, boxing, refactor, performance, frame spike, draw call audit, performance code review, benchmark | `.claude/agents/06_QA_PROFILER.md` |
| pipeline, handoff, conflicts between roles, priorities, feature implementation order | `.claude/agents/SYSTEM_ORCHESTRATOR.md` |

Disambiguation rules:
- Match by **meaning**, not by exact string, and in any language (user prompts may be in Vietnamese).
- Keywords matching several roles → the role with the **narrower** scope leads; the broader role reviews.
- No role matches → ask the user one question; do not pick on your own.
- When starting a reply, print one line: `[ROLE: 02_GAMEPLAY_ENGINEER] — matched on: "lead target", "projectile"`.

---

## 5. Handoff Protocol (summary — details in `SYSTEM_ORCHESTRATOR.md`)

A new feature goes through 4 phases in order; each phase ends with a **Handoff Artifact** (schema in `SYSTEM_ORCHESTRATOR.md §3`):

```
Phase 1  Architecture Spec        01_GAME_ARCHITECT
   ↓     (interfaces, events, asmdef, ADR)
Phase 2  Implementation           02_GAMEPLAY_ENGINEER  ∥  03_TECH_ARTIST  ∥  04_AI_DESIGNER
   ↓     (code + assets + shaders; parallel if they do not share files)
Phase 3  Economy Injection        05_ECONOMY_BALANCER
   ↓     (SO/JSON, formulas, data tables — replace every magic constant)
Phase 4  QA Profiler Audit        06_QA_PROFILER
         (10-point audit, Profiler measurements, PASS/FAIL verdict)
```

No phase skipping. Phase N+1 starts only when the phase N artifact exists with `status: READY`. QA `FAIL` → return to the phase that caused it, with the list of violations as `file:line`.

---

## 6. Self-Healing Loop

Before declaring any code change done, run the loop below. Do not hand over while the loop is not green.

```
1. Run:          bash scripts/verify.sh
2. If exit 0:    record the result (tests passed, warnings) → hand over.
3. If exit ≠ 0:
   a. Read the FULL output; identify the FIRST root error (later errors are usually consequences).
   b. For a stack trace: take the first frame located in `Assets/` or `src/` (skip engine/BCL frames).
   c. Read that file:line and the 30 lines around it; state the suspected cause in 1 sentence.
   d. Fix the CAUSE, not the symptom (forbidden: wrapping in try/catch to swallow the error, adding a null-check that hides an initialization-order bug, disabling a test, lowering the warning level).
   e. Go back to step 1.
4. Limit: at most 5 rounds. Still red on round 5 → stop and report: commands run, root error, the 2 remaining hypotheses, files changed. Do not keep guessing.
```

`scripts/verify.sh` probes the environment in this order: (1) template structure integrity and the 6-section frame of the role files; (2) syntax of `scripts/*.py`; (3) if a `*.sln` exists → `dotnet build -warnaserror` (and `dotnet test` for pure .NET test projects); with no `.sln` but `UNITY_PATH` set → Unity batchmode EditMode tests; (4) when `Assets/` exists → `python scripts/audit_hotpath.py Assets`.

Exit codes: `0` green (including a template repo with no source yet) · `1` failure · `3` **`Assets/` exists but there is no way to verify the build** (no `.sln` and no `UNITY_PATH`). Exit `3` is **not green**: do not hand over and do not tick tasks; tell the user how to provide the missing environment.

---

## 7. Default Behavior

- Keep replies concise; code in fenced blocks with a language; paths as `path:line`.
- Do not create files outside the structure in §2 unless asked.
- Never put gameplay constants (damage, speed, cooldown) in code — they belong to `05_ECONOMY_BALANCER` (ScriptableObject/JSON).
- Every new architectural decision → add an ADR to `docs/context/CONTRACTS_ADR.md`.
- Small commits, Conventional Commits messages (`feat:`, `fix:`, `perf:`, `docs:`, `refactor:`).
