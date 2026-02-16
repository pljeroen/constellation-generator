# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""D-P1-02: Deterministic replay bundle generation and replay."""
from __future__ import annotations

from pathlib import Path

import pytest

from humeris.domain.replay_bundle import create_replay_bundle, replay_bundle


def test_replay_bundle_roundtrip_is_deterministic(tmp_path: Path):
    path = create_replay_bundle(
        out_dir=tmp_path,
        inputs={"scenario": "advanced_oumuamua_suncentric", "config": "relative/path.json"},
        outputs={"metric": 1.234},
        software_refs={"constellation_generator": "6fb66bc", "gmat": "d9025c0"},
    )
    out = replay_bundle(path)
    assert out["inputs"]["scenario"] == "advanced_oumuamua_suncentric"
    assert out["software_refs"]["gmat"] == "d9025c0"


def test_replay_bundle_rejects_absolute_paths(tmp_path: Path):
    path = create_replay_bundle(
        out_dir=tmp_path,
        inputs={"config": "/absolute/path/not_allowed.json"},
        outputs={"metric": 1.0},
        software_refs={"constellation_generator": "6fb66bc"},
    )
    with pytest.raises(ValueError, match="absolute filesystem path"):
        replay_bundle(path)
