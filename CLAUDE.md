# CLAUDE.md — Root Router & Session Engine

> File này được Claude Code nạp tự động ở mỗi session. Nó là **router**, không phải nơi chứa chi tiết. Chi tiết nằm ở `docs/context/` (trạng thái dự án) và `.claude/agents/` (vai trò chuyên biệt). Không nhân bản nội dung của các file đó vào đây.

---

## 1. Core Engineering Invariants

Các bất biến dưới đây áp dụng cho MỌI đoạn code sinh ra, bất kể role. Vi phạm = code bị từ chối ở pha QA.

### 1.1 Zero-GC trong hot path

Hot path = `Update()`, `LateUpdate()`, `FixedUpdate()`, `IState.Tick/FixedTick`, `BTNode.Tick`, mọi callback từ Physics, và mọi hàm được gọi từ chúng.

| Cấm trong hot path | Thay bằng |
|---|---|
| `new` class/array/`List<T>`/`Dictionary` | Cấp phát sẵn ở `Awake`/`OnSpawnFromPool`, tái sử dụng bằng `Clear()` |
| Boxing (`object`, `IComparable` non-generic, `string.Format` với value type, `enum.ToString()`, `enum.HasFlag` trên runtime cũ) | Generic constraint `where T : struct`, so sánh bit thủ công `(flags & mask) != 0` |
| LINQ (`Where`, `Select`, `Any`, `ToList`, `OrderBy`) | `for` loop trên `List<T>`/mảng, index-based |
| `foreach` trên `IEnumerable<T>` / interface | `for` với index, hoặc `foreach` trên `List<T>` (struct enumerator, không alloc) |
| Nối chuỗi `"a" + b`, `$"..."`, `string.Format` | `StringBuilder` cache sẵn, `TMP_Text.SetText(fmt, arg)`, hoặc cache `string[]` cho số nguyên nhỏ |
| Lambda/anonymous delegate bắt biến (closure) | `static` lambda, delegate cache ở field, hoặc method group cache một lần |
| `GetComponent<T>()`, `Camera.main`, `FindObjectOfType`, `GameObject.Find`, `tag ==` | Cache ở `Awake`; dùng `CompareTag`; inject qua reference |
| `Physics.RaycastAll`, `SphereCastAll`, `OverlapSphere` | Bản `NonAlloc` với buffer cấp trước |
| `Vector3[]`/`Mesh.vertices`/`Mesh.normals` getter | `Mesh.GetVertices(List<Vector3>)`, `Mesh.AcquireReadOnlyMeshData` |
| Coroutine `yield return new WaitForSeconds(x)` | Cache `WaitForSeconds` ở field; ưu tiên timer float trong `Tick` |
| `Debug.Log` không bọc | `[Conditional("UNITY_EDITOR")]` hoặc `[Conditional("ENABLE_LOG")]` wrapper |

Ngân sách: **0 byte managed allocation mỗi frame** ở trạng thái ổn định (đo bằng Profiler → GC Alloc column = 0 B).

### 1.2 Object Pooling bắt buộc

Mọi thực thể sinh/hủy động phải đi qua pool và implement `IPoolable` (xem `docs/context/CONTRACTS_ADR.md`):

- Projectiles, Hit VFX, Muzzle flash, Damage popups, Decals, SFX one-shot emitters.
- Enemies (kể cả khi wave < 10 — pool là quy tắc, không phải tối ưu sớm).
- Cấm `Instantiate`/`Destroy` trong gameplay loop. `Instantiate` chỉ hợp lệ trong `Pool.Prewarm()` lúc loading.
- Pool phải có `maxSize`; khi vượt ngưỡng: tái chế thực thể cũ nhất (hoặc từ chối spawn), KHÔNG âm thầm `Instantiate` thêm.

### 1.3 Toán học 3D

