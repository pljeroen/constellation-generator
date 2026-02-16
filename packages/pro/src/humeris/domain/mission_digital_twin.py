# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Mission digital twin continuity checks across lifecycle phases."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TwinState:
    phase: str
    state_id: str
    parent_state_id: str | None


_PHASE_ORDER = ("design", "operations", "end_of_life")


def validate_twin_continuity(states: list[TwinState]) -> dict[str, object]:
    """Validate continuity across design -> operations -> end_of_life."""
    if len(states) < 3:
        return {"ok": False, "reason": "at least 3 states required"}

    seen_phases = {s.phase for s in states}
    required = set(_PHASE_ORDER)
    if not required.issubset(seen_phases):
        return {"ok": False, "reason": "missing required lifecycle phases"}

    by_id = {s.state_id: s for s in states}
    for s in states:
        if s.parent_state_id is not None and s.parent_state_id not in by_id:
            return {"ok": False, "reason": f"orphan state: {s.state_id}"}

    ordered = sorted(states, key=lambda s: _PHASE_ORDER.index(s.phase) if s.phase in _PHASE_ORDER else 99)
    for idx in range(1, len(ordered)):
        prev = ordered[idx - 1]
        cur = ordered[idx]
        if cur.phase in _PHASE_ORDER and prev.phase in _PHASE_ORDER:
            if _PHASE_ORDER.index(cur.phase) < _PHASE_ORDER.index(prev.phase):
                return {"ok": False, "reason": "non-monotonic phase transition"}

    return {"ok": True, "phases": sorted(seen_phases)}
