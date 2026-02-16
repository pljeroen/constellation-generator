# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Schema compatibility and deprecation contract checks."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiCompatibilityResult:
    compatible: bool
    breaking_changes: tuple[str, ...]
    requires_version_bump: bool
    migration_notes_present: bool


def evaluate_schema_compatibility(
    previous_fields: set[str],
    current_fields: set[str],
    migration_notes: str,
    version_bumped: bool,
) -> ApiCompatibilityResult:
    """Evaluate compatibility gate for schema evolution."""
    removed = sorted(previous_fields - current_fields)
    breaking = tuple(f"removed:{name}" for name in removed)

    has_break = len(breaking) > 0
    notes_present = migration_notes.strip() != ""

    compatible = True
    if has_break and (not version_bumped or not notes_present):
        compatible = False

    return ApiCompatibilityResult(
        compatible=compatible,
        breaking_changes=breaking,
        requires_version_bump=has_break,
        migration_notes_present=notes_present,
    )


def schema_diff(previous_fields: set[str], current_fields: set[str]) -> dict[str, list[str]]:
    """Machine-readable schema diff for release artifacts."""
    return {
        "added": sorted(current_fields - previous_fields),
        "removed": sorted(previous_fields - current_fields),
        "unchanged": sorted(previous_fields & current_fields),
    }