- **Rotation = `Quaternion`.** Không cộng/trừ `eulerAngles` để xoay liên tục. Tích lũy góc yaw/pitch dưới dạng `float` riêng (đã `Clamp` pitch), rồi dựng `Quaternion.AngleAxis(yaw, Vector3.up) * Quaternion.AngleAxis(pitch, Vector3.right)`.
- Hướng: dùng `transform.forward/right/up`, `Vector3.Dot`, `Vector3.Cross`, `Vector3.SignedAngle`, `Quaternion.LookRotation`, `Quaternion.RotateTowards`, `Quaternion.Slerp` (hoặc `SlerpUnclamped` khi có kiểm soát).
- So sánh khoảng cách dùng `sqrMagnitude`; chỉ gọi `magnitude`/`Distance` khi cần giá trị thực.
- Chuẩn hóa: kiểm tra `sqrMagnitude > 1e-8f` trước khi `normalized` để tránh NaN/zero vector. Dùng `Vector3.ClampMagnitude`, `Vector3.ProjectOnPlane` cho chuyển động theo mặt phẳng.
- Không so sánh float bằng `==`. Dùng `Mathf.Approximately` hoặc epsilon tường minh.
- Chuyển động độc lập framerate: nhân `Time.deltaTime` (Update) hoặc `Time.fixedDeltaTime` (FixedUpdate); lerp mượt dùng `1f - Mathf.Exp(-k * dt)` thay vì `Lerp(a, b, 0.1f)`.
- Vật lý: đổi `Rigidbody.velocity`/`MovePosition`/`AddForce` chỉ trong `FixedUpdate`. Không di chuyển `Transform` của vật thể có `Rigidbody` không-kinematic.

### 1.4 Rendering budget

| Chỉ số | Ngân sách |
|---|---|
| Draw calls (SetPass + Batches) | **< 150** ở cảnh tham chiếu |
| Triangles nhân vật | ≤ 30k tris |
| Material trên mỗi nhân vật | ≤ 3 |
| Frame time | 16.6 ms (60 FPS khóa) |

Quy tắc: bật SRP Batcher (mọi shader phải tương thích — CBUFFER `UnityPerMaterial`), GPU Instancing cho props lặp (`#pragma multi_compile_instancing`), Static Batching cho môi trường tĩnh, dùng chung material, texture atlas, LOD group cho asset > 5k tris. Không `renderer.material` (tạo instance) — dùng `sharedMaterial` hoặc `MaterialPropertyBlock` (SRP Batcher tương thích khi dùng property block cần cân nhắc; ưu tiên `_BaseColor` per-instance qua instancing).

---

## 2. Directory Mapping

```
/
├── CLAUDE.md                          ← file này (router, luôn nạp)
├── README.md                          ← hướng dẫn dùng template
├── .gitignore
├── .gitattributes                     ← chuẩn hóa LF + Git LFS cho asset nhị phân
├── .claude/
│   ├── agents/
│   │   ├── SYSTEM_ORCHESTRATOR.md     ← pipeline 4 pha, handoff schema, conflict matrix
│   │   ├── 01_GAME_ARCHITECT.md       ← kiến trúc, pattern, event bus
│   │   ├── 02_GAMEPLAY_ENGINEER.md    ← gameplay, điều khiển, camera, combat, physics
│   │   ├── 03_TECH_ARTIST.md          ← shader, Blender, FBX pipeline
│   │   ├── 04_AI_DESIGNER.md          ← FSM, Behavior Tree, NavMesh, perception
│   │   ├── 05_ECONOMY_BALANCER.md     ← stats, công thức, progression, config
│   │   └── 06_QA_PROFILER.md          ← profiling, GC, memory leak, refactor
│   ├── commands/
│   │   └── handover.md                ← slash command /handover
│   └── local/                         ← (gitignored) log tạm của AI
├── docs/context/
│   ├── PROJECT_CONTEXT.md             ← nguồn sự thật duy nhất (engine, budget, convention)
│   ├── SESSION_LOG.md                 ← bộ nhớ ngoài giữa các session
│   ├── ROADMAP_BACKLOG.md             ← milestone + checklist + acceptance criteria
│   └── CONTRACTS_ADR.md               ← interface lõi + Architecture Decision Records
└── scripts/
    ├── verify.sh                      ← cổng build/test/audit cho Self-Healing Loop
    ├── audit_hotpath.py               ← quét hot path tìm vi phạm Zero-GC (ERROR chặn merge)
    └── blender_export_unity.py        ← chuẩn hóa pivot, freeze transform, xuất FBX Y-Up
```

Khi thêm file vào bất kỳ thư mục nào ở trên, cập nhật sơ đồ này trong cùng commit.

---

## 3. Session Lifecycle Protocol

### 3.1 Session Start (bắt buộc, trước khi xử lý bất kỳ task nào)

Đọc theo đúng thứ tự:

