# ROADMAP_BACKLOG.md — Milestones & Checklist

> Quy tắc: task chỉ được tick `[x]` khi **Acceptance Criteria (AC)** đã đo bằng công cụ/test thực tế và kết quả được ghi vào `SESSION_LOG.md`. Số liệu ngân sách tham chiếu `PROJECT_CONTEXT.md §2`.
> Kích thước: S ≤ 0.5 ngày · M ≈ 1–2 ngày · L ≈ 3–5 ngày.

**Milestone đang active:** `M1`

---

## M1 — Core Movement, Custom Kinematic Controller & 3D Orbit Camera

Mục tiêu: nhân vật di chuyển mượt, không xuyên tường, không rung, camera bám mượt và không xuyên vật thể. Zero-GC ngay từ đầu.

- [ ] **M1-01 · Assembly skeleton & Core contracts** (S) — `01_GAME_ARCHITECT`
  Tạo các `.asmdef` theo `PROJECT_CONTEXT §3.3`; đưa `IDamageable`, `IPoolable`, `IState` vào `Vanguard.Core`.
  **AC:** (1) Dự án compile 0 error, 0 warning với `-warnaserror`; (2) đồ thị asmdef không có vòng (kiểm bằng script `Editor` hoặc `dotnet build`); (3) 3 interface khớp chữ ký trong `CONTRACTS_ADR.md`.

- [ ] **M1-02 · Zero-GC Event Bus** (M) — `01_GAME_ARCHITECT`
  `EventBus<T> where T : struct` với dispatch không alloc.
  **AC:** (1) Publish 10,000 event/frame tới 8 subscriber → GC Alloc = 0 B (Performance Test); (2) unsubscribe trong lúc dispatch không gây `InvalidOperationException`; (3) độ trễ dispatch ≤ 0.05 ms cho 8 subscriber.

- [ ] **M1-03 · Generic Object Pool** (M) — `01_GAME_ARCHITECT`
  `ObjectPool<T> where T : Component, IPoolable` có prewarm, `maxSize`, chính sách tràn.
  **AC:** (1) `Get`/`Release` 100,000 vòng → GC Alloc = 0 B sau prewarm; (2) khi vượt `maxSize`, không `Instantiate` mới (assert bằng counter); (3) gọi `Release` hai lần cho cùng object không làm hỏng pool (test).

- [ ] **M1-04 · Input layer (Input System)** (S) — `02_GAMEPLAY_ENGINEER`
  `InputActions` asset, `PlayerInputReader` phát `struct MoveInput`/`LookInput` qua bus.
  **AC:** (1) Hỗ trợ Keyboard+Mouse và Gamepad; (2) deadzone 0.15 cho stick, kết quả ở [0,1]; (3) GC Alloc = 0 B mỗi frame khi giữ phím.

- [ ] **M1-05 · Custom Kinematic Character Controller** (L) — `02_GAMEPLAY_ENGINEER`
  Capsule sweep + collide-and-slide (tối đa 5 lần lặp), xử lý slope, step-up, ground snapping, không dùng `CharacterController` mặc định.
  **AC:** (1) Leo dốc ≤ 50°, trượt xuống dốc > 50°; (2) step-up bậc cao ≤ 0.3 m; (3) không xuyên tường ở vận tốc 25 m/s trong 60 giây test tự động (0 lần penetration); (4) `MoveAndSlide` ≤ 0.08 ms/frame; (5) 0 B GC Alloc.

- [ ] **M1-06 · Move / Jump / Dash state set** (M) — `02_GAMEPLAY_ENGINEER`
  `IdleState`, `RunState`, `JumpState`, `FallState`, `DashState` theo ADR-002. Coyote time & jump buffer.
  **AC:** (1) Coyote time 0.10 s và jump buffer 0.12 s, xác minh bằng PlayMode test có `Time.timeScale` cố định; (2) chuyển state không alloc; (3) dash quãng đường sai lệch ≤ 2% giữa 30 FPS và 144 FPS.

