# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""D-P2-03: API schema compatibility gate and machine-readable diff."""
from __future__ import annotations

from humeris.domain.api_contracts import evaluate_schema_compatibility, schema_diff


def test_schema_gate_requires_version_bump_and_migration_notes_for_breaking_changes():
    prev = {"id", "epoch", "ecc"}
    curr = {"id", "epoch"}

    bad = evaluate_schema_compatibility(
        previous_fields=prev,
        current_fields=curr,
        migration_notes="",
        version_bumped=False,
    )
    assert bad.compatible is False
    assert bad.requires_version_bump is True

    good = evaluate_schema_compatibility(
        previous_fields=prev,
        current_fields=curr,
        migration_notes="ecc removed; use anomaly_state.eccentricity",
        version_bumped=True,
    )
    assert good.compatible is True


def test_schema_diff_is_machine_readable():
    diff = schema_diff({"a", "b"}, {"b", "c"})
    assert diff == {"added": ["c"], "removed": ["a"], "unchanged": ["b"]}
