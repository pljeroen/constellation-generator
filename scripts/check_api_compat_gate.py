#!/usr/bin/env python3
"""CI compatibility gate for manifest/API schema evolution."""
from __future__ import annotations

import json
import re
from pathlib import Path

from humeris.domain.api_contracts import evaluate_schema_compatibility

ROOT = Path(__file__).resolve().parents[1]
PREV = ROOT / "docs" / "contracts" / "api_schema_previous.json"
CURR = ROOT / "docs" / "contracts" / "api_schema_current.json"
MIG = ROOT / "docs" / "contracts" / "API_MIGRATIONS.md"
CORE_PYPROJECT = ROOT / "packages" / "core" / "pyproject.toml"


def read_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not m:
        raise SystemExit(f"Could not find version in {path}")
    return m.group(1)


def main() -> int:
    prev = json.loads(PREV.read_text(encoding="utf-8"))
    curr = json.loads(CURR.read_text(encoding="utf-8"))

    prev_fields = set(prev.get("fields", []))
    curr_fields = set(curr.get("fields", []))

    current_version = read_version(CORE_PYPROJECT)
    migration_notes = MIG.read_text(encoding="utf-8")
    version_bumped = prev.get("schema_version") != curr.get("schema_version")

    result = evaluate_schema_compatibility(
        previous_fields=prev_fields,
        current_fields=curr_fields,
        migration_notes=migration_notes if current_version in migration_notes else "",
        version_bumped=version_bumped,
    )

    if not result.compatible:
        print("API compatibility gate: FAIL")
        print("breaking_changes:", ", ".join(result.breaking_changes) or "none")
        print("requires_version_bump:", result.requires_version_bump)
        print("migration_notes_present:", result.migration_notes_present)
        return 1

    print("API compatibility gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
