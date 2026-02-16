# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""D-P0-03: Profile-driven conjunction screening behavior."""
from __future__ import annotations

from humeris.domain.conjunction_profiles import (
    evaluate_profiled_screening,
    get_screening_profile,
)


def test_profile_pack_selection_has_versioned_metadata():
    p = get_screening_profile("conservative")
    assert p.profile_id == "conservative"
    assert p.version == "v1"


def test_profile_output_includes_probability_band():
    out = evaluate_profiled_screening(
        miss_distance_m=9000.0,
        base_collision_probability=2e-5,
        profile_name="nominal",
    )
    band = out["output"]["collision_probability_band"]
    assert set(band.keys()) == {"lower", "nominal", "upper"}
    assert band["lower"] <= band["nominal"] <= band["upper"]
