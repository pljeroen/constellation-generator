# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""D-P2-01: Digital twin continuity checks across mission phases."""
from __future__ import annotations

from humeris.domain.mission_digital_twin import TwinState, validate_twin_continuity


def test_digital_twin_validates_three_phase_continuity():
    states = [
        TwinState(phase="design", state_id="s0", parent_state_id=None),
        TwinState(phase="operations", state_id="s1", parent_state_id="s0"),
        TwinState(phase="end_of_life", state_id="s2", parent_state_id="s1"),
    ]
    out = validate_twin_continuity(states)
    assert out["ok"] is True


def test_digital_twin_rejects_orphan_state():
    states = [
        TwinState(phase="design", state_id="s0", parent_state_id=None),
        TwinState(phase="operations", state_id="s1", parent_state_id="missing"),
        TwinState(phase="end_of_life", state_id="s2", parent_state_id="s1"),
    ]
    out = validate_twin_continuity(states)
    assert out["ok"] is False
    assert "orphan" in out["reason"]