1. `docs/context/PROJECT_CONTEXT.md` — engine, budget, convention. Đây là nguồn sự thật; nếu xung đột với trí nhớ của bạn, file thắng.
2. `docs/context/SESSION_LOG.md` — đọc block **mới nhất** (trên cùng) để biết nhánh hiện tại, milestone đang chạy, nợ kỹ thuật và **Exact Next 3 Steps**.
3. `docs/context/ROADMAP_BACKLOG.md` — xác định task `[ ]` đầu tiên của milestone đang active.

Sau đó báo lại người dùng đúng 4 dòng: nhánh hiện tại · milestone active · task kế tiếp · blocker (nếu có). Chưa viết code trước khi xong bước này.

Nếu task chạm tới interface/contract, đọc thêm `docs/context/CONTRACTS_ADR.md`.

### 3.2 Session End / Handover — lệnh `/handover`

Người dùng gõ `/handover` (định nghĩa ở `.claude/commands/handover.md`) hoặc Claude tự thực hiện khi thấy dấu hiệu kết thúc session. Trình tự cố định:

1. **Tick checklist:** trong `ROADMAP_BACKLOG.md`, đổi `[ ]` → `[x]` cho từng task mà Acceptance Criteria đã được kiểm chứng bằng lệnh/test thực tế. Task chưa đo được metric thì KHÔNG tick.
2. **Ghi diff tóm tắt:** chạy `git diff --stat` và `git log --oneline` từ đầu session; tóm tắt theo file/module vào mục *Work Completed in Session*.
3. **Ghi nợ kỹ thuật/bug** phát hiện được vào *Technical Debt / Bugs Discovered* (kèm file:line).
4. **Ghi Exact Next 3 Steps:** 3 hành động cụ thể, mỗi hành động đủ nhỏ để làm trong một session, có đường dẫn file và tiêu chí xong.
5. **Thêm block mới lên đầu** `SESSION_LOG.md` (không sửa block cũ). Tăng số session.
6. Commit: `docs(session): handover session NN` và báo hash commit cho người dùng.

### 3.3 Quy tắc bảo trì context

- `PROJECT_CONTEXT.md` chỉ sửa khi thay đổi quyết định cấp dự án; ghi lý do vào ADR.
- `SESSION_LOG.md` là append-only theo block (mới nhất ở trên).
- Không dán code dài vào `SESSION_LOG.md`; chỉ tham chiếu `path:line` hoặc commit hash.

---

## 4. Dynamic Role Routing Table

**Luật cứng:** trước khi sinh bất kỳ dòng code nào, xác định intent, **đọc file role tương ứng bằng công cụ Read**, rồi mới làm việc theo đúng khung role đó. Task đa-intent → đọc `SYSTEM_ORCHESTRATOR.md` trước, sau đó đọc từng role theo thứ tự pipeline.

| Từ khóa / ngữ cảnh tác vụ | Role file (đọc trước khi code) |
|---|---|
| kiến trúc, design pattern, event bus, message broker, dependency injection, service locator, assembly definition, module boundary, save/load architecture, scene management | `.claude/agents/01_GAME_ARCHITECT.md` |
| gameplay, player controller, kinematic controller, điều khiển, input, camera 3D, orbit camera, combat, hitbox, hurtbox, weapon trace, projectile, lead target, physics, raycast, collision, jump, dash | `.claude/agents/02_GAMEPLAY_ENGINEER.md` |
| shader, HLSL, ShaderGraph, toon, outline, material, Blender, bpy, rigging, skinning, FBX, pivot, LOD, texture atlas, import pipeline, VFX graph | `.claude/agents/03_TECH_ARTIST.md` |
| AI, enemy, FSM, behavior tree, NavMesh, NavMeshAgent, perception, sight cone, hearing, steering, pathfinding, aggro, squad | `.claude/agents/04_AI_DESIGNER.md` |
| stats, damage formula, armor, mitigation, progression, level curve, XP, loot table, config JSON, ScriptableObject data, balance, drop rate | `.claude/agents/05_ECONOMY_BALANCER.md` |
| profiling, profiler, memory leak, GC alloc, boxing, refactor, performance, frame spike, draw call audit, code review hiệu năng, benchmark | `.claude/agents/06_QA_PROFILER.md` |
| pipeline, handoff, xung đột giữa các role, ưu tiên, thứ tự triển khai feature | `.claude/agents/SYSTEM_ORCHESTRATOR.md` |

