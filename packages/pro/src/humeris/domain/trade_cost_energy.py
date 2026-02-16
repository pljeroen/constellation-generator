# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Compute-budget-aware trade study scoring and Pareto extraction."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostEnergyPoint:
    mission_performance: float
    compute_cost_usd: float
    energy_kwh: float
    runtime_s: float


def pareto_front_cost_energy(points: list[CostEnergyPoint]) -> list[int]:
    """Pareto front maximizing performance while minimizing cost/energy/runtime."""
    front: list[int] = []
    for i, a in enumerate(points):
        dominated = False
        for j, b in enumerate(points):
            if i == j:
                continue
            ge_perf = b.mission_performance >= a.mission_performance
            le_cost = b.compute_cost_usd <= a.compute_cost_usd
            le_energy = b.energy_kwh <= a.energy_kwh
            le_runtime = b.runtime_s <= a.runtime_s
            strict = (
                b.mission_performance > a.mission_performance
                or b.compute_cost_usd < a.compute_cost_usd
                or b.energy_kwh < a.energy_kwh
                or b.runtime_s < a.runtime_s
            )
            if ge_perf and le_cost and le_energy and le_runtime and strict:
                dominated = True
                break
        if not dominated:
            front.append(i)
    return front
