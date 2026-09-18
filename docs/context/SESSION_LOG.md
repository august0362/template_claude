# SESSION_LOG.md — External Memory Ledger

> Bộ nhớ ngoài giữa các session. **Append-only theo block; block mới nhất nằm trên cùng.** Không sửa block cũ. Không dán code dài — chỉ tham chiếu `path:line` hoặc commit hash.
> Claude đọc block trên cùng ở Session Start và ghi block mới ở `/handover`.

---

## Template (sao chép nguyên khối, điền, dán lên trên block gần nhất)

```markdown
## Session NN — <tiêu đề ngắn> — YYYY-MM-DD

| Trường | Giá trị |
|---|---|
| Current Branch | `<tên nhánh>` |
| Active Milestone | `M<n> — <tên>` |
| Base commit | `<hash đầu session>` |
| Head commit | `<hash cuối session>` |
| Verify status | `scripts/verify.sh` → PASS / FAIL (<n> vòng self-healing) |

### Work Completed in Session
- [x] <Task ID> — <mô tả> → `<path>` (AC đã đo: <số liệu>)
- Diff tóm tắt: <n> files changed, +<a> / −<d> (từ `git diff --stat`)

### Technical Debt / Bugs Discovered
- <severity: LOW/MED/HIGH> · `<path>:<line>` — <mô tả, hệ quả, hướng xử lý>
- (không có) nếu trống

### Exact Next 3 Steps
1. `<role>` — <hành động cụ thể> · file: `<path>` · xong khi: <tiêu chí đo được>
2. `<role>` — ...
3. `<role>` — ...
```

---

## Session 00 — Initial Setup — 2026-09-19

| Trường | Giá trị |
|---|---|
| Current Branch | `main` |
| Active Milestone | `M1 — Core Movement, Custom Kinematic Controller & 3D Orbit Camera` |
| Base commit | `(none — repository chưa có commit)` |
| Head commit | `(commit đầu tiên: "feat: initialize 3D game multi-agent & context engineering template")` |
| Verify status | `scripts/verify.sh` → PASS (không có source để build; script in cảnh báo và thoát 0) |

### Work Completed in Session
- [x] Khởi tạo cây thư mục: `docs/context/`, `.claude/agents/`, `.claude/commands/`, `scripts/`.
- [x] `CLAUDE.md` — router gốc: 4 nhóm bất biến kỹ thuật (Zero-GC, Pooling, Quaternion math, Draw call budget), Session Lifecycle, Routing Table, Handoff Protocol, Self-Healing Loop.
- [x] `docs/context/PROJECT_CONTEXT.md` — Unity 6 / C# 12 / URP; ngân sách 16.6 ms, 0 B alloc/frame, ≤ 150 draw calls, ≤ 30k tris; naming, asmdef DAG, layer matrix.
- [x] `docs/context/ROADMAP_BACKLOG.md` — 4 milestone (M1–M4), mỗi task có checkbox và Acceptance Criteria đo được.
- [x] `docs/context/CONTRACTS_ADR.md` — `IDamageable`/`DamageData`, `IPoolable`, `IState`; ADR-001 (Layer Matrix + NonAlloc raycast), ADR-002 (State Pattern).
- [x] `.claude/agents/SYSTEM_ORCHESTRATOR.md` + 6 role file (`01`–`06`) theo khung 6 mục.
- [x] `.claude/commands/handover.md`, `scripts/verify.sh`, `scripts/audit_hotpath.py` (đã thử trên mẫu vi phạm/sạch), `scripts/blender_export_unity.py` (đã kiểm tra cú pháp), `.gitignore`, `.gitattributes` (LF + Git LFS), `README.md`.
- Diff tóm tắt: repository mới, toàn bộ file là file thêm mới.

### Technical Debt / Bugs Discovered
- LOW · `docs/context/PROJECT_CONTEXT.md` — tên mã `Project Vanguard` và namespace `Vanguard.*` là giá trị mẫu; đổi bằng find-replace khi dùng template cho dự án thật.
- MED · Chưa có project Unity thật; code C# trong `CONTRACTS_ADR.md` và các role file **chưa được biên dịch hay chạy test** (không có Unity trong môi trường tạo template). Cần chép vào `Assets/_Project/Scripts/` ở M1-01, build và chạy các test đi kèm; lỗi biên dịch nếu có phải sửa ngay ở session đó.
- LOW · `scripts/blender_export_unity.py` mới kiểm tra cú pháp Python, chưa chạy trong Blender thật. Chạy thử với `--dry-run` rồi export một asset mẫu trước khi dùng cho asset thật.
- LOW · `.gitattributes` bật Git LFS cho `.fbx/.png/.wav/...`: mỗi máy phải chạy `git lfs install` một lần trước khi thêm asset nhị phân.

### Exact Next 3 Steps
1. `01_GAME_ARCHITECT` — Tạo project Unity 6 URP tại thư mục gốc, dựng các `.asmdef` theo `PROJECT_CONTEXT §3.3` và chép `IDamageable`/`IPoolable`/`IState` từ `CONTRACTS_ADR.md` vào `Assets/_Project/Scripts/Core/` · xong khi: project compile 0 error 0 warning (M1-01).
2. `01_GAME_ARCHITECT` — Cài `EventBus<T>` từ `01_GAME_ARCHITECT.md` vào `Vanguard.Core` kèm Performance Test 10,000 event/frame · xong khi: GC Alloc = 0 B (M1-02).
3. `02_GAMEPLAY_ENGINEER` — Dựng `InputActions` asset và `PlayerInputReader` phát `MoveInput`/`LookInput` qua bus · xong khi: Keyboard+Mouse và Gamepad chạy, 0 B GC Alloc (M1-04).
