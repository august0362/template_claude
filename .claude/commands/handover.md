---
description: Kết thúc session — tick ROADMAP, ghi diff, nợ kỹ thuật và Exact Next 3 Steps vào SESSION_LOG.md
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git rev-parse:*), Bash(git add:*), Bash(git commit:*), Bash(bash scripts/verify.sh:*), Read, Edit
---

# /handover — Session End Protocol

Ngữ cảnh tự động thu thập lúc gọi lệnh:

- Nhánh hiện tại: !`git rev-parse --abbrev-ref HEAD`
- Trạng thái làm việc: !`git status --short`
- Thống kê thay đổi so với HEAD: !`git diff --stat HEAD`
- 20 commit gần nhất: !`git log --oneline -20`

Ghi chú thêm từ người dùng (có thể trống): $ARGUMENTS

Thực hiện **đúng thứ tự**, không bỏ bước:

## 1. Kiểm chứng trước khi chốt

Chạy `bash scripts/verify.sh`. Nếu exit ≠ 0 → chạy Self-Healing Loop (CLAUDE.md §6) tới khi xanh hoặc hết 5 vòng. Không tick task nào khi verify đang đỏ; ghi trạng thái thật vào bảng *Verify status*.

## 2. Tick checklist trong `docs/context/ROADMAP_BACKLOG.md`

- Đổi `[ ]` → `[x]` **chỉ** cho task mà *mọi* điều kiện trong Acceptance Criteria đã được đo/kiểm bằng lệnh, test hoặc số đo Profiler thực tế trong session này.
- Task làm dở hoặc chưa đo được metric: **giữ `[ ]`**, ghi phần đã xong vào *Work Completed* (không tick nửa vời).
- Không sửa nội dung AC. Nếu AC sai/thiếu, ghi vào *Technical Debt / Bugs Discovered* và hỏi người dùng.

## 3. Ghi block mới lên ĐẦU `docs/context/SESSION_LOG.md`

- Đọc block trên cùng để lấy số session hiện tại; block mới = số đó + 1 (định dạng `NN` hai chữ số).
- Dùng đúng template trong file: Current Branch, Active Milestone, Base/Head commit, Verify status, Work Completed in Session, Technical Debt / Bugs Discovered, Exact Next 3 Steps.
- **Work Completed:** mỗi mục có Task ID, đường dẫn file chính và số đo AC. Kèm dòng diff tóm tắt từ `git diff --stat` (số file, +/− dòng), không dán code.
- **Technical Debt / Bugs:** mỗi mục có mức độ (LOW/MED/HIGH), `path:line`, hệ quả và hướng xử lý. Ghi `(không có)` nếu trống.
- **Exact Next 3 Steps:** đúng 3 hành động; mỗi hành động gồm role phụ trách, việc cụ thể đủ nhỏ để làm trong một session, đường dẫn file, và tiêu chí xong đo được.
- **Không sửa block cũ.** Nếu milestone đã hoàn tất mọi task, cập nhật dòng `Milestone đang active` ở đầu `ROADMAP_BACKLOG.md`.

## 4. Commit

```
git add docs/context/ROADMAP_BACKLOG.md docs/context/SESSION_LOG.md
git commit -m "docs(session): handover session NN"
```

Nếu có thay đổi code chưa commit, hỏi người dùng có muốn commit riêng (`feat:`/`fix:`/`perf:`) trước khi handover hay không; không gộp code vào commit `docs(session)`.

## 5. Báo cáo cho người dùng (tối đa 8 dòng)

Hash commit handover · các task đã tick (ID) · verify PASS/FAIL · số nợ kỹ thuật mới · Exact Next 3 Steps (nhắc lại đúng như đã ghi).