- [ ] **M1-07 · 3D Orbit Camera** (M) — `02_GAMEPLAY_ENGINEER`
  Yaw/pitch tích lũy dạng float, dựng bằng Quaternion, collision bằng SphereCast, damping độc lập framerate.
  **AC:** (1) Pitch bị kẹp [-30°, 70°]; không Gimbal Lock ở pitch biên (test 10,000 mẫu, `abs(Vector3.Dot(forward, up)) < 0.9397`); (2) camera không xuyên tường (SphereCast radius 0.25 m, 0 frame xuyên trong test đi sát tường); (3) độ mượt: jitter vị trí camera ≤ 0.5 mm giữa 60 FPS và 144 FPS; (4) 0 B GC Alloc.

- [ ] **M1-08 · Sandbox_Arena scene & QA gate M1** (S) — `06_QA_PROFILER`
  **AC:** (1) Frame time p99 ≤ 16.6 ms; (2) GC Alloc = 0 B trong 60 s di chuyển liên tục; (3) audit 10 điểm của `06_QA_PROFILER` = PASS.

---

## M2 — State-Driven Combat, Hitbox/Hurtbox & Weapon Trace System

Mục tiêu: chiến đấu dựa trên state, hit detection chính xác theo swept trace, dữ liệu vũ khí nằm ở SO.

- [ ] **M2-01 · Data schema vũ khí & combo** (M) — `05_ECONOMY_BALANCER`
  `WeaponDefinition` SO, `ComboStep`, JSON schema.
  **AC:** (1) SO round-trip JSON `ToJson → FromJson` bằng nhau 100% trên 50 mẫu; (2) không còn magic number damage/cooldown trong code Gameplay (grep = 0); (3) validate `OnValidate` chặn `damage < 0`, `windup ≤ 0`.

- [ ] **M2-02 · Armor Mitigation & Damage pipeline** (M) — `05_ECONOMY_BALANCER`
  Công thức giảm trừ theo giáp, crit, hệ sát thương.
  **AC:** (1) Với Armor=100, Constant=100 → mitigation = 50% (sai số ≤ 1e-4); (2) mitigation ∈ [0, 0.9] với mọi Armor ≥ 0; (3) 1,000,000 lần tính → 0 B GC Alloc; (4) bảng tra 20 giá trị Armor khớp công thức.

- [ ] **M2-03 · Hitbox/Hurtbox & Layer Matrix** (M) — `02_GAMEPLAY_ENGINEER`
  Áp dụng ADR-001; `Hurtbox` implement `IDamageable`; ma trận layer khai báo đúng `PROJECT_CONTEXT §3.4`.
  **AC:** (1) Ma trận collision khớp bảng (test tự động đọc `Physics.GetIgnoreLayerCollision`); (2) không dùng `OnTriggerStay`; (3) hit query dùng NonAlloc, 0 B GC Alloc.

- [ ] **M2-04 · Weapon Trace System (swept)** (L) — `02_GAMEPLAY_ENGINEER`
  Trace theo đoạn giữa vị trí socket frame trước và frame này (sub-step theo tốc độ), chống hit trùng trong cùng swing.
  **AC:** (1) Lưỡi kiếm quét 20 m/s không bỏ sót mục tiêu dày 0.1 m (1,000 lần thử, 0 miss); (2) mỗi mục tiêu chỉ nhận đúng 1 hit / swing; (3) ≤ 0.15 ms/frame với 5 trace socket; (4) 0 B GC Alloc.

- [ ] **M2-05 · Combat State Machine** (M) — `02_GAMEPLAY_ENGINEER`
  `AttackWindupState`, `AttackActiveState`, `AttackRecoveryState`, `HitStunState`, `BlockState`. Input buffer 0.15 s, cancel window.
  **AC:** (1) Số frame windup/active/recovery khớp SO (sai số 0 frame ở 60 FPS); (2) combo 3 đòn chain thành công khi nhấn trong cancel window, thất bại ngoài cửa sổ; (3) 0 B GC Alloc.

