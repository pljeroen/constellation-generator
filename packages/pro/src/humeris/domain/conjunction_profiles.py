# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Profile-driven conjunction screening outputs with probability bands."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreeningProfile:
    profile_id: str
    version: str
    threshold_m: float
    covariance_scale: float


_PROFILE_PACKS = {
    "conservative": ScreeningProfile(
        profile_id="conservative",
        version="v1",
        threshold_m=25000.0,
        covariance_scale=1.5,
    ),
    "nominal": ScreeningProfile(
        profile_id="nominal",
        version="v1",
        threshold_m=15000.0,
        covariance_scale=1.0,
    ),
    "aggressive": ScreeningProfile(
        profile_id="aggressive",
        version="v1",
        threshold_m=8000.0,
        covariance_scale=0.75,
    ),
}


def get_screening_profile(name: str) -> ScreeningProfile:
    try:
        return _PROFILE_PACKS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown screening profile: {name}") from exc


def evaluate_profiled_screening(
    miss_distance_m: float,
    base_collision_probability: float,
    profile_name: str,
) -> dict[str, object]:
    """Evaluate conjunction result under a named profile pack."""
    profile = get_screening_profile(profile_name)

    scaled_pc = min(1.0, max(0.0, base_collision_probability * profile.covariance_scale))
    lower = max(0.0, scaled_pc * 0.7)
    upper = min(1.0, scaled_pc * 1.3)

    flagged = miss_distance_m <= profile.threshold_m or upper >= 1e-4

    return {
        "profile": {
            "id": profile.profile_id,
            "version": profile.version,
            "threshold_m": profile.threshold_m,
            "covariance_scale": profile.covariance_scale,
        },
        "input": {
            "miss_distance_m": miss_distance_m,
            "base_collision_probability": base_collision_probability,
        },
        "output": {
            "flagged": flagged,
            "collision_probability_band": {
                "lower": lower,
                "nominal": scaled_pc,
                "upper": upper,
            },
        },
    }
