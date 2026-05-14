"""Пересобирает docs/laws/index.yml из YAML-фронтматтеров всех файлов справочника.

Запуск:
    python tools/rebuild_index.py
"""

import datetime
import glob
import os
import re
import sys
from typing import Any

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAWS_DIR = os.path.join(ROOT, "docs", "laws")
COMMON_DIR = os.path.join(LAWS_DIR, "common")
INDEX_PATH = os.path.join(LAWS_DIR, "index.yml")


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


def collect_laws() -> list[dict[str, Any]]:
    paths = sorted(
        p
        for p in glob.glob(os.path.join(LAWS_DIR, "*.md"))
        if os.path.basename(p) not in {"README.md", "schema.md"}
    )
    laws: list[dict[str, Any]] = []
    for p in paths:
        data = load_frontmatter(p)
        if not data:
            continue
        laws.append(
            {
                "id": data.get("id"),
                "file": os.path.basename(p),
                "short_title": data.get("short_title"),
                "title": data.get("title"),
                "type": data.get("type"),
                "status": data.get("status"),
                "in_force_since": data.get("in_force_since"),
                "last_amended": data.get("last_amended"),
                "applies_to": data.get("applies_to") or [],
                "tags": data.get("tags") or [],
                "verified_at": data.get("verified_at"),
                "verified": data.get("verified"),
                "violations_count": len(data.get("violations") or []),
                "regulators": data.get("regulators") or [],
            }
        )
    return laws


def collect_common() -> list[dict[str, Any]]:
    paths = sorted(glob.glob(os.path.join(COMMON_DIR, "*.md")))
    items: list[dict[str, Any]] = []
    for p in paths:
        data = load_frontmatter(p)
        if not data:
            continue
        items.append(
            {
                "id": data.get("id"),
                "file": "common/" + os.path.basename(p),
                "title": data.get("title"),
                "document_kind": data.get("document_kind"),
                "status": data.get("status"),
                "verified_at": data.get("verified_at"),
                "verified": data.get("verified"),
            }
        )
    return items


def check_integrity(laws: list[dict[str, Any]], common: list[dict[str, Any]]) -> list[str]:
    all_ids = {law["id"] for law in laws} | {item["id"] for item in common}
    issues: list[str] = []
    for p in sorted(glob.glob(os.path.join(LAWS_DIR, "*.md"))):
        if os.path.basename(p) in {"README.md", "schema.md"}:
            continue
        data = load_frontmatter(p) or {}
        fid = data.get("id")
        for r in data.get("related") or []:
            if r not in all_ids:
                issues.append(f"{fid} -> related: {r} (NOT FOUND)")
        for c in data.get("references_in_common") or []:
            if c not in all_ids:
                issues.append(f"{fid} -> references_in_common: {c} (NOT FOUND)")
    return issues


def main() -> None:
    laws = collect_laws()
    common = collect_common()
    issues = check_integrity(laws, common)

    index: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.date.today().isoformat(),
        "generator": "tools/rebuild_index.py",
        "total_laws": len(laws),
        "total_common_compendiums": len(common),
        "total_violations": sum(law["violations_count"] for law in laws),
        "laws": laws,
        "common_compendiums": common,
    }

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write("# Машинный индекс справочника законов.\n")
        f.write("# Сгенерирован из YAML-фронтматтеров файлов в docs/laws/.\n")
        f.write("# Не править руками — пересборка: python tools/rebuild_index.py\n\n")
        yaml.safe_dump(
            index,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=120,
        )

    print(f"index.yml regenerated -> {INDEX_PATH}")
    print(f"  total_laws: {len(laws)}")
    print(f"  total_common: {len(common)}")
    print(f"  total_violations: {sum(law['violations_count'] for law in laws)}")
    if issues:
        print("INTEGRITY ISSUES:")
        for i in issues:
            print(f"  - {i}")
        sys.exit(1)
    else:
        print("integrity: all related[] and references_in_common[] resolve.")


if __name__ == "__main__":
    main()
