# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""D-P2-02: Mission-performance vs compute-cost Pareto frontier."""
from __future__ import annotations

from humeris.domain.trade_cost_energy import CostEnergyPoint, pareto_front_cost_energy


def test_cost_energy_pareto_front_contains_non_dominated_points():
    points = [
        CostEnergyPoint(mission_performance=0.8, compute_cost_usd=10.0, energy_kwh=2.0, runtime_s=60.0),
        CostEnergyPoint(mission_performance=0.9, compute_cost_usd=12.0, energy_kwh=2.5, runtime_s=70.0),
        CostEnergyPoint(mission_performance=0.7, compute_cost_usd=8.0, energy_kwh=1.8, runtime_s=55.0),
        CostEnergyPoint(mission_performance=0.75, compute_cost_usd=14.0, energy_kwh=4.0, runtime_s=120.0),
    ]
    front = pareto_front_cost_energy(points)
    assert 3 not in front
    assert len(front) >= 2