- [ ] **M2-06 · Projectile & Lead Target** (M) — `02_GAMEPLAY_ENGINEER`
  Pool đạn, thuật toán bắn đón đầu.
  **AC:** (1) Với mục tiêu chuyển động thẳng đều, sai lệch điểm chạm ≤ 0.05 m; (2) trả về `false` khi không có nghiệm (mục tiêu nhanh hơn đạn và đang chạy xa); (3) 200 projectile đồng thời → ≤ 0.3 ms/frame.

- [ ] **M2-07 · Damage popup & Hit VFX (pooled)** (S) — `03_TECH_ARTIST`
  **AC:** (1) 0 lần `Instantiate` trong gameplay (Profiler marker `Object.Instantiate` = 0); (2) VFX dùng chung 1 material, ≤ 2 draw call cho toàn bộ hit VFX; (3) popup text không alloc chuỗi (`SetText` overload).

- [ ] **M2-08 · QA gate M2** (S) — `06_QA_PROFILER`
  **AC:** (1) Audit 10 điểm PASS; (2) Frame p99 ≤ 16.6 ms khi 30 enemy đánh nhau (proxy dummy); (3) 0 GC.Collect trong 10 phút soak.

---

## M3 — Enemy AI Hierarchy (Behavior Tree, NavMesh, Spatial Perception)

Mục tiêu: enemy ra quyết định bằng Behavior Tree, nhận thức không gian rẻ, di chuyển NavMesh không tốn frame.

- [ ] **M3-01 · Behavior Tree core** (M) — `04_AI_DESIGNER`
  `BTNode`, `Sequence`, `Selector`, `Inverter`, `Cooldown`, `Action`, Blackboard dạng struct-typed key.
  **AC:** (1) Test truth table cho Sequence/Selector với Success/Failure/Running (≥ 12 case) pass; (2) node `Running` tiếp tục từ đúng con ở tick sau; (3) 1 tree 30 node tick ≤ 0.02 ms; (4) 0 B GC Alloc.

- [ ] **M3-02 · Spatial Perception** (M) — `04_AI_DESIGNER`
  Sight cone (dot product), hearing radius, line-of-sight bằng 1 raycast NonAlloc, tần suất cập nhật 10 Hz phân tán.
  **AC:** (1) Nhìn thấy mục tiêu khi `angle ≤ halfFOV` và `dist ≤ range` và không bị che (test 9 vị trí); (2) 30 enemy perception ≤ 0.4 ms/frame tổng; (3) raycast count/frame ≤ 4 nhờ time-slicing.

- [ ] **M3-03 · NavMesh agent integration** (M) — `04_AI_DESIGNER`
  `NavMeshAgent` với `updateRotation=false`, tự xoay bằng Quaternion; re-path có throttle.
  **AC:** (1) Enemy tới mục tiêu trong ≤ 0.3 m sai số; (2) `SetDestination` ≤ 2 lần/giây/agent; (3) 30 agent ≤ 1.2 ms/frame NavMesh update.

- [ ] **M3-04 · Enemy archetypes (Grunt, Archer, Brute)** (L) — `04_AI_DESIGNER`
  Mỗi archetype = 1 BT asset + 1 SO stats.
  **AC:** (1) Grunt: tiếp cận → tấn công cận chiến; Archer: giữ khoảng cách 8–12 m, bắn dùng Lead Target; Brute: charge khi thấy mục tiêu > 6 m; (2) mỗi archetype có test PlayMode mô tả hành vi; (3) không archetype nào hardcode chỉ số.

- [ ] **M3-05 · Aggro & Group coordination** (M) — `04_AI_DESIGNER`
  Token tấn công: tối đa 3 enemy tấn công đồng thời.
  **AC:** (1) Với 10 enemy, tại mọi thời điểm ≤ 3 enemy ở trạng thái Attack (assert trong test 5 phút); (2) enemy không được cấp token quay vòng (orbit) ở bán kính 4–6 m; (3) 0 B GC Alloc.

