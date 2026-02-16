# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.
"""CCSDS OMM/OEM contract validation with provenance retention."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class CcsdsValidationError(ValueError):
    """Raised when a CCSDS record is malformed or contract-violating."""


_REQUIRED_OMM_FIELDS = {
    "OBJECT_NAME",
    "OBJECT_ID",
    "NORAD_CAT_ID",
    "EPOCH",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
}

_REQUIRED_OEM_FIELDS = {
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "TIME_SYSTEM",
    "EPOCHS",
    "X",
    "Y",
    "Z",
    "X_DOT",
    "Y_DOT",
    "Z_DOT",
}


@dataclass(frozen=True)
class CcsdsEnvelope:
    """CCSDS record with stable provenance metadata."""

    message_type: str
    payload: dict[str, Any]
    source_timestamp: str
    provenance_hash: str



def _stable_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()



def _require_fields(record: dict[str, Any], required_fields: set[str], message_type: str) -> None:
    missing = sorted(f for f in required_fields if f not in record)
    if missing:
        raise CcsdsValidationError(
            f"{message_type} missing required fields: {', '.join(missing)}"
        )



def _validate_numeric_positive(record: dict[str, Any], key: str, message_type: str) -> None:
    value = record.get(key)
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise CcsdsValidationError(f"{message_type} field {key} must be numeric") from exc
    if f <= 0.0:
        raise CcsdsValidationError(f"{message_type} field {key} must be > 0")



def validate_omm_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate OMM-like record and return shallow copy on success."""
    _require_fields(record, _REQUIRED_OMM_FIELDS, "OMM")
    _validate_numeric_positive(record, "MEAN_MOTION", "OMM")
    ecc = float(record["ECCENTRICITY"])
    if ecc < 0.0:
        raise CcsdsValidationError("OMM field ECCENTRICITY must be >= 0")
    return dict(record)



def validate_oem_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate OEM-like record and return shallow copy on success."""
    _require_fields(record, _REQUIRED_OEM_FIELDS, "OEM")
    epochs = record["EPOCHS"]
    if not isinstance(epochs, list) or not epochs:
        raise CcsdsValidationError("OEM field EPOCHS must be a non-empty list")
    for key in ("X", "Y", "Z", "X_DOT", "Y_DOT", "Z_DOT"):
        series = record[key]
        if not isinstance(series, list) or len(series) != len(epochs):
            raise CcsdsValidationError(
                f"OEM field {key} must be list matching EPOCHS length"
            )
    return dict(record)



def envelope_from_record(message_type: str, record: dict[str, Any], source_timestamp: str | None = None) -> CcsdsEnvelope:
    """Create a provenance-carrying envelope from a validated CCSDS record."""
    normalized_type = message_type.upper()
    if normalized_type == "OMM":
        payload = validate_omm_record(record)
    elif normalized_type == "OEM":
        payload = validate_oem_record(record)
    else:
        raise CcsdsValidationError(f"Unsupported message type: {message_type}")

    ts = source_timestamp or datetime.now(UTC).isoformat()
    return CcsdsEnvelope(
        message_type=normalized_type,
        payload=payload,
        source_timestamp=ts,
        provenance_hash=_stable_hash(payload),
    )



def roundtrip_envelope(envelope: CcsdsEnvelope) -> CcsdsEnvelope:
    """Serialize and deserialize envelope while preserving required semantics."""
    blob = json.dumps(
        {
            "message_type": envelope.message_type,
            "payload": envelope.payload,
            "source_timestamp": envelope.source_timestamp,
            "provenance_hash": envelope.provenance_hash,
        },
        sort_keys=True,
    )
    raw = json.loads(blob)
    # Fail loudly if provenance no longer matches payload.
    expected = _stable_hash(raw["payload"])
    if raw["provenance_hash"] != expected:
        raise CcsdsValidationError("Envelope provenance hash mismatch after transform")
    return CcsdsEnvelope(
        message_type=raw["message_type"],
        payload=raw["payload"],
        source_timestamp=raw["source_timestamp"],
        provenance_hash=raw["provenance_hash"],
    )
