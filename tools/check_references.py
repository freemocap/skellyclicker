from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
bib = (root / "references.bib").read_text(encoding="utf-8-sig")
entries = re.split(r"(?=@\w+\{)", bib)
keys = set()
for entry in entries:
    if not entry.strip():
        continue
    match = re.match(r"@\w+\{([^,]+),", entry)
    assert match, "Invalid bibliography entry"
    key = match.group(1)
    assert key not in keys, f"Duplicate key: {key}"
    keys.add(key)
    for field in ("title", "url", "urldate", "review", "claim"):
        assert re.search(rf"\b{field}\s*=\s*\{{[^}}]+\}}", entry), f"Missing {field}: {key}"
for path in [root / "native/src/main.rs", root / "README.md", root / "PLAYBACK.md", root / "docs/training-dashboard.md", root / "backend/skellyclicker_app/workers/train_dlc.py"]:
    for key in re.findall(r"\[@([\w-]+)\]", path.read_text(encoding="utf-8-sig")):
        assert key in keys, f"Unresolved citation {key}: {path}"
print(f"PASS: {len(keys)} source references and current citations")