- [ ] **M3-06 · Enemy stats & scaling** (S) — `05_ECONOMY_BALANCER`
  **AC:** (1) HP/Damage theo level lấy từ `ProgressionCurve` SO; (2) bảng cân bằng cho level 1–30 xuất CSV; (3) time-to-kill mục tiêu: Grunt 3–4 đòn ở level ngang bằng.

- [ ] **M3-07 · QA gate M3** (S) — `06_QA_PROFILER`
  **AC:** (1) 50 enemy đồng thời: frame p99 ≤ 16.6 ms; (2) 0 B GC Alloc; (3) không leak: số object `EnemyController` sau 100 wave spawn/despawn = số ban đầu (Memory Profiler diff).

---

## M4 — Profiling, Memory Optimization & Draw Call Batching

Mục tiêu: khóa cứng ngân sách, chốt build phát hành ứng viên.

- [ ] **M4-01 · Baseline profiling capture** (S) — `06_QA_PROFILER`
  **AC:** Có 3 capture (`.data`) cho Sandbox_Arena kèm bảng số liệu: CPU ms, render ms, batches, SetPass, tris, GC Alloc, managed heap — lưu ở `docs/perf/`.

- [ ] **M4-02 · GC audit toàn codebase** (M) — `06_QA_PROFILER`
  **AC:** (1) Grep/Roslyn analyzer không còn LINQ, `GetComponent`, `Camera.main`, string concat trong hot path; (2) Profiler 5 phút gameplay: GC Alloc = 0 B/frame; (3) 0 GC.Collect.

- [ ] **M4-03 · SRP Batcher & GPU Instancing pass** (M) — `03_TECH_ARTIST`
  **AC:** (1) 100% shader dự án SRP Batcher compatible (Inspector báo "compatible"); (2) props lặp dùng Instancing; (3) Batches giảm ≥ 30% so với baseline M4-01.

- [ ] **M4-04 · LOD, atlas, static batching** (M) — `03_TECH_ARTIST`
  **AC:** (1) Nhân vật LOD0 ≤ 30k, LOD1 ≤ 12k, LOD2 ≤ 4k tris; (2) **Draw calls ≤ 150** tại 3 góc camera tham chiếu (Frame Debugger); (3) Tris ≤ 1.5M.

- [ ] **M4-05 · Memory leak sweep** (M) — `06_QA_PROFILER`
  **AC:** (1) Memory Profiler snapshot trước/sau 20 lần load/unload scene: chênh lệch managed ≤ 1 MB; (2) không còn subscriber dangling trên EventBus (test đếm handler = 0 sau unload); (3) texture/mesh runtime tạo ra đều được `Destroy`.

- [ ] **M4-06 · Physics & Animator budget** (S) — `02_GAMEPLAY_ENGINEER`
  **AC:** Physics ≤ 1.5 ms, Animator ≤ 1.0 ms với 30 enemy; Animator culling `CullUpdateTransforms` cho enemy ngoài màn hình.

- [ ] **M4-07 · Soak test 30 phút** (S) — `06_QA_PROFILER`
  **AC:** (1) 30 phút bot chơi tự động: 0 crash; (2) managed heap tăng ≤ 2 MB; (3) frame p99 ≤ 16.6 ms suốt phiên.

- [ ] **M4-08 · Release candidate sign-off** (S) — `SYSTEM_ORCHESTRATOR`
  **AC:** Toàn bộ AC của M1–M4 đã `[x]`; `scripts/verify.sh` xanh; báo cáo QA cuối cùng `PASS`.

---

## Backlog chưa xếp milestone

- [ ] Save/Load hệ thống (JSON + versioned migration) — `01_GAME_ARCHITECT` + `05_ECONOMY_BALANCER`
- [ ] Lock-on targeting (dot-product cone + nearest) — `02_GAMEPLAY_ENGINEER`
- [ ] Ragdoll blend-out khi chết (pooled) — `03_TECH_ARTIST`
- [ ] Loot table & drop rate — `05_ECONOMY_BALANCER`
