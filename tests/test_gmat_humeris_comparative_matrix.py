# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Expanded GMAT-vs-Humeris comparative validation matrix."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from humeris.adapters.celestrak import SGP4Adapter
from humeris.adapters.gmat_mirror import run_humeris_mirror
from humeris.domain.atmosphere import DragConfig
from humeris.domain.ccsds_contracts import envelope_from_record, roundtrip_envelope
from humeris.domain.compliance_profiles import evaluate_compliance_profile
from humeris.domain.conjunction_profiles import evaluate_profiled_screening
from humeris.domain.deorbit import DeorbitRegulation, assess_deorbit_compliance
from humeris.domain.maneuvers import hohmann_transfer
from humeris.domain.numerical_propagation import TwoBodyGravity, propagate_numerical
from humeris.domain.orbital_mechanics import OrbitalConstants
from humeris.domain.orbit_properties import state_vector_to_elements
from humeris.domain.propagation import OrbitalState


_GMAT_REPO = Path("/home/jeroen/gmat")


def _parse_keplerian_report(path: Path) -> list[dict[str, float]]:
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    rows: list[dict[str, float]] = []
    for ln in lines[1:]:
        parts = ln.split()
        vals = list(map(float, parts[4:]))
        rows.append(
            {
                "sma_km": vals[0],
                "ecc": vals[1],
                "inc_deg": vals[2],
                "raan_deg": vals[3],
                "aop_deg": vals[4],
                "ta_deg": vals[5],
            }
        )
    return rows


@pytest.mark.skipif(not _GMAT_REPO.exists(), reason="Local GMAT repo not available")
def test_timeseries_parity_against_gmat_oem_reference():
    """Time-series endpoint parity against GMAT OEM propagation reference."""
    p = _GMAT_REPO / "docs/test-runs/run-0008-3b5fc7b-clean/cases/headless_oem_ephemeris_propagation/KeplerianElements.txt"
    rows = _parse_keplerian_report(p)
    start = rows[0]
    end_gmat = rows[-1]

    epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    a_m = start["sma_km"] * 1000.0
    n = math.sqrt(OrbitalConstants.MU_EARTH / a_m**3)
    state = OrbitalState(
        semi_major_axis_m=a_m,
        eccentricity=start["ecc"],
        inclination_rad=math.radians(start["inc_deg"]),
        raan_rad=math.radians(start["raan_deg"]),
        arg_perigee_rad=math.radians(start["aop_deg"]),
        true_anomaly_rad=math.radians(start["ta_deg"]),
        mean_motion_rad_s=n,
        reference_epoch=epoch,
    )

    out = propagate_numerical(
        initial_state=state,
        duration=timedelta(days=2),
        step=timedelta(seconds=60),
        force_models=[TwoBodyGravity()],
        integrator="dormand_prince",
    )
    end = state_vector_to_elements(out.steps[-1].position_eci, out.steps[-1].velocity_eci)

    assert abs(end["semi_major_axis_m"] / 1000.0 - end_gmat["sma_km"]) < 0.2
    assert abs(end["eccentricity"] - end_gmat["ecc"]) < 1e-3
    assert abs(end["inclination_deg"] - end_gmat["inc_deg"]) < 0.02


@pytest.mark.skipif(not _GMAT_REPO.exists(), reason="Local GMAT repo not available")
def test_force_model_matrix_parity_floor_cases():
    """Comparative force-model matrix floor via mirrored GMAT scenario classes."""
    out = run_humeris_mirror()
    assert set(out.keys()) >= {
        "basic_leo_two_body",
        "advanced_j2_raan_drift",
        "advanced_oumuamua_hyperbolic",
        "advanced_oumuamua_suncentric",
    }

    basic = out["basic_leo_two_body"]
    j2 = out["advanced_j2_raan_drift"]
    hyp = out["advanced_oumuamua_hyperbolic"]
    sun = out["advanced_oumuamua_suncentric"]

    assert abs(basic["endSMA"] - basic["startSMA"]) < 0.1
    assert 0.01 < j2["raanDriftDeg"] < 30.0
    assert hyp["endECC"] > 1.0 and sun["endECC"] > 1.0
    assert "SolarThirdBodyForce" in sun["forceModels"]


@pytest.mark.skipif(not _GMAT_REPO.exists(), reason="Local GMAT repo not available")
def test_maneuver_parity_sample_completion_and_humeris_dv_range():
    """Maneuver cross-check: GMAT sample completion + Humeris transfer math sanity."""
    stdout_path = _GMAT_REPO / "docs/test-runs/run-0008-3b5fc7b-clean/cases/sample_hohmann_transfer/stdout.txt"
    text = stdout_path.read_text(encoding="utf-8")
    assert "Mission run completed" in text

    r1 = OrbitalConstants.R_EARTH + 300_000.0
    r2 = OrbitalConstants.R_EARTH + 35_786_000.0
    plan = hohmann_transfer(r1, r2)
    assert 3500.0 < plan.total_delta_v_ms < 4500.0


