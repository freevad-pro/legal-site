"""Печатает все verification_notes из всех файлов справочника."""

import glob
import io
import os
import re
import sys
from typing import Any

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAWS_DIR = os.path.join(ROOT, "docs", "laws")

# UTF-8 stdout для Windows-консоли
if sys.platform == "win32" and isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")


def load_frontmatter(path: str) -> dict[str, Any] | None:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None
    parsed = yaml.safe_load(m.group(1))
    if not isinstance(parsed, dict):
        return None
    return parsed


def main() -> None:
    files = sorted(
        p
        for p in glob.glob(os.path.join(LAWS_DIR, "*.md"))
        if os.path.basename(p) not in {"README.md", "schema.md"}
    )
    files += sorted(glob.glob(os.path.join(LAWS_DIR, "common", "*.md")))

    total = 0
    for p in files:
        data = load_frontmatter(p)
        if not data:
            continue
        notes = data.get("verification_notes") or []
        if not notes:
            continue
        print(f"\n=== {data.get('id')} ({len(notes)} notes) ===")
        for i, n in enumerate(notes, 1):
            print(f"  {i}. {n.strip()}")
        total += len(notes)

    print(f"\n--- TOTAL verification_notes across all files: {total} ---")


if __name__ == "__main__":
    main()
