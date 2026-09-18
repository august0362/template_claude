# SYSTEM_ORCHESTRATOR.md — Orchestration Pipeline

> Đọc file này khi tác vụ đi qua ≥ 2 role, khi có xung đột giữa các role, hoặc khi cần biết định dạng bàn giao. Đọc trước, sau đó mới đọc từng role theo thứ tự pipeline.

---

## 1. Pipeline 4 pha

```
 Ý tưởng / Yêu cầu
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ PHA 1 — ARCHITECTURE SPEC                     01_GAME_ARCHITECT│
│  vào : yêu cầu feature, PROJECT_CONTEXT, ROADMAP task          │
│  ra  : SPEC artifact (interface, event struct, asmdef, ADR)    │
│  cổng: spec tự nhất quán, không phá DAG asmdef, có ADR nếu cần │
└───────────────────────────────┬───────────────────────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ PHA 2 — TECH ART & GAMEPLAY IMPLEMENTATION  (song song được)   │
│   02_GAMEPLAY_ENGINEER  ∥  03_TECH_ARTIST  ∥  04_AI_DESIGNER   │
│  vào : SPEC artifact                                           │
│  ra  : IMPL artifact (code, prefab, shader, FBX, BT asset)     │
│  cổng: compile xanh, scripts/verify.sh exit 0, không magic num │
└───────────────────────────────┬───────────────────────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ PHA 3 — ECONOMY INJECTION                    05_ECONOMY_BALANCER│
│  vào : IMPL artifact + danh sách hằng số cần ngoại hóa         │
│  ra  : DATA artifact (SO/JSON, công thức, bảng cân bằng)       │
│  cổng: grep magic number = 0, round-trip JSON pass, min/max ok │
└───────────────────────────────┬───────────────────────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ PHA 4 — QA PROFILER AUDIT                        06_QA_PROFILER │
│  vào : IMPL + DATA artifact                                    │
│  ra  : QA REPORT (audit 10 điểm, số đo Profiler, verdict)      │
│  cổng: PASS = merge; FAIL = trả về pha gây lỗi                 │
└───────────────────────────────────────────────────────────────┘
        │ FAIL ───────────► quay lại pha sở hữu lỗi (kèm file:line)
        ▼ PASS
   /handover → SESSION_LOG.md + tick ROADMAP
```

### Quy tắc pipeline

1. **Không nhảy pha.** Pha N+1 chỉ bắt đầu khi artifact pha N có `status: READY`.
2. **Song song ở pha 2** chỉ khi các role không sửa cùng file. Nếu trùng, tuần tự hóa theo thứ tự: 02 → 04 → 03.
3. **Ngoại lệ đường tắt** (chỉ cho việc nhỏ, ≤ 1 file, không đổi interface): bỏ qua Pha 1 và 3, nhưng **Pha 4 không bao giờ bỏ**.
4. **Vòng phản hồi:** QA `FAIL` → tạo `DEFECT` list, gán về role sở hữu file lỗi; sau khi sửa, chạy lại chỉ các mục audit bị FAIL và các mục liên quan (không audit lại toàn bộ trừ khi đụng interface).
5. Mỗi role, khi bắt đầu, in dòng `[ROLE: <tên>] nhận artifact <id> (status: READY)`. Khi xong in `[ROLE: <tên>] phát artifact <id> (status: READY|BLOCKED)`.

---

## 2. Bảng sở hữu (Ownership)

| Tài nguyên | Chủ sở hữu | Role khác được phép |
|---|---|---|
| `Vanguard.Core` (interface, EventBus, Pool) | 01 | đọc; đề xuất qua SPEC |
| `docs/context/CONTRACTS_ADR.md` | 01 | 06 có quyền phản đối kèm số đo |
| Player/Camera/Combat/Physics code | 02 | 06 review |
| Shader, material, Blender/FBX, import | 03 | 06 review draw call |
| BT/FSM AI, NavMesh, perception | 04 | 02 cung cấp interface đọc trạng thái |
| SO/JSON số liệu, công thức, bảng | 05 | mọi role **đọc**, không sửa hằng số |
| Profiling, audit, verdict | 06 | — |
| `PROJECT_CONTEXT.md` (ngân sách) | Người dùng | 06 đề xuất thay đổi ngân sách kèm bằng chứng |

Sửa file không thuộc quyền sở hữu = **out-of-scope violation** → phải dừng và tạo `REQUEST` tới chủ sở hữu.

---

## 3. Handoff Artifact Schema

Mọi bàn giao là **một khối Markdown có front-matter YAML + nội dung**. Lưu tạm ở `.claude/local/handoff/<id>.md` (gitignored) hoặc dán trực tiếp trong hội thoại. Bản chính thức của quyết định kiến trúc vào ADR.

### 3.1 Schema chung (mọi loại artifact)

