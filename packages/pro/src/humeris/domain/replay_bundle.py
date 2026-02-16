# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Deterministic replay bundles for critical parity/compliance runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any



def _is_absolute_path(value: object) -> bool:
    return isinstance(value, str) and (value.startswith("/") or ":\\" in value)



def create_replay_bundle(
    out_dir: Path,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    software_refs: dict[str, str],
) -> Path:
    """Create replay bundle with deterministic payload and integrity hash."""
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": "replay_bundle_v1",
        "inputs": inputs,
        "outputs": outputs,
        "software_refs": software_refs,
    }

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()

    manifest = {
        **payload,
        "bundle_hash": digest,
    }
    path = out_dir / "replay_bundle.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path



def replay_bundle(bundle_path: Path) -> dict[str, Any]:
    """Load and verify replay bundle; fail if integrity/path constraints break."""
    manifest = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle_hash = manifest.pop("bundle_hash")

    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected = hashlib.sha256(encoded).hexdigest()
    if bundle_hash != expected:
        raise ValueError("Replay bundle hash mismatch")

    def walk(obj: object) -> None:
        if _is_absolute_path(obj):
            raise ValueError("Replay bundle contains absolute filesystem path")
        if isinstance(obj, dict):
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(manifest)
    return manifest
