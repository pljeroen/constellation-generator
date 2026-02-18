# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Opt-in falsification gates for Tier-1 research modules.

These tests are intentionally strict: failing a gate means the claimed value
of a T1 method is not evidenced under controlled synthetic conditions.

Execution is opt-in to avoid surprising baseline CI:
    HUMERIS_T1_FALSIFY=1 pytest tests/test_t1_falsification_gate.py -q
"""

import importlib.util
import math
import os
from datetime import datetime

import numpy as np
import pytest

from humeris.domain.competing_risks import RiskProfile, compute_competing_risks
from humeris.domain.control_analysis import compute_cw_controllability
from humeris.domain.functorial_composition import compose_forces
from humeris.domain.gramian_reconfiguration import compute_fuel_cost_index
from humeris.domain.hodge_cusum import compute_topology_snapshot, monitor_topology_cusum


_ENABLE = os.getenv("HUMERIS_T1_FALSIFY", "0") == "1"
pytestmark = pytest.mark.skipif(
    not _ENABLE,
    reason="Set HUMERIS_T1_FALSIFY=1 to run Tier-1 falsification gates.",
)


class _ConstantForce:
    def __init__(self, acc):
        self._acc = acc

    def acceleration(self, epoch, position, velocity):
        return self._acc


def _ring_4():
    return [
        [0, 1, 0, 1],
        [1, 0, 1, 0],
        [0, 1, 0, 1],
        [1, 0, 1, 0],
    ]


def _broken_ring_4():
    return [
        [0, 1, 0, 0],
        [1, 0, 1, 0],
        [0, 1, 0, 1],
        [0, 0, 1, 0],
    ]


def test_t1_functorial_superposition_is_exact():
    epoch = datetime(2026, 1, 1)
    models = [
        ("a", _ConstantForce((1e-6, 2e-6, -1e-6))),
        ("b", _ConstantForce((3e-6, -4e-6, 2e-6))),
        ("c", _ConstantForce((-2e-6, 1e-6, 5e-6))),
    ]
    result = compose_forces(models, epoch, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    expected = np.array([2e-6, -1e-6, 6e-6], dtype=np.float64)
    got = np.array(result.total_acceleration, dtype=np.float64)

    assert np.linalg.norm(got - expected) < 1e-18, (
        "FALSIFIED[T1-01]: functorial composition deviates from exact linear "
        "superposition. Candidate for removal/deprecation."
    )
    assert result.composition_residual < 1e-18
    assert result.is_order_independent


def test_t1_hodge_cusum_rejects_transient_single_tick_change():
    snapshots = [compute_topology_snapshot(_ring_4(), 4, i) for i in range(20)]
    snapshots.append(compute_topology_snapshot(_broken_ring_4(), 4, 20))
    snapshots.extend(compute_topology_snapshot(_ring_4(), 4, i) for i in range(21, 41))

    result = monitor_topology_cusum(
        snapshots,
        threshold=5.0,
        drift=0.5,
        baseline_window=20,
    )
    assert result.num_topology_changes == 0, (
        "FALSIFIED[T1-02]: Hodge-CUSUM triggers on a one-sample transient. "
        "Candidate for removal/deprecation unless robustness is fixed."
    )


def test_t1_gramian_cost_index_separates_cheap_vs_expensive_directions():
    # Representative LEO mean motion (~95 min period).
    n_rad_s = 2.0 * math.pi / (95.0 * 60.0)
    analysis = compute_cw_controllability(n_rad_s=n_rad_s, duration_s=1800.0, step_s=10.0)

    cheap_cost = compute_fuel_cost_index(analysis.max_energy_direction, analysis)
    expensive_cost = compute_fuel_cost_index(analysis.min_energy_direction, analysis)

    assert cheap_cost < 1.0, (
        "FALSIFIED[T1-03]: Gramian method does not identify a below-average "
        "cost direction."
    )
    assert expensive_cost > 1.0, (
        "FALSIFIED[T1-03]: Gramian method does not identify an above-average "
        "cost direction."
    )
    assert expensive_cost > cheap_cost * 10.0, (
        "FALSIFIED[T1-03]: Directional cost anisotropy is too weak to justify "
        "the method. Candidate for removal/deprecation."
    )


def test_t1_koopman_kscs_removed_after_falsification_decision():
    assert importlib.util.find_spec("humeris.domain.koopman_conjunction") is None, (
        "FALSIFIED[T1-04]: KSCS module still present after removal decision."
    )


def test_t1_competing_risks_prevents_probability_mass_violation():
    # Two high constant hazards where naive sum of independent failures > 1.
    hazard_per_day = 1.0 / 365.25  # 1/year
    risks = [
        RiskProfile(name="risk_a", hazard_rates=(hazard_per_day,), is_constant=True),
        RiskProfile(name="risk_b", hazard_rates=(hazard_per_day,), is_constant=True),
    ]

    result = compute_competing_risks(risks, duration_years=5.0, dt_years=0.01)
    final_survival = float(result.overall_survival[-1])
    competing_total_failure = 1.0 - final_survival

    single_fail = 1.0 - math.exp(-5.0)  # per-risk failure probability over 5 years
    naive_sum = single_fail + single_fail

    assert naive_sum > 1.0  # sanity check for baseline failure mode
    assert competing_total_failure <= 1.0 + 1e-12, (
        "FALSIFIED[T1-05]: competing-risks output violates probability mass."
    )
    cif_sum = sum(series[-1] for _, series in result.cause_specific_cif)
    assert abs(cif_sum - competing_total_failure) < 1e-6