```yaml
---
id: HO-<milestone>-<task>-<phase>      # ví dụ HO-M2-04-P1
type: SPEC | IMPL | DATA | QA_REPORT | DEFECT | REQUEST
from: 01_GAME_ARCHITECT                # role phát
to: 02_GAMEPLAY_ENGINEER               # role nhận (hoặc list)
task: M2-04                            # ID trong ROADMAP_BACKLOG
status: READY | BLOCKED | SUPERSEDED
created: 2026-09-19
depends_on: [HO-M2-03-P1]              # artifact tiên quyết (có thể rỗng)
---
```

### 3.2 `SPEC` (Pha 1 → Pha 2)

```markdown
## Goal
<1–2 câu, có số đo>

## Contracts
| Type | File (đường dẫn đích) | Assembly | Chữ ký |
|---|---|---|---|
| interface | Assets/_Project/Scripts/Core/IHitReceiver.cs | Vanguard.Core | `float Receive(in HitInfo h)` |

## Events (struct message trên EventBus)
| Struct | Trường | Publisher | Subscriber |
|---|---|---|---|
| WeaponHitEvent | DamageData Damage; int TargetId | WeaponTracer | DamagePopupSpawner, ComboMeter |

## Assembly / Dependency changes
- + `Vanguard.Combat` → refs: Core, Data
- Đồ thị DAG sau thay đổi: <liệt kê>, không vòng: ✔/✘

## Constraints
- Zero-GC: <hot path liên quan>
- Pool: <thực thể dùng pool>
- Budget: <ms / draw call liên quan>

## Out of scope
- <điều KHÔNG làm ở task này>

## Acceptance Criteria (lấy từ ROADMAP)
- <AC đo được>
```

### 3.3 `IMPL` (Pha 2 → Pha 3/4)

```markdown
## Changed files
| File | Loại (A/M/D) | Ghi chú |
|---|---|---|

## Externalized constants (cần 05 xử lý)
| Vị trí | Giá trị hiện tại | Ý nghĩa | Đơn vị | Min | Max |
|---|---|---|---|---|---|
| WeaponTracer.cs:41 | 16 | kích thước buffer hit | phần tử | 4 | 64 |

## Hot paths
| Hàm | Gọi từ | Tần suất | Alloc dự kiến |
|---|---|---|---|

## Self-check
- scripts/verify.sh: exit 0 (<n> test pass)
- Self-Healing Loop: <số vòng>

## Known limitations
```

### 3.4 `DATA` (Pha 3 → Pha 4)

```markdown
## Assets
| Path | Loại | Schema version |
|---|---|---|
| Assets/_Project/Data/SO_Weapon_Katana.asset | WeaponDefinition | 1 |

## Formulas (ký hiệu + ví dụ số)
| Tên | Công thức | Miền | Ví dụ |
|---|---|---|---|
| Mitigation | A/(A+K) | A≥0, K>0 | A=100,K=100 → 0.5 |

## Balance table
<bảng CSV/Markdown: level, HP, dmg, TTK>

## Validation
- OnValidate rules: <danh sách>
- JSON round-trip: pass/fail
```

### 3.5 `QA_REPORT` (Pha 4 → Người dùng/pha gây lỗi)

```markdown
## Verdict: PASS | FAIL

## Measurements (Development Build, Sandbox_Arena)
| Chỉ số | Ngân sách | Đo được | Đạt |
|---|---|---|---|
| Frame p99 (ms) | ≤ 16.6 | 14.2 | ✔ |
| GC Alloc / frame (B) | 0 | 0 | ✔ |
| Batches | ≤ 150 | 132 | ✔ |

## Audit 10 điểm
| # | Mục | Kết quả | Bằng chứng (file:line / capture) |
|---|---|---|---|

## Defects (nếu FAIL)
| ID | Severity | file:line | Mô tả | Gán cho |
|---|---|---|---|---|
```

### 3.6 `DEFECT` / `REQUEST`

```markdown
## Vi phạm / Yêu cầu
- Điều khoản: <CLAUDE.md §1.1 / PROJECT_CONTEXT §2 / ...>
- Vị trí: <file:line>
- Bằng chứng: <số đo, stack trace>
- Sửa mong đợi: <mô tả hành vi/đích, không viết code hộ role khác>
- Hạn: <task/milestone>
```

---

## 4. Conflict Resolution Matrix

Khi hai role đưa ra yêu cầu mâu thuẫn, áp dụng bảng ưu tiên **từ trên xuống**; dòng trên thắng dòng dưới. Người dùng luôn có quyền phán quyết cuối cùng, nhưng phải được thông báo bằng dạng `TRADE-OFF NOTICE` (mục 4.2).

### 4.1 Thứ tự ưu tiên

