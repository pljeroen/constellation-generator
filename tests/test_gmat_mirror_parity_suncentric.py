# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""RED/GREEN coverage for D-P0-01 Sun-centric parity extension."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from humeris.adapters.gmat_mirror import run_humeris_mirror


def _load_compare_script_module():
    script_path = Path("scripts/run_gmat_mirror_compare.py").resolve()
    spec = importlib.util.spec_from_file_location("run_gmat_mirror_compare", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_suncentric_case_emits_required_metrics():
    out = run_humeris_mirror()
    assert "advanced_oumuamua_suncentric" in out

    case = out["advanced_oumuamua_suncentric"]
    required = {
        "startECC",
        "startINC",
        "startRMAG",
        "endECC",
        "endINC",
        "endRMAG",
        "startEnergySign",
        "endEnergySign",
        "elapsedDays",
    }
    assert required.issubset(case.keys())
    assert case["startECC"] > 1.0
    assert case["endECC"] > 1.0
    assert case["startEnergySign"] in {-1, 0, 1}
    assert case["endEnergySign"] in {-1, 0, 1}


def test_report_includes_assumption_and_residual_sections():
    module = _load_compare_script_module()
    payload = {
        "status": "pass",
        "timestamp_utc": "2026-02-16T23:00:00Z",
        "constellation_repo": {"git": {"label": "x", "commit": "x", "dirty": "clean"}},
        "gmat_repo": {
            "git": {"label": "y", "commit": "y", "dirty": "clean"},
            "repository_url": "https://example.invalid/gmat",
            "run_id": "run-0000",
        },
        "comparison": {"cases": []},
        "suncentric_extension": {
            "assumption_differences": [
                "Earth-mu mirror used for hyperbolic regime parity.",
                "Dedicated Sun-centric force components remain approximated.",
            ],
            "residual_mismatch_budget": {
                "ecc": "advisory",
                "inc_deg": "advisory",
                "rmag_km": "advisory",
                "energy_sign": "bounded",
            },
        },
    }

    report = module._build_report_markdown(payload)
    assert "## Assumption Differences" in report
    assert "## Residual Mismatch Budget" in report
    assert "Earth-mu mirror used for hyperbolic regime parity." in report
