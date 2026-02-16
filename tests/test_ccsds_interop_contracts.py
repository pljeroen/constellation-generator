# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.
"""D-P0-02: CCSDS OMM/OEM interoperability and provenance contracts."""
from __future__ import annotations

import pytest

from humeris.domain.ccsds_contracts import (
    CcsdsValidationError,
    envelope_from_record,
    roundtrip_envelope,
)


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

_OEM = {
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "CENTER_NAME": "EARTH",
    "REF_FRAME": "EME2000",
    "TIME_SYSTEM": "UTC",
    "EPOCHS": ["2026-02-16T00:00:00Z", "2026-02-16T00:01:00Z"],
    "X": [1.0, 2.0],
    "Y": [3.0, 4.0],
    "Z": [5.0, 6.0],
    "X_DOT": [0.1, 0.2],
    "Y_DOT": [0.3, 0.4],
    "Z_DOT": [0.5, 0.6],
}


def test_omm_roundtrip_preserves_semantics_and_provenance():
    env = envelope_from_record("OMM", _OMM, source_timestamp="2026-02-16T00:00:00Z")
    out = roundtrip_envelope(env)
    assert out.payload["OBJECT_ID"] == _OMM["OBJECT_ID"]
    assert out.source_timestamp == "2026-02-16T00:00:00Z"
    assert out.provenance_hash == env.provenance_hash


def test_oem_roundtrip_preserves_semantics_and_provenance():
    env = envelope_from_record("OEM", _OEM)
    out = roundtrip_envelope(env)
    assert out.payload["REF_FRAME"] == "EME2000"
    assert out.provenance_hash == env.provenance_hash


def test_malformed_near_valid_record_fails_loudly():
    bad = dict(_OMM)
    bad.pop("MEAN_MOTION")
    with pytest.raises(CcsdsValidationError, match="missing required fields"):
        envelope_from_record("OMM", bad)

    bad2 = dict(_OMM)
    bad2["MEAN_MOTION"] = -1.0
    with pytest.raises(CcsdsValidationError, match="must be > 0"):
        envelope_from_record("OMM", bad2)
