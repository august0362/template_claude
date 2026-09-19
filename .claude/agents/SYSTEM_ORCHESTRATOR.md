# SYSTEM_ORCHESTRATOR.md — Orchestration Pipeline

> Read this file when a task passes through ≥ 2 roles, when roles conflict, or when you need the handoff format. Read it first, then read each role in pipeline order.

---

## 1. The 4-phase pipeline

```
 Idea / Requirement
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ PHASE 1 — ARCHITECTURE SPEC                   01_GAME_ARCHITECT│
│  in  : feature request, PROJECT_CONTEXT, ROADMAP task          │
│  out : SPEC artifact (interfaces, event structs, asmdef, ADR)  │
│  gate: spec is self-consistent, keeps the asmdef DAG, ADR added│
└───────────────────────────────┬───────────────────────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ PHASE 2 — TECH ART & GAMEPLAY IMPLEMENTATION  (can be parallel)│
│   02_GAMEPLAY_ENGINEER  ∥  03_TECH_ARTIST  ∥  04_AI_DESIGNER   │
│  in  : SPEC artifact                                           │
│  out : IMPL artifact (code, prefabs, shaders, FBX, BT assets)  │
│  gate: compiles green, scripts/verify.sh exit 0, no magic nums │
└───────────────────────────────┬───────────────────────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ PHASE 3 — ECONOMY INJECTION                  05_ECONOMY_BALANCER│
│  in  : IMPL artifact + list of constants to externalize        │
│  out : DATA artifact (SO/JSON, formulas, balance tables)       │
│  gate: magic-number grep = 0, JSON round-trip pass, min/max ok │
└───────────────────────────────┬───────────────────────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ PHASE 4 — QA PROFILER AUDIT                      06_QA_PROFILER │
│  in  : IMPL + DATA artifacts                                   │
│  out : QA REPORT (10-point audit, Profiler numbers, verdict)   │
│  gate: PASS = merge; FAIL = return to the phase that caused it │
└───────────────────────────────────────────────────────────────┘
        │ FAIL ───────────► back to the owning phase (with file:line)
        ▼ PASS
   /handover → SESSION_LOG.md + tick ROADMAP
```

### Pipeline rules

1. **No phase skipping.** Phase N+1 starts only when the phase N artifact has `status: READY`.
2. **Phase 2 may run in parallel** only when the roles do not edit the same file. If they overlap, serialize in this order: 02 → 04 → 03.
3. **Shortcut exception** (small work only: ≤ 1 file, no interface change): skip Phases 1 and 3, but **Phase 4 is never skipped**.
4. **Feedback loop:** QA `FAIL` → create a `DEFECT` list, assign each to the role that owns the failing file; after the fix, re-run only the failed audit items and related ones (do not re-audit everything unless an interface was touched).
5. Each role prints `[ROLE: <name>] received artifact <id> (status: READY)` when it starts and `[ROLE: <name>] emitted artifact <id> (status: READY|BLOCKED)` when it finishes.

---

## 2. Ownership table

| Resource | Owner | Other roles may |
|---|---|---|
| `Vanguard.Core` (interfaces, EventBus, Pool) | 01 | read; propose via SPEC |
| `docs/context/CONTRACTS_ADR.md` | 01 | 06 may object with measurements |
| Player/Camera/Combat/Physics code | 02 | 06 reviews |
| Shaders, materials, Blender/FBX, import | 03 | 06 reviews draw calls |
| BT/FSM AI, NavMesh, perception | 04 | 02 provides state-reading interfaces |
| SO/JSON data, formulas, tables | 05 | every role **reads**, none edits constants |
| Profiling, audit, verdict | 06 | — |
| `PROJECT_CONTEXT.md` (budgets) | The user | 06 proposes budget changes with evidence |

Editing a file you do not own = **out-of-scope violation** → stop and create a `REQUEST` to the owner.

---

## 3. Handoff Artifact Schema

Every handoff is **one Markdown block with YAML front-matter + body**. Store it temporarily in `.claude/local/handoff/<id>.md` (gitignored) or paste it directly in the conversation. The official record of an architectural decision goes into an ADR.

