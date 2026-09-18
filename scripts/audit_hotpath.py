#!/usr/bin/env python3
"""
audit_hotpath.py — quét thân hàm hot path trong *.cs và báo vi phạm Zero-GC.

Hot path = thân các hàm: Update, FixedUpdate, LateUpdate, Tick, FixedTick, OnTick, Evaluate,
OnTriggerStay, OnCollisionStay (đổi bằng --methods).

Cách dùng:
    python scripts/audit_hotpath.py [đường_dẫn ...]        # mặc định: Assets/
    python scripts/audit_hotpath.py --methods Update,Tick Assets/_Project/Scripts

Loại vi phạm:
    ERROR  → exit code 1 (chặn merge).
    WARN   → chỉ báo cáo; người review phải xác minh.

Bỏ qua có lý do (cùng dòng hoặc dòng ngay trên):
    // audit:ignore ALLOC-NEW <lý do>

Thư mục Editor/, Tests/, Library/, Temp/ (tính từ thư mục gốc được quét) bị bỏ qua.
"""
import argparse
import bisect
import pathlib
import re
import sys

DEFAULT_METHODS = ("Update,FixedUpdate,LateUpdate,Tick,FixedTick,OnTick,Evaluate,"
                   "OnTriggerStay,OnCollisionStay")

VALUE_TYPES = ("Vector2|Vector3|Vector4|Vector2Int|Vector3Int|Quaternion|Ray|Ray2D|Color|Color32|"
               "Bounds|Rect|Matrix4x4|LayerMask|RaycastHit|Plane|Keyframe|NativeArray|DamageData|"
               "WeaponHitEvent|LeadSolution|DefenseProfile")

# (id, mức, regex, thông điệp) — áp dụng trên văn bản đã bỏ comment và nội dung chuỗi.
RULES = [
    ("ALLOC-ARRAY", "ERROR", re.compile(r"\bnew\s+[\w\.<>]+\s*\["), "cấp phát mảng trong hot path"),
    ("ALLOC-NEW", "ERROR",
     re.compile(r"\bnew\s+(?!(?:" + VALUE_TYPES + r")\b)(?!WaitFor)[A-Za-z_][\w\.<>,]*\s*(?:\(|\{)"),
     "new kiểu tham chiếu trong hot path (dùng pool/cache)"),
    ("ALLOC-NEW-TARGET", "WARN", re.compile(r"\bnew\s*\(\s*\)"), "new() target-typed: xác minh là value type"),
    ("COROUTINE-WAIT", "ERROR", re.compile(r"\bnew\s+WaitFor\w+\s*\("), "new WaitFor* mỗi lần (cache ở field)"),
    ("LINQ", "ERROR",
     re.compile(r"\.(Where|Select|SelectMany|Any|All|First|FirstOrDefault|Last|LastOrDefault|Single|"
                r"ToList|ToArray|ToDictionary|OrderBy|OrderByDescending|GroupBy|Distinct|Zip|Aggregate)\s*\("),
     "LINQ/ToList/ToArray cấp phát"),
    ("STRING-CONCAT", "ERROR", re.compile(r'(\$"|\bstring\.Format\s*\(|"\s*\+|\+\s*")'),
     "nối/nội suy chuỗi cấp phát"),
    ("STRING-TOSTRING", "WARN", re.compile(r"\.ToString\s*\("), "ToString() cấp phát chuỗi"),
    ("LOOKUP", "ERROR",
     re.compile(r"\b(GetComponent(?:s|InChildren|InParent)?\s*[<\(]|FindObjectOfType|FindObjectsOfType|"
                r"FindFirstObjectByType|FindAnyObjectByType|GameObject\.Find|FindWithTag|Camera\.main|"
                r"Resources\.Load|SendMessage|BroadcastMessage)"),
     "tra cứu/Find/GetComponent trong hot path (cache ở Awake)"),
    ("TAG-COMPARE", "ERROR", re.compile(r"\.tag\s*[!=]="), "so sánh .tag cấp phát (dùng CompareTag)"),
    ("PHYSICS-ALLOC", "ERROR",
     re.compile(r"Physics\.(RaycastAll|SphereCastAll|CapsuleCastAll|BoxCastAll|OverlapSphere|OverlapBox|"
                r"OverlapCapsule)\s*\("),
     "truy vấn vật lý trả mảng mới (dùng bản NonAlloc + buffer cấp trước)"),
    ("INSTANTIATE", "ERROR", re.compile(r"\b(Instantiate|Destroy|DestroyImmediate)\s*\("),
     "Instantiate/Destroy trong hot path (dùng ObjectPool)"),
    ("MESH-GETTER", "ERROR",
     re.compile(r"\.(vertices|normals|tangents|uv|uv2|triangles|colors|bones|materials)\b(?!\s*=[^=])"),
     "getter trả bản sao mảng (dùng Get*(List) / sharedMaterials)"),
    ("MATERIAL-INSTANCE", "ERROR", re.compile(r"\.material\b(?!s|\s*=[^=])"),
     "renderer.material tạo instance (dùng sharedMaterial)"),
    ("CLOSURE", "WARN", re.compile(r"=>"), "lambda/local function: nếu bắt biến thì cấp phát closure"),
    ("FOREACH", "WARN", re.compile(r"\bforeach\s*\("), "foreach: chỉ an toàn trên mảng/List<T>"),
    ("LOG", "WARN", re.compile(r"\bDebug\.Log(?:Warning|Error)?\s*\("), "Debug.Log trong hot path (bọc [Conditional])"),
]