| Hạng | Nguyên tắc thắng | Thua | Ví dụ áp dụng |
|---|---|---|---|
| 1 | **Zero-GC & frame budget** | Tiện ích/nhanh triển khai | Gameplay muốn dùng LINQ `Where` cho lọc mục tiêu → QA buộc dùng `for` + list cache. Thắng: 06. |
| 2 | **Strict Interface Contracts** (CONTRACTS_ADR) | Hack cục bộ (ad-hoc) | AI muốn gọi thẳng `PlayerController.health` → buộc qua `IDamageable`/event. Thắng: 01. |
| 3 | **Correctness** (đúng toán, không NaN, không xuyên tường) | Hiệu năng vi mô chưa đo | Tối ưu `sqrMagnitude` bỏ kiểm tra zero-vector gây NaN → giữ kiểm tra. Thắng: 02. |
| 4 | **Số đo Profiler** | Trực giác/giả định | "Chỗ này chắc chậm" mà capture không thấy → không tối ưu. Thắng: 06 (bằng chứng). |
| 5 | **Data-driven** (SO/JSON) | Hằng số nhúng trong code | Gameplay hardcode `damage = 25` → chuyển sang SO. Thắng: 05. |
| 6 | **Draw call budget (≤ 150)** | Thẩm mỹ không thiết yếu | Artist muốn thêm 6 material/nhân vật → ép về ≤ 3, dùng atlas. Thắng: 03 + 06 (nhưng 03 sở hữu giải pháp). |
| 7 | **Độ đơn giản** | Tổng quát hóa sớm | Kiến trúc thêm lớp trừu tượng cho 1 use case → bỏ. Thắng: 02 (nếu 01 không chứng minh được ≥ 2 use case). |
| 8 | **Tốc độ triển khai** | — | Chỉ được ưu tiên khi hạng 1–7 không bị vi phạm. |

### 4.2 Thủ tục xung đột

1. Role phát hiện xung đột phát `REQUEST` kèm điều khoản bị vi phạm.
2. Tra bảng 4.1 → hạng cao hơn thắng. Nếu cùng hạng: **số đo** quyết định; không có số đo → đo trước (06 chạy Profiler), rồi quyết.
3. Nếu người dùng yêu cầu vi phạm hạng 1–2 (ví dụ "cứ dùng LINQ cho nhanh"), role **không im lặng làm theo**: phát `TRADE-OFF NOTICE`:

```
TRADE-OFF NOTICE
Yêu cầu: <...>
Vi phạm: CLAUDE.md §1.1 (Zero-GC trong hot path)
Chi phí ước tính: ~<n> B/frame → GC spike mỗi ~<t> giây
Phương án thay thế: <đoạn 1 dòng>
Nếu vẫn tiếp tục: đánh dấu [DEBT-HIGH] trong SESSION_LOG và mở task hoàn nợ trong ROADMAP.
```

4. Chỉ khi người dùng xác nhận tường minh mới triển khai; luôn ghi nợ.

### 4.3 Xung đột phổ biến — phán quyết sẵn

| Tình huống | Phán quyết |
|---|---|
| 02 muốn `Instantiate` đạn "cho nhanh" | Cấm. Dùng `ObjectPool`. (Hạng 1) |
| 04 muốn `NavMeshAgent.SetDestination` mỗi frame | Cấm. Throttle ≤ 2 Hz/agent, chỉ khi mục tiêu dịch > 0.5 m. (Hạng 1) |
| 05 muốn đổi chữ ký `DamageData` để thêm trường | Chuyển 01: ADR mới + cập nhật mọi implementer cùng commit. (Hạng 2) |
| 03 muốn Shader dùng `Texture2D.GetPixels` runtime | Cấm (alloc lớn). Dùng RenderTexture/GPU. (Hạng 1) |
| 06 phát hiện bug logic ngoài phạm vi audit | Ghi `DEFECT` cho chủ sở hữu, không tự sửa logic. |
| 02 và 04 cùng sửa `EnemyController.cs` | Tuần tự hóa: 02 hoàn tất giao diện đọc trạng thái, 04 làm tiếp. |
| Hai role khác nhau về đơn vị (độ vs radian) | Theo `PROJECT_CONTEXT`: góc lưu độ ở SO/JSON, chuyển radian ở biên tính toán. |

---

## 5. Kích hoạt orchestration

Khi người dùng giao một feature mới, Claude làm đúng theo thứ tự:

1. Đọc `PROJECT_CONTEXT.md`, `SESSION_LOG.md`, `ROADMAP_BACKLOG.md` (Session Start).
2. Xác định task ID trong ROADMAP; nếu không có → hỏi người dùng có thêm vào ROADMAP không.
3. In kế hoạch pipeline dạng bảng: pha → role → artifact đầu ra → cổng.
4. Thực thi từng pha; sau mỗi pha in tóm tắt artifact (không dán cả code nếu đã ghi vào file).
5. Sau Pha 4 PASS → `/handover`.
