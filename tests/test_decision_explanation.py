# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""D-P1-03: Operator-facing decision explanation section in reports."""
from __future__ import annotations

import importlib.util
from pathlib import Path



def _load_compare_script_module():
    script_path = Path("scripts/run_gmat_mirror_compare.py").resolve()
    spec = importlib.util.spec_from_file_location("run_gmat_mirror_compare", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_contains_executive_summary_confidence_and_limits():
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
        "executive_summary": {
            "confidence": "0.88",
            "known_limitations": ["sun-centric force parity pending"],
            "next_actions": ["promote CI gate"],
        },
        "replay_bundle": "replay_bundle.json",
    }
    report = module._build_report_markdown(payload)
    assert "## Executive Summary" in report
    assert "Confidence" in report
    assert "known_limitations" not in report
    assert "sun-centric force parity pending" in report
    assert "Replay bundle" in report
    assert "replay_bundle.json" in report
