# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""CLI selection coverage for conjunction profile packs."""
from __future__ import annotations

import json
import subprocess
import sys


def test_cli_profile_selection_outputs_probability_band():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/conjunction_profile_eval.py",
            "--profile",
            "nominal",
            "--miss-distance-m",
            "9000",
            "--base-pc",
            "2e-5",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    out = json.loads(proc.stdout)
    assert out["profile"]["id"] == "nominal"
    band = out["output"]["collision_probability_band"]
    assert set(band.keys()) == {"lower", "nominal", "upper"}


def test_cli_rejects_invalid_profile_value():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/conjunction_profile_eval.py",
            "--profile",
            "invalid",
            "--miss-distance-m",
            "9000",
            "--base-pc",
            "2e-5",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "invalid choice" in proc.stderr
