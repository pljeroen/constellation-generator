# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.
"""
JSON simulation file I/O adapter.

Reads and writes simulation data in JSON format.
"""
import json
from typing import Any

from humeris.domain.ccsds_contracts import CcsdsEnvelope, roundtrip_envelope
from humeris.ports import SimulationReader, SimulationWriter


class JsonSimulationReader(SimulationReader):
    """Reads simulation data from JSON files."""

    def read_simulation(self, path: str) -> dict[str, Any]:
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def extract_template_entity(self, sim_data: dict, entity_name: str) -> dict:
        entities = sim_data.get('Entities', [])
        for entity in entities:
            if entity.get('Name') == entity_name:
                return entity
        raise ValueError(f"Entity '{entity_name}' not found in simulation data")

    def extract_earth_entity(self, sim_data: dict) -> dict:
        return self.extract_template_entity(sim_data, 'Earth')

    def read_ccsds_envelope(self, path: str) -> CcsdsEnvelope:
        """Read, deserialize, and verify a CCSDS envelope JSON file."""
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        envelope = CcsdsEnvelope(
            message_type=raw["message_type"],
            payload=raw["payload"],
            source_timestamp=raw["source_timestamp"],
            provenance_hash=raw["provenance_hash"],
        )
        # roundtrip_envelope verifies provenance integrity loudly.
        return roundtrip_envelope(envelope)


class JsonSimulationWriter(SimulationWriter):
    """Writes simulation data to JSON files."""

    def write_simulation(self, sim_data: dict, path: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(sim_data, f, indent=2, ensure_ascii=False)

    def write_ccsds_envelope(self, envelope: CcsdsEnvelope, path: str) -> None:
        """Write a CCSDS envelope JSON file preserving provenance metadata."""
        body = {
            "message_type": envelope.message_type,
            "payload": envelope.payload,
            "source_timestamp": envelope.source_timestamp,
            "provenance_hash": envelope.provenance_hash,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(body, f, indent=2, ensure_ascii=False)