Quy tắc phân giải mơ hồ:
- Từ khóa khớp nhiều role → role có phạm vi **hẹp hơn** dẫn dắt, role rộng hơn review.
- Không khớp role nào → hỏi lại người dùng một câu, không tự chọn.
- Khi bắt đầu phản hồi, in một dòng: `[ROLE: 02_GAMEPLAY_ENGINEER] — lý do khớp: "lead target", "projectile"`.

---

## 5. Handoff Protocol (tóm tắt — chi tiết ở `SYSTEM_ORCHESTRATOR.md`)

Feature mới đi qua 4 pha theo thứ tự, mỗi pha kết thúc bằng một **Handoff Artifact** (schema trong `SYSTEM_ORCHESTRATOR.md §3`):

```
Pha 1  Architecture Spec        01_GAME_ARCHITECT
   ↓   (interface, event, asmdef, ADR)
Pha 2  Implementation           02_GAMEPLAY_ENGINEER  ∥  03_TECH_ARTIST  ∥  04_AI_DESIGNER
   ↓   (code + asset + shader; chạy song song nếu không chia sẻ file)
Pha 3  Economy Injection        05_ECONOMY_BALANCER
   ↓   (SO/JSON, công thức, bảng số liệu — thay mọi hằng số magic)
Pha 4  QA Profiler Audit        06_QA_PROFILER
       (audit 10 điểm, số đo Profiler, verdict PASS/FAIL)
```

Không nhảy pha. Pha N+1 chỉ bắt đầu khi artifact của pha N tồn tại và pass `status: READY`. QA `FAIL` → trả về pha gây lỗi kèm danh sách vi phạm `file:line`.

---

## 6. Self-Healing Loop

Trước khi tuyên bố xong bất kỳ thay đổi code nào, chạy vòng lặp sau. Không bàn giao khi vòng lặp chưa xanh.

```
1. Chạy:        bash scripts/verify.sh
2. Nếu exit 0:  ghi kết quả (số test pass, warning) → bàn giao.
3. Nếu exit ≠ 0:
   a. Đọc TOÀN BỘ output; xác định lỗi GỐC đầu tiên (lỗi sau thường là hệ quả).
   b. Với stack trace: lấy frame đầu tiên nằm trong `Assets/` hoặc `src/` (bỏ frame của engine/BCL).
   c. Đọc file:line đó và 30 dòng xung quanh; nêu giả thuyết nguyên nhân trong 1 câu.
   d. Sửa NGUYÊN NHÂN, không sửa triệu chứng (cấm: bọc try/catch nuốt lỗi, thêm null-check che lỗi thứ tự khởi tạo, tắt test, hạ warning level).
   e. Quay lại bước 1.
4. Giới hạn: tối đa 5 vòng. Vòng 5 vẫn đỏ → dừng, báo cáo: lệnh đã chạy, lỗi gốc, 2 giả thuyết còn lại, file đã sửa. Không tiếp tục đoán mò.
```

`scripts/verify.sh` tự dò môi trường theo thứ tự: (1) kiểm tra toàn vẹn cấu trúc template và khung 6 mục của role file; (2) cú pháp `scripts/*.py`; (3) nếu có `*.sln` → `dotnet build -warnaserror` (và `dotnet test` cho dự án test .NET thuần); nếu không có `.sln` nhưng có `UNITY_PATH` → Unity batchmode EditMode tests; (4) khi có `Assets/` → `python scripts/audit_hotpath.py Assets`.

Mã thoát: `0` xanh (kể cả repo template chưa có source) · `1` lỗi · `3` **có `Assets/` nhưng không có cách xác minh build** (thiếu `.sln` lẫn `UNITY_PATH`). Mã `3` **không phải xanh**: không được bàn giao và không được tick task; báo người dùng cách bổ sung môi trường.

---

## 7. Hành vi mặc định

- Trả lời ngắn gọn; code trong block có ngôn ngữ; đường dẫn dạng `path:line`.
- Không tạo file ngoài cấu trúc ở §2 nếu không được yêu cầu.
- Không đưa hằng số gameplay (damage, speed, cooldown) vào code — chúng thuộc `05_ECONOMY_BALANCER` (ScriptableObject/JSON).
- Mọi quyết định kiến trúc mới → thêm ADR vào `docs/context/CONTRACTS_ADR.md`.
- Commit nhỏ, message theo Conventional Commits (`feat:`, `fix:`, `perf:`, `docs:`, `refactor:`).
