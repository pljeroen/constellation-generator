# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Machine-readable regulatory compliance profiles and traces."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from humeris.domain.atmosphere import DragConfig
from humeris.domain.deorbit import DeorbitRegulation, assess_deorbit_compliance


@dataclass(frozen=True)
class RuleEvaluation:
    rule_id: str
    passed: bool
    rationale: str
    remediation: str


@dataclass(frozen=True)
class ComplianceProfile:
    profile_id: str
    title: str
    regulation: DeorbitRegulation
    rationale: str
    effective_date: str


_PRESETS = {
    "us_fcc_5year_v1": ComplianceProfile(
        profile_id="us_fcc_5year_v1",
        title="US FCC 5-year disposal preset",
        regulation=DeorbitRegulation.FCC_5YEAR,
        rationale="FCC post-mission disposal timeline for small satellites.",
        effective_date="2024-09-29",
    ),
    "eu_zero_debris_25year_v1": ComplianceProfile(
        profile_id="eu_zero_debris_25year_v1",
        title="EU-style zero-debris 25-year preset",
        regulation=DeorbitRegulation.ESA_25YEAR,
        rationale="ESA-aligned sustainability baseline for disposal timelines.",
        effective_date="2023-01-01",
    ),
}


def get_compliance_profile(profile_id: str) -> ComplianceProfile:
    try:
        return _PRESETS[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown compliance profile: {profile_id}") from exc


def evaluate_compliance_profile(
    profile_id: str,
    altitude_km: float,
    drag_config: DragConfig,
    epoch: datetime,
    eccentricity: float = 0.0,
) -> dict[str, object]:
    """Evaluate a profile and emit trace with rule IDs and remediation."""
    profile = get_compliance_profile(profile_id)
    assessment = assess_deorbit_compliance(
        altitude_km=altitude_km,
        drag_config=drag_config,
        epoch=epoch,
        regulation=profile.regulation,
        eccentricity=eccentricity,
    )

    rules = [
        RuleEvaluation(
            rule_id=f"{profile.profile_id}:deorbit_lifetime",
            passed=assessment.compliant,
            rationale=(
                f"Natural lifetime {assessment.natural_lifetime_days:.2f} days "
                f"<= threshold {assessment.threshold_days:.2f} days"
            ),
            remediation=(
                "No remediation required"
                if assessment.compliant
                else "Lower perigee and re-run compliance simulation"
            ),
        )
    ]

    violations = [r.rule_id for r in rules if not r.passed]
    remediation = [r.remediation for r in rules if not r.passed]

    return {
        "profile": {
            "id": profile.profile_id,
            "title": profile.title,
            "effective_date": profile.effective_date,
            "rationale": profile.rationale,
        },
        "assessment": {
            "compliant": assessment.compliant,
            "natural_lifetime_days": assessment.natural_lifetime_days,
            "threshold_days": assessment.threshold_days,
        },
        "rules": [r.__dict__ for r in rules],
        "violated_rule_ids": violations,
        "remediation_options": remediation,
    }