IGNORE = re.compile(r"audit:ignore\s+([A-Z\-]+)")
SKIPPED_DIRS = {"Editor", "Tests", "Library", "Temp"}


def blank(segment):
    """Thay mọi ký tự bằng khoảng trắng, giữ xuống dòng để không lệch số dòng/vị trí."""
    return "".join(ch if ch == "\n" else " " for ch in segment)


def sanitize(text):
    """Bỏ comment và nội dung chuỗi/char; giữ nguyên độ dài, dấu ngoặc kép và xuống dòng."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(blank(text[i:j]))
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(blank(text[i:j]))
            i = j
        elif text[i] in "\"'":
            quote = text[i]
            j = i + 1
            while j < n and text[j] != quote:
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(quote + blank(text[i + 1:j - 1]) + (quote if j - i >= 2 else ""))
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def find_bodies(clean, method_re):
    """Sinh (vị_trí_bắt_đầu, vị_trí_kết_thúc) ký tự của thân từng hàm hot path."""
    n = len(clean)
    for m in method_re.finditer(clean):
        i, depth = m.end(), 1                      # ngay sau '(' của danh sách tham số
        while i < n and depth:
            if clean[i] == "(":
                depth += 1
            elif clean[i] == ")":
                depth -= 1
            i += 1
        while i < n and clean[i].isspace():
            i += 1

        if clean.startswith(";", i):               # abstract / interface: không có thân
            continue
        if clean.startswith("=>", i):              # thân biểu thức
            end = clean.find(";", i)
            yield i + 2, (n if end < 0 else end)
            continue

        brace = clean.find("{", i)                 # có thể có ràng buộc `where ...` trước '{'
        if brace < 0:
            continue
        depth, j = 0, brace
        while j < n:
            if clean[j] == "{":
                depth += 1
            elif clean[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield brace, j


def audit_file(path, method_re):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        return [(str(path), 0, "ERROR", "IO", f"không đọc được: {exc}")]

    clean = sanitize(text)
    raw_lines = text.split("\n")
    clean_lines = clean.split("\n")
    line_starts = [0]
    for line in clean_lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)

    findings = []
    seen = set()
    for body_start, body_end in find_bodies(clean, method_re):
        first = bisect.bisect_right(line_starts, body_start) - 1
        last = bisect.bisect_right(line_starts, body_end) - 1
        for ln in range(first, last + 1):
            lo = max(body_start, line_starts[ln]) - line_starts[ln]
            hi = min(body_end, line_starts[ln] + len(clean_lines[ln])) - line_starts[ln]
            segment = clean_lines[ln][lo:hi]
            if not segment.strip() or "throw new" in segment:
                continue

            ignored = set(IGNORE.findall(raw_lines[ln]))
            if ln:
                ignored |= set(IGNORE.findall(raw_lines[ln - 1]))

            for rule_id, level, regex, message in RULES:
                if rule_id in ignored or (ln, rule_id) in seen:
                    continue
                if regex.search(segment):
                    seen.add((ln, rule_id))
                    findings.append((str(path), ln + 1, level, rule_id, message))
    return findings


def main():
    if hasattr(sys.stdout, "reconfigure"):          # console Windows mặc định cp1258/cp1252 không in được tiếng Việt
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Audit Zero-GC hot path")
    parser.add_argument("paths", nargs="*", default=["Assets"])
    parser.add_argument("--methods", default=DEFAULT_METHODS)
    args = parser.parse_args()

    names = "|".join(re.escape(m.strip()) for m in args.methods.split(",") if m.strip())
    method_re = re.compile(r"\b(?:void|bool|float|int|BTStatus)\s+(?:" + names + r")\s*\(")

    files = []
    for p in args.paths:
        root = pathlib.Path(p)
        if root.is_file():
            files.append(root)                      # file chỉ định trực tiếp thì luôn quét
        elif root.is_dir():
            for f in sorted(root.rglob("*.cs")):
                if not SKIPPED_DIRS.intersection(f.relative_to(root).parts[:-1]):
                    files.append(f)

    findings = []
    for f in files:
        findings.extend(audit_file(f, method_re))

    for path, line, level, rule_id, message in sorted(findings, key=lambda x: (x[0], x[1])):
        print(f"{path}:{line}: [{level} {rule_id}] {message}")

    errors = sum(1 for f in findings if f[2] == "ERROR")
    print(f"audit_hotpath: {len(files)} file, {errors} ERROR, {len(findings) - errors} WARN")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