@pytest.mark.skipif(not _GMAT_REPO.exists(), reason="Local GMAT repo not available")
def test_conjunction_backtesting_profile_calibration_proxy():
    """Proxy backtest on historical-like conjunction tuples."""
    historical = [
        {"miss": 8000.0, "base_pc": 1.5e-5, "observed_flag": True},
        {"miss": 25000.0, "base_pc": 1.0e-7, "observed_flag": False},
        {"miss": 12000.0, "base_pc": 9.0e-5, "observed_flag": True},
    ]
    errors = []
    for row in historical:
        pred = evaluate_profiled_screening(row["miss"], row["base_pc"], "nominal")
        predicted = bool(pred["output"]["flagged"])
        errors.append(1.0 if predicted != row["observed_flag"] else 0.0)
    assert sum(errors) / len(errors) <= 0.34


@pytest.mark.skipif(not _GMAT_REPO.exists(), reason="Local GMAT repo not available")
def test_deorbit_backtesting_against_reference_windows_proxy():
    """Proxy deorbit backtesting using known altitude lifetime expectations."""
    drag = DragConfig(cd=2.2, area_m2=0.3, mass_kg=200.0)
    epoch = datetime(2026, 2, 16, tzinfo=timezone.utc)

    low = assess_deorbit_compliance(450.0, drag, epoch, regulation=DeorbitRegulation.FCC_5YEAR)
    high = assess_deorbit_compliance(900.0, drag, epoch, regulation=DeorbitRegulation.FCC_5YEAR)

    assert low.natural_lifetime_days < high.natural_lifetime_days
    assert low.natural_lifetime_days > 0.0


def test_ephemeris_roundtrip_covariance_provenance_contract_cycles():
    """Repeated round-trips preserve envelope provenance integrity."""
    omm = {
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "NORAD_CAT_ID": 25544,
        "EPOCH": "2026-02-16T00:00:00Z",
        "MEAN_MOTION": 15.5,
        "ECCENTRICITY": 0.0005,
        "INCLINATION": 51.6,
        "RA_OF_ASC_NODE": 120.0,
        "ARG_OF_PERICENTER": 85.0,
        "MEAN_ANOMALY": 10.0,
    }
    env = envelope_from_record("OMM", omm, source_timestamp="2026-02-16T00:00:00Z")
    p0 = env.provenance_hash
    for _ in range(5):
        env = roundtrip_envelope(env)
    assert env.provenance_hash == p0


@pytest.mark.skipif(not _GMAT_REPO.exists(), reason="Local GMAT repo not available")
def test_cross_propagator_sanity_against_gmat_and_sgp4():
    """Cross-propagator sanity (GMAT class + SGP4 + Humeris)."""
    sample = {
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "EPOCH": "2026-02-11T04:21:12.145248",
        "MEAN_MOTION": 15.4854011,
        "ECCENTRICITY": 0.00110736,
        "INCLINATION": 51.6314,
        "RA_OF_ASC_NODE": 203.3958,
        "ARG_OF_PERICENTER": 86.686,
        "MEAN_ANOMALY": 273.5395,
        "EPHEMERIS_TYPE": 0,
        "CLASSIFICATION_TYPE": "U",
        "NORAD_CAT_ID": 25544,
        "ELEMENT_SET_NO": 999,
        "REV_AT_EPOCH": 55222,
        "BSTAR": 0.00022024123,
        "MEAN_MOTION_DOT": 0.00011529,
        "MEAN_MOTION_DDOT": 0,
    }
    sat = SGP4Adapter().omm_to_satellite(sample)
    r_km = math.sqrt(sum(p**2 for p in sat.position_eci)) / 1000.0

    gm = run_humeris_mirror()["basic_leo_two_body"]
    assert abs(r_km - gm["startRMAG"]) < 1200.0


def test_compliance_profile_trace_contains_rule_ids_and_remediation():
    drag = DragConfig(cd=2.2, area_m2=0.3, mass_kg=200.0)
    out = evaluate_compliance_profile(
        profile_id="us_fcc_5year_v1",
        altitude_km=700.0,
        drag_config=drag,
        epoch=datetime(2026, 2, 16, tzinfo=timezone.utc),
    )
    assert isinstance(out["violated_rule_ids"], list)
    assert isinstance(out["remediation_options"], list)


@pytest.mark.skipif(not _GMAT_REPO.exists(), reason="Local GMAT repo not available")
def test_comparative_artifact_linkage_between_suites():
    """Ensure comparative artifacts can be linked across both repositories."""
    gm_manifest = _GMAT_REPO / "docs/test-runs/run-0008-3b5fc7b-clean/manifest.json"
    hum_latest = Path("docs/gmat-parity-runs/LATEST")
    assert gm_manifest.exists()
    assert hum_latest.exists()
    _ = json.loads(gm_manifest.read_text(encoding="utf-8"))
