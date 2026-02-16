# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""D-P1-01: Regulatory compliance profile traces."""
from __future__ import annotations

from datetime import datetime, timezone

from humeris.domain.atmosphere import DragConfig
from humeris.domain.compliance_profiles import evaluate_compliance_profile


def test_compliance_profiles_emit_machine_readable_rationale_and_rule_ids():
    drag = DragConfig(cd=2.2, area_m2=0.3, mass_kg=200.0)
    out = evaluate_compliance_profile(
        profile_id="us_fcc_5year_v1",
        altitude_km=450.0,
        drag_config=drag,
        epoch=datetime(2026, 2, 16, tzinfo=timezone.utc),
    )
    assert out["profile"]["id"] == "us_fcc_5year_v1"
    assert out["profile"]["rationale"]
    assert isinstance(out["violated_rule_ids"], list)
    assert isinstance(out["remediation_options"], list)
