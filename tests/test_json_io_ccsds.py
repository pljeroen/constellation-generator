# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.
"""Adapter-level CCSDS envelope JSON IO interoperability tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from humeris.adapters.json_io import JsonSimulationReader, JsonSimulationWriter
from humeris.domain.ccsds_contracts import envelope_from_record


_OMM = {
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


def test_json_io_roundtrip_ccsds_envelope(tmp_path: Path):
    env = envelope_from_record("OMM", _OMM, source_timestamp="2026-02-16T00:00:00Z")
    p = tmp_path / "omm_envelope.json"

    JsonSimulationWriter().write_ccsds_envelope(env, str(p))
    out = JsonSimulationReader().read_ccsds_envelope(str(p))

    assert out.message_type == "OMM"
    assert out.payload["OBJECT_ID"] == "1998-067A"
    assert out.source_timestamp == "2026-02-16T00:00:00Z"
    assert out.provenance_hash == env.provenance_hash


def test_json_io_rejects_tampered_provenance(tmp_path: Path):
    env = envelope_from_record("OMM", _OMM)
    p = tmp_path / "tampered.json"

    JsonSimulationWriter().write_ccsds_envelope(env, str(p))
    text = p.read_text(encoding="utf-8")
    p.write_text(text.replace(env.provenance_hash, "0" * 64), encoding="utf-8")

    with pytest.raises(ValueError, match="provenance hash mismatch"):
        JsonSimulationReader().read_ccsds_envelope(str(p))