### 3.1 Common schema (all artifact types)

```yaml
---
id: HO-<milestone>-<task>-<phase>      # e.g. HO-M2-04-P1
type: SPEC | IMPL | DATA | QA_REPORT | DEFECT | REQUEST
from: 01_GAME_ARCHITECT                # sending role
to: 02_GAMEPLAY_ENGINEER               # receiving role (or a list)
task: M2-04                            # ID in ROADMAP_BACKLOG
status: READY | BLOCKED | SUPERSEDED
created: 2026-09-19
depends_on: [HO-M2-03-P1]              # prerequisite artifacts (may be empty)
---
```

### 3.2 `SPEC` (Phase 1 → Phase 2)

```markdown
## Goal
<1–2 sentences, with a measurable target>

## Contracts
| Type | File (target path) | Assembly | Signature |
|---|---|---|---|
| interface | Assets/_Project/Scripts/Core/IHitReceiver.cs | Vanguard.Core | `float Receive(in HitInfo h)` |

## Events (struct messages on the EventBus)
| Struct | Fields | Publisher | Subscriber |
|---|---|---|---|
| WeaponHitEvent | DamageData Damage; int TargetId | WeaponTracer | DamagePopupSpawner, ComboMeter |

## Assembly / Dependency changes
- + `Vanguard.Combat` → refs: Core, Data
- DAG after the change: <list>, no cycles: ✔/✘

## Constraints
- Zero-GC: <relevant hot paths>
- Pool: <entities that use pooling>
- Budget: <relevant ms / draw calls>

## Out of scope
- <what this task does NOT do>

## Acceptance Criteria (from ROADMAP)
- <measurable AC>
```

### 3.3 `IMPL` (Phase 2 → Phase 3/4)

```markdown
## Changed files
| File | Type (A/M/D) | Notes |
|---|---|---|

## Externalized constants (for 05 to handle)
| Location | Current value | Meaning | Unit | Min | Max |
|---|---|---|---|---|---|
| WeaponTracer.cs:41 | 16 | hit buffer size | elements | 4 | 64 |

## Hot paths
| Function | Called from | Frequency | Expected alloc |
|---|---|---|---|

## Self-check
- scripts/verify.sh: exit 0 (<n> tests passed)
- Self-Healing Loop: <number of rounds>

## Known limitations
```

### 3.4 `DATA` (Phase 3 → Phase 4)

```markdown
## Assets
| Path | Type | Schema version |
|---|---|---|
| Assets/_Project/Data/SO_Weapon_Katana.asset | WeaponDefinition | 1 |

## Formulas (symbols + numeric example)
| Name | Formula | Domain | Example |
|---|---|---|---|
| Mitigation | A/(A+K) | A≥0, K>0 | A=100,K=100 → 0.5 |

## Balance table
<CSV/Markdown table: level, HP, dmg, TTK>

## Validation
- OnValidate rules: <list>
- JSON round-trip: pass/fail
```

### 3.5 `QA_REPORT` (Phase 4 → user / the phase that caused the failure)

```markdown
## Verdict: PASS | FAIL

## Measurements (Development Build, Sandbox_Arena)
| Metric | Budget | Measured | Met |
|---|---|---|---|
| Frame p99 (ms) | ≤ 16.6 | 14.2 | ✔ |
| GC Alloc / frame (B) | 0 | 0 | ✔ |
| Batches | ≤ 150 | 132 | ✔ |

## 10-point audit
| # | Item | Result | Evidence (file:line / capture) |
|---|---|---|---|

## Defects (if FAIL)
| ID | Severity | file:line | Description | Assigned to |
|---|---|---|---|---|
```

### 3.6 `DEFECT` / `REQUEST`

```markdown
## Violation / Request
- Clause: <CLAUDE.md §1.1 / PROJECT_CONTEXT §2 / ...>
- Location: <file:line>
- Evidence: <measurements, stack trace>
- Expected fix: <describe the behavior/target, do not write code for another role>
- Deadline: <task/milestone>
```

---

## 4. Conflict Resolution Matrix

When two roles make conflicting demands, apply the priority table **from top to bottom**; a higher row beats a lower row. The user always has the final say, but must be informed with a `TRADE-OFF NOTICE` (section 4.2).

