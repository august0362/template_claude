#!/usr/bin/env bash
# verify.sh — cổng kiểm chứng cho Self-Healing Loop (CLAUDE.md §6).
#
# Exit code:
#   0 = xanh (hoặc repo template chưa có source)
#   1 = lỗi cấu trúc / build / test / audit
#   3 = có source (Assets/) nhưng không có cách xác minh build (thiếu .sln lẫn UNITY_PATH)
#
# Biến môi trường:
#   UNITY_PATH  đường dẫn tới Unity.exe / Unity (để chạy EditMode test ở batchmode)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

status=0
note() { printf '[verify] %s\n' "$*"; }
fail() { printf '[verify][FAIL] %s\n' "$*" >&2; status=1; }
unverified() { printf '[verify][UNVERIFIED] %s\n' "$*" >&2; (( status == 0 )) && status=3; }

find_python() {
  local cand
  for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
      echo "$cand"
      return 0
    fi
  done
  return 1
}

# ── 1. Toàn vẹn cấu trúc template ────────────────────────────────────────────
required=(
  CLAUDE.md README.md .gitignore .gitattributes
  .claude/agents/SYSTEM_ORCHESTRATOR.md
  .claude/agents/01_GAME_ARCHITECT.md
  .claude/agents/02_GAMEPLAY_ENGINEER.md
  .claude/agents/03_TECH_ARTIST.md
  .claude/agents/04_AI_DESIGNER.md
  .claude/agents/05_ECONOMY_BALANCER.md
  .claude/agents/06_QA_PROFILER.md
  .claude/commands/handover.md
  docs/context/PROJECT_CONTEXT.md
  docs/context/SESSION_LOG.md
  docs/context/ROADMAP_BACKLOG.md
  docs/context/CONTRACTS_ADR.md
  scripts/verify.sh scripts/audit_hotpath.py scripts/blender_export_unity.py
)
for f in "${required[@]}"; do
  [[ -f "$f" ]] || fail "thiếu file bắt buộc: $f"
done

# Mỗi role file phải có đủ 6 mục theo khung bắt buộc.
for role in .claude/agents/0[1-6]_*.md; do
  [[ -f "$role" ]] || continue
  for n in 1 2 3 4 5 6; do
    grep -qE "^## ${n}\. " "$role" || fail "$role thiếu mục '## ${n}.'"
  done
done

# ── 2. Công cụ Python ────────────────────────────────────────────────────────
PY=""
if PY="$(find_python)"; then
  for f in scripts/*.py; do
    "$PY" -m py_compile "$f" 2>/dev/null || fail "lỗi cú pháp Python: $f"
  done
  find scripts -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null
else
  note "không tìm thấy Python: bỏ qua kiểm tra scripts/*.py và audit hot path."
fi

# ── 3. Build & test ──────────────────────────────────────────────────────────
has_source=0
[[ -d Assets ]] && has_source=1

slns=()
while IFS= read -r line; do slns+=("$line"); done < <(
  find . -maxdepth 2 -name '*.sln' -not -path './Library/*' -not -path './Temp/*' 2>/dev/null
)

if (( ${#slns[@]} > 0 )); then
  if command -v dotnet >/dev/null 2>&1; then
    for sln in "${slns[@]}"; do
      note "dotnet build -warnaserror $sln"
      dotnet build "$sln" -warnaserror --nologo -v q || fail "dotnet build lỗi: $sln"
    done
    # dotnet test chỉ áp dụng cho dự án test .NET thuần (Unity test assembly cần Unity runner).
    if grep -rqs "Microsoft.NET.Test.Sdk" --include='*.csproj' . 2>/dev/null; then
      for sln in "${slns[@]}"; do
        dotnet test "$sln" --no-build --nologo -v q || fail "dotnet test lỗi: $sln"
      done
    fi
  else
    unverified "có .sln nhưng không tìm thấy 'dotnet'."
  fi
elif [[ -n "${UNITY_PATH:-}" && -f ProjectSettings/ProjectVersion.txt ]]; then
  mkdir -p Logs
  note "Unity EditMode tests (batchmode)"
  "$UNITY_PATH" -batchmode -nographics -projectPath "$ROOT" \
    -runTests -testPlatform EditMode \
    -testResults "$ROOT/Logs/editmode-results.xml" \
    -logFile "$ROOT/Logs/unity-editmode.log" \
    || fail "Unity EditMode tests lỗi (xem Logs/unity-editmode.log, Logs/editmode-results.xml)"
elif (( has_source )); then
  unverified "có Assets/ nhưng không có .sln và không đặt UNITY_PATH — mở project trong IDE một lần để sinh .sln, hoặc export UNITY_PATH."
else
  note "chưa có source (repo template) — bỏ qua build/test."
fi

# ── 4. Audit Zero-GC hot path ────────────────────────────────────────────────
if (( has_source )) && [[ -n "$PY" ]]; then
  note "audit_hotpath.py Assets"
  PYTHONIOENCODING=utf-8 "$PY" scripts/audit_hotpath.py Assets || fail "audit_hotpath: có vi phạm ERROR"
fi

# ── Kết luận ─────────────────────────────────────────────────────────────────
case "$status" in
  0) note "PASS" ;;
  3) note "UNVERIFIED (không thể xác minh build)" ;;
  *) note "FAIL" ;;
esac
exit "$status"
