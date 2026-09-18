# 3D Game — Multi-Agent & Spec-Driven Context Engineering Template

Repository mẫu để phát triển game 3D (mặc định **Unity 6 / C# 12 / URP**, dùng được cho Unreal khi đổi `PROJECT_CONTEXT.md`) cùng **Claude Code**, Cursor/Roo Code hoặc Claude Projects.

Ý tưởng cốt lõi: thay vì để AI "nhớ" dự án bằng hội thoại, mọi tri thức nằm trong file — **router** (`CLAUDE.md`), **6 vai trò chuyên biệt** (`.claude/agents/`), và **bộ nhớ ngoài** giữa các session (`docs/context/`). Mỗi session bắt đầu bằng việc đọc file và kết thúc bằng `/handover`.

---

## 1. Cấu trúc

```
├── CLAUDE.md                        Router: bất biến kỹ thuật, routing, vòng đời session, self-healing
├── .claude/
│   ├── agents/
│   │   ├── SYSTEM_ORCHESTRATOR.md   Pipeline 4 pha, schema bàn giao, ma trận xung đột
│   │   ├── 01_GAME_ARCHITECT.md     Kiến trúc, EventBus, ObjectPool
│   │   ├── 02_GAMEPLAY_ENGINEER.md  Controller, camera, combat, Lead Target
│   │   ├── 03_TECH_ARTIST.md        Shader HLSL, script Blender, pipeline FBX
│   │   ├── 04_AI_DESIGNER.md        Behavior Tree, perception, NavMesh
│   │   ├── 05_ECONOMY_BALANCER.md   Công thức giáp, progression, JSON schema
│   │   └── 06_QA_PROFILER.md        Audit 10 điểm, Zero-GC, profiling
│   └── commands/handover.md         Lệnh /handover
├── docs/context/
│   ├── PROJECT_CONTEXT.md           Nguồn sự thật: engine, ngân sách, quy ước, asmdef
│   ├── ROADMAP_BACKLOG.md           4 milestone, task có Acceptance Criteria đo được
│   ├── SESSION_LOG.md               Nhật ký session (append-only, mới nhất ở trên)
│   └── CONTRACTS_ADR.md             IDamageable, IPoolable, IState, ADR-001/002
└── scripts/
    ├── verify.sh                    Cổng build/test/audit cho self-healing loop
    ├── audit_hotpath.py             Quét hot path tìm vi phạm Zero-GC
    └── blender_export_unity.py      Chuẩn hóa pivot, freeze transform, xuất FBX Y-Up
```

---

## 2. Dùng repo này làm GitHub Template

**Bật chế độ Template** (một lần, trên repo gốc):

- Giao diện: **Settings → General → tick "Template repository"**.
- Hoặc CLI: `gh repo edit <owner>/<repo> --template`.

**Tạo dự án game mới từ template:**

```bash
# CLI (khuyến nghị)
gh repo create my-game --template <owner>/<repo> --private --clone
cd my-game

# Hoặc giao diện: nút "Use this template" → "Create a new repository"
```

Khác với fork, template tạo repo **không kèm lịch sử commit** của template — dự án mới bắt đầu sạch.

---

## 3. Sau khi clone — thiết lập một lần

```bash
# 1. Git LFS cho asset nhị phân (.fbx, .png, .wav, ...). BẮT BUỘC trước khi thêm asset.
git lfs install

# 2. Kiểm tra toàn vẹn template (cần bash + Python 3).
bash scripts/verify.sh

# 3. Đổi tên mã mẫu "Vanguard" (namespace, asmdef) sang tên dự án của bạn.
#    Sửa PROJECT_CONTEXT.md trước, rồi find-replace "Vanguard" trên toàn repo.

# 4. Tạo project Unity 6 (URP) tại thư mục gốc, dựng .asmdef theo PROJECT_CONTEXT §3.3.
#    Mở project trong IDE một lần để Unity sinh .sln (verify.sh dùng để dotnet build),
#    hoặc export UNITY_PATH để chạy EditMode test ở batchmode.
```

Dùng Unreal thay Unity: sửa `PROJECT_CONTEXT.md §1` (engine, ngôn ngữ) và ngân sách; các quy tắc Zero-GC/pooling/toán học vẫn áp dụng (thay ví dụ C# bằng C++ tương ứng khi cần).

---

## 4. Bắt đầu một session mới với Claude Code

```bash
claude
```

Claude tự nạp `CLAUDE.md`. Câu mở đầu khuyến nghị:

```
Bắt đầu session mới. Theo CLAUDE.md §3.1, đọc PROJECT_CONTEXT.md, SESSION_LOG.md (block mới nhất) và ROADMAP_BACKLOG.md, rồi báo lại đúng 4 dòng: nhánh hiện tại · milestone active · task kế tiếp · blocker.
```

Sau đó giao việc bằng ngôn ngữ tự nhiên — router sẽ chọn role:

```
Làm task M1-02: Zero-GC Event Bus.
```

Kích hoạt thẳng một role (mỗi role có "One-Line Activation Trigger" ở mục 6 của file của nó), ví dụ:

```
Kích hoạt QA_PROFILER: đọc .claude/agents/06_QA_PROFILER.md và PROJECT_CONTEXT.md (§2), rồi audit 10 điểm + đo Profiler cho: commit HEAD — chạy scripts/verify.sh và scripts/audit_hotpath.py, trả QA_REPORT.
```

**Kết thúc session:**

```
/handover
```

Lệnh này chạy `verify.sh`, tick checklist trong `ROADMAP_BACKLOG.md` (chỉ những task đã đo được Acceptance Criteria), ghi block mới lên đầu `SESSION_LOG.md` kèm **Exact Next 3 Steps**, rồi commit `docs(session): handover session NN`.

**Cursor / Roo Code / Claude Projects:** trỏ file rules/instructions về `CLAUDE.md`; với Claude Projects, tải lên `CLAUDE.md`, `docs/context/*` và `.claude/agents/*`.

---

## 5. Quy trình phát triển một feature

```
Pha 1  Architecture Spec        01_GAME_ARCHITECT
Pha 2  Implementation           02_GAMEPLAY_ENGINEER ∥ 03_TECH_ARTIST ∥ 04_AI_DESIGNER
Pha 3  Economy Injection        05_ECONOMY_BALANCER
Pha 4  QA Profiler Audit        06_QA_PROFILER   →  PASS: merge · FAIL: trả về pha gây lỗi
```

Chi tiết, schema bàn giao và ma trận phân xử xung đột: [.claude/agents/SYSTEM_ORCHESTRATOR.md](.claude/agents/SYSTEM_ORCHESTRATOR.md).

Bất biến kỹ thuật không thương lượng: **0 byte GC/frame** ở hot path · **Object Pooling** cho mọi thực thể động · **Quaternion** cho xoay · **≤ 150 draw call**, 16.6 ms/frame.

---

## 6. Kiểm chứng

```bash
bash scripts/verify.sh                       # cấu trúc + build/test + audit
python scripts/audit_hotpath.py Assets       # chỉ audit Zero-GC hot path
blender -b Scenes/Hero.blend -P scripts/blender_export_unity.py -- --out Assets/_Project/Art/Models --dry-run
```

Mã thoát của `verify.sh`: `0` xanh · `1` lỗi · `3` có source nhưng không thể xác minh build.

---

## 7. Lưu ý

- Code C# trong các file tài liệu là mã tham chiếu chưa được biên dịch trong một project Unity thật ở phiên bản template này; chép vào `Assets/_Project/Scripts/` ở task M1-01 và chạy test đi kèm để xác nhận.
- `scripts/audit_hotpath.py` là bộ quét dựa trên regex, không thay thế Profiler; xem giới hạn ở tiêu đề file.
- Chọn license phù hợp cho dự án của bạn trước khi công khai repo.