### 4.1 Priority order

| Rank | Winning principle | Loses | Example |
|---|---|---|---|
| 1 | **Zero-GC & frame budget** | Convenience/speed of implementation | Gameplay wants LINQ `Where` to filter targets → QA requires `for` + a cached list. Winner: 06. |
| 2 | **Strict Interface Contracts** (CONTRACTS_ADR) | Ad-hoc local hacks | AI wants to call `PlayerController.health` directly → must go through `IDamageable`/events. Winner: 01. |
| 3 | **Correctness** (correct math, no NaN, no wall clipping) | Unmeasured micro-performance | Optimizing with `sqrMagnitude` while dropping the zero-vector check causes NaN → keep the check. Winner: 02. |
| 4 | **Profiler measurements** | Intuition/assumptions | "This spot is probably slow" but the capture shows nothing → do not optimize. Winner: 06 (evidence). |
| 5 | **Data-driven** (SO/JSON) | Constants embedded in code | Gameplay hardcodes `damage = 25` → move to an SO. Winner: 05. |
| 6 | **Draw call budget (≤ 150)** | Non-essential aesthetics | Artist wants 6 more materials per character → force it down to ≤ 3 with an atlas. Winner: 03 + 06 (03 owns the solution). |
| 7 | **Simplicity** | Premature generalization | Architecture adds an abstraction layer for a single use case → drop it. Winner: 02 (unless 01 proves ≥ 2 use cases). |
| 8 | **Speed of implementation** | — | May win only when ranks 1–7 are not violated. |

### 4.2 Conflict procedure

1. The role that detects a conflict emits a `REQUEST` citing the violated clause.
2. Look up table 4.1 → the higher rank wins. Same rank: **measurements** decide; with no measurements → measure first (06 runs the Profiler), then decide.
3. If the user asks for a rank 1–2 violation (e.g. "just use LINQ, it's faster to write"), the role **does not silently comply**: it issues a `TRADE-OFF NOTICE`:

```
TRADE-OFF NOTICE
Request: <...>
Violates: CLAUDE.md §1.1 (Zero-GC in the hot path)
Estimated cost: ~<n> B/frame → GC spike roughly every ~<t> seconds
Alternative: <one-line alternative>
If you still proceed: mark [DEBT-HIGH] in SESSION_LOG and open a repayment task in ROADMAP.
```

4. Implement only after the user explicitly confirms; always record the debt.

### 4.3 Common conflicts — pre-decided rulings

| Situation | Ruling |
|---|---|
| 02 wants to `Instantiate` bullets "for speed" | Forbidden. Use `ObjectPool`. (Rank 1) |
| 04 wants `NavMeshAgent.SetDestination` every frame | Forbidden. Throttle to ≤ 2 Hz/agent, only when the target moved > 0.5 m. (Rank 1) |
| 05 wants to change the `DamageData` signature to add a field | Route to 01: new ADR + update every implementer in the same commit. (Rank 2) |
| 03 wants a shader that uses `Texture2D.GetPixels` at runtime | Forbidden (large allocation). Use a RenderTexture/GPU. (Rank 1) |
| 06 finds a logic bug outside the audit scope | File a `DEFECT` for the owner; do not fix the logic yourself. |
| 02 and 04 both edit `EnemyController.cs` | Serialize: 02 finishes the state-reading interface, then 04 continues. |
| Two roles disagree on units (degrees vs radians) | Follow `PROJECT_CONTEXT`: store angles in degrees in SO/JSON, convert to radians at the calculation boundary. |

---

## 5. Triggering orchestration

When the user hands over a new feature, Claude does exactly this, in order:

1. Read `PROJECT_CONTEXT.md`, `SESSION_LOG.md`, `ROADMAP_BACKLOG.md` (Session Start).
2. Identify the task ID in ROADMAP; if none → ask the user whether to add it to ROADMAP.
3. Print the pipeline plan as a table: phase → role → output artifact → gate.
4. Execute each phase; after each phase print an artifact summary (do not paste the whole code if it was already written to a file).
5. After Phase 4 PASS → `/handover`.
