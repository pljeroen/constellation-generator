# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Tests for interactive viewer server.

HTTP server serving Cesium viewer with on-demand CZML generation,
dynamic constellation management, and analysis layer control.
"""

import ast
import json
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from http.client import HTTPResponse
from unittest.mock import patch

import pytest

from humeris.domain.constellation import (
    ShellConfig,
    generate_walker_shell,
)
from humeris.domain.propagation import derive_orbital_state


EPOCH = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)


def _make_states(n_planes=2, n_sats=2, altitude_km=550):
    """Create a small set of orbital states for testing."""
    shell = ShellConfig(
        altitude_km=altitude_km, inclination_deg=53,
        num_planes=n_planes, sats_per_plane=n_sats,
        phase_factor=1, raan_offset_deg=0, shell_name="Test",
    )
    sats = generate_walker_shell(shell)
    return [derive_orbital_state(s, EPOCH) for s in sats]


# ---------------------------------------------------------------------------
# Layer state management
# ---------------------------------------------------------------------------


class TestLayerState:
    """Tests for LayerState dataclass."""

    def test_layer_state_creation(self):
        from humeris.adapters.viewer_server import LayerState
        layer = LayerState(
            layer_id="walker-1",
            name="Constellation:Walker-550",
            category="Constellation",
            layer_type="walker",
            mode="animated",
            visible=True,
            states=_make_states(),
            params={"altitude_km": 550},
            czml=[{"id": "document", "version": "1.0"}],
        )
        assert layer.layer_id == "walker-1"
        assert layer.name == "Constellation:Walker-550"
        assert layer.category == "Constellation"
        assert layer.layer_type == "walker"
        assert layer.mode == "animated"
        assert layer.visible is True
        assert len(layer.states) == 4
        assert layer.params == {"altitude_km": 550}
        assert len(layer.czml) == 1

    def test_layer_state_defaults(self):
        from humeris.adapters.viewer_server import LayerState
        layer = LayerState(
            layer_id="test",
            name="Test",
            category="Test",
            layer_type="walker",
            mode="snapshot",
            visible=True,
            states=[],
            params={},
            czml=[],
        )
        assert layer.czml == []
        assert layer.states == []


class TestLayerManager:
    """Tests for layer management functions."""

    def test_add_layer(self):
        from humeris.adapters.viewer_server import (
            LayerManager,
            LayerState,
        )
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Constellation:Walker",
            category="Constellation",
            layer_type="walker",
            states=states,
            params={"altitude_km": 550},
        )
        assert layer_id is not None
        assert layer_id in mgr.layers

    def test_add_layer_auto_mode_animated_small(self):
        """<=100 sats default to animated mode."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states(n_planes=2, n_sats=2)  # 4 sats
        layer_id = mgr.add_layer(
            name="Constellation:Small",
            category="Constellation",
            layer_type="walker",
            states=states,
            params={},
        )
        assert mgr.layers[layer_id].mode == "animated"

    def test_add_layer_auto_mode_snapshot_large(self):
        """>100 sats default to snapshot mode."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states(n_planes=6, n_sats=20)  # 120 sats
        layer_id = mgr.add_layer(
            name="Constellation:Large",
            category="Constellation",
            layer_type="walker",
            states=states,
            params={},
        )
        assert mgr.layers[layer_id].mode == "snapshot"

    def test_add_layer_explicit_mode(self):
        """Explicit mode overrides auto-detection."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Test",
            category="Constellation",
            layer_type="walker",
            states=states,
            params={},
            mode="snapshot",
        )
        assert mgr.layers[layer_id].mode == "snapshot"

    def test_add_layer_generates_czml(self):
        """Adding a layer generates CZML packets."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Constellation:Walker",
            category="Constellation",
            layer_type="walker",
            states=states,
            params={},
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 0
        assert czml[0]["id"] == "document"

    def test_remove_layer(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Test", category="Test", layer_type="walker",
            states=states, params={},
        )
        assert layer_id in mgr.layers
        mgr.remove_layer(layer_id)
        assert layer_id not in mgr.layers

    def test_remove_nonexistent_layer_raises(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        with pytest.raises(KeyError):
            mgr.remove_layer("nonexistent")

    def test_update_layer_visibility(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Test", category="Test", layer_type="walker",
            states=states, params={},
        )
        mgr.update_layer(layer_id, visible=False)
        assert mgr.layers[layer_id].visible is False

    def test_update_layer_mode_regenerates_czml(self):
        """Switching mode regenerates CZML."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Constellation:Test",
            category="Constellation",
            layer_type="walker",
            states=states,
            params={},
            mode="animated",
        )
        old_czml = mgr.layers[layer_id].czml
        mgr.update_layer(layer_id, mode="snapshot")
        new_czml = mgr.layers[layer_id].czml
        assert mgr.layers[layer_id].mode == "snapshot"
        # CZML should be different after mode change
        assert new_czml != old_czml

    def test_update_nonexistent_layer_raises(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        with pytest.raises(KeyError):
            mgr.update_layer("nonexistent", visible=False)

    def test_get_state_returns_all_layers_metadata(self):
        """get_state() returns layer metadata without CZML data."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        mgr.add_layer(
            name="Constellation:A", category="Constellation",
            layer_type="walker", states=states, params={},
        )
        mgr.add_layer(
            name="Analysis:Eclipse", category="Analysis",
            layer_type="eclipse", states=states, params={},
        )
        state = mgr.get_state()
        assert len(state["layers"]) == 2
        for layer_info in state["layers"]:
            assert "layer_id" in layer_info
            assert "name" in layer_info
            assert "category" in layer_info
            assert "mode" in layer_info
            assert "visible" in layer_info
            assert "num_entities" in layer_info
            # No CZML data in state response
            assert "czml" not in layer_info

    def test_get_czml_for_layer(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Test", category="Test", layer_type="walker",
            states=states, params={},
        )
        czml = mgr.get_czml(layer_id)
        assert isinstance(czml, list)
        assert len(czml) > 0
        assert czml[0]["id"] == "document"

    def test_get_czml_nonexistent_raises(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        with pytest.raises(KeyError):
            mgr.get_czml("nonexistent")

    def test_unique_layer_ids(self):
        """Each add_layer call produces a unique ID."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        ids = set()
        for i in range(5):
            layer_id = mgr.add_layer(
                name=f"Test:{i}", category="Test", layer_type="walker",
                states=states, params={},
            )
            ids.add(layer_id)
        assert len(ids) == 5


# ---------------------------------------------------------------------------
# CZML generation dispatch
# ---------------------------------------------------------------------------


class TestCzmlDispatch:
    """Tests for CZML generation dispatch based on layer type and mode."""

    def test_walker_snapshot_dispatch(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Constellation:Walker",
            category="Constellation",
            layer_type="walker",
            states=states,
            params={},
            mode="snapshot",
        )
        czml = mgr.layers[layer_id].czml
        # Snapshot packets: document + 1 per sat, no path/interpolation
        assert czml[0]["id"] == "document"
        # Snapshot points use point.pixelSize, not path
        sat_packet = czml[1]
        assert "point" in sat_packet
        assert "position" in sat_packet

    def test_walker_animated_dispatch(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Constellation:Walker",
            category="Constellation",
            layer_type="walker",
            states=states,
            params={},
            mode="animated",
        )
        czml = mgr.layers[layer_id].czml
        assert czml[0]["id"] == "document"
        # Animated packets have time-varying position (cartographicDegrees array)
        sat_packet = czml[1]
        assert "position" in sat_packet

    def test_eclipse_snapshot_dispatch(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Eclipse",
            category="Analysis",
            layer_type="eclipse",
            states=states,
            params={},
            mode="snapshot",
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 0
        assert czml[0]["id"] == "document"

    def test_eclipse_animated_dispatch(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Eclipse",
            category="Analysis",
            layer_type="eclipse",
            states=states,
            params={},
            mode="animated",
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 0
        assert czml[0]["id"] == "document"

    def test_coverage_dispatch(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Coverage",
            category="Analysis",
            layer_type="coverage",
            states=states,
            params={"lat_step_deg": 30.0, "lon_step_deg": 30.0},
            mode="snapshot",
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 0
        assert czml[0]["id"] == "document"

    def test_ground_track_dispatch(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:GroundTrack",
            category="Analysis",
            layer_type="ground_track",
            states=states,
            params={},
            mode="snapshot",
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 0
        assert czml[0]["id"] == "document"

    def test_ground_station_layer(self):
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_ground_station(
            name="Svalbard",
            lat_deg=78.23,
            lon_deg=15.39,
            source_states=states,
        )
        assert layer_id in mgr.layers
        layer = mgr.layers[layer_id]
        assert layer.category == "Ground Station"
        assert len(layer.czml) > 0

    def test_sensor_dispatch(self):
        """Sensor footprint layer generates CZML with entity packets."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Sensor", category="Analysis",
            layer_type="sensor", states=states, params={},
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 1
        assert czml[0]["id"] == "document"

    def test_isl_dispatch(self):
        """ISL topology layer generates CZML with entity packets."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:ISL", category="Analysis",
            layer_type="isl", states=states, params={},
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 1
        assert czml[0]["id"] == "document"

    def test_fragility_dispatch(self):
        """Fragility layer generates CZML with entity packets."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Fragility", category="Analysis",
            layer_type="fragility", states=states, params={},
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 1
        assert czml[0]["id"] == "document"

    def test_hazard_dispatch(self):
        """Hazard evolution layer generates CZML with entity packets."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Hazard", category="Analysis",
            layer_type="hazard", states=states, params={},
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 1
        assert czml[0]["id"] == "document"

    def test_network_eclipse_dispatch(self):
        """Network eclipse layer generates CZML with entity packets."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Network Eclipse", category="Analysis",
            layer_type="network_eclipse", states=states, params={},
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 1
        assert czml[0]["id"] == "document"

    def test_coverage_connectivity_dispatch(self):
        """Coverage connectivity layer generates CZML (doc + possible entities)."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Coverage Connectivity", category="Analysis",
            layer_type="coverage_connectivity", states=states, params={},
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) >= 1
        assert czml[0]["id"] == "document"

    def test_precession_dispatch(self):
        """Precession layer generates CZML with entity packets."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Precession", category="Analysis",
            layer_type="precession", states=states, params={},
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 1
        assert czml[0]["id"] == "document"

    def test_conjunction_dispatch(self):
        """Conjunction replay layer generates CZML with entity packets."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Conjunction", category="Analysis",
            layer_type="conjunction", states=states, params={},
        )
        czml = mgr.layers[layer_id].czml
        assert len(czml) > 1
        assert czml[0]["id"] == "document"


# ---------------------------------------------------------------------------
# HTTP server + API
# ---------------------------------------------------------------------------


def _start_server(port):
    """Start viewer server on given port, return (server, thread)."""
    from humeris.adapters.viewer_server import (
        create_viewer_server,
        LayerManager,
    )
    mgr = LayerManager(epoch=EPOCH)
    server = create_viewer_server(mgr, port=port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Wait for server to be ready
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://localhost:{port}/api/state", timeout=1)
            break
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.05)
    return server, mgr


def _api_request(port, method, path, body=None):
    """Make HTTP request to server, return (status, parsed_json_or_text)."""
    url = f"http://localhost:{port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        content = resp.read().decode()
        try:
            return resp.status, json.loads(content)
        except json.JSONDecodeError:
            return resp.status, content
    except urllib.error.HTTPError as e:
        content = e.read().decode()
        try:
            return e.code, json.loads(content)
        except json.JSONDecodeError:
            return e.code, content


@pytest.fixture
def server_port():
    """Find a free port for testing."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def running_server(server_port):
    """Start server, yield (port, manager), shutdown after test."""
    server, mgr = _start_server(server_port)
    yield server_port, mgr
    server.shutdown()


class TestHttpApi:
    """Tests for HTTP API endpoints."""

    def test_get_root_returns_html(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "GET", "/")
        assert status == 200
        assert "<!DOCTYPE html>" in body

    def test_get_state_empty(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "GET", "/api/state")
        assert status == 200
        assert body["layers"] == []

    def test_post_constellation_walker(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550,
                "inclination_deg": 53,
                "num_planes": 2,
                "sats_per_plane": 2,
                "phase_factor": 1,
                "raan_offset_deg": 0,
                "shell_name": "Test-Walker",
            },
        })
        assert status == 201
        assert "layer_id" in body

        # Verify it appears in state
        status, state = _api_request(port, "GET", "/api/state")
        assert len(state["layers"]) == 1
        assert state["layers"][0]["category"] == "Constellation"

    def test_post_analysis_eclipse(self, running_server):
        port, mgr = running_server
        # First add a constellation as source
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Source",
            },
        })
        source_id = body["layer_id"]

        # Add eclipse analysis
        status, body = _api_request(port, "POST", "/api/analysis", {
            "type": "eclipse",
            "source_layer": source_id,
            "params": {},
        })
        assert status == 201
        assert "layer_id" in body

    def test_post_ground_station(self, running_server):
        port, mgr = running_server
        # Need a constellation for ground station access computation
        _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Src",
            },
        })
        status, body = _api_request(port, "POST", "/api/ground-station", {
            "name": "Svalbard",
            "lat": 78.23,
            "lon": 15.39,
        })
        assert status == 201
        assert "layer_id" in body

    def test_get_czml_for_layer(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Test",
            },
        })
        layer_id = body["layer_id"]
        status, czml = _api_request(port, "GET", f"/api/czml/{layer_id}")
        assert status == 200
        assert isinstance(czml, list)
        assert czml[0]["id"] == "document"

    def test_put_layer_update_mode(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Test",
            },
        })
        layer_id = body["layer_id"]
        status, body = _api_request(port, "PUT", f"/api/layer/{layer_id}", {
            "mode": "snapshot",
        })
        assert status == 200
        assert body["mode"] == "snapshot"

    def test_put_layer_update_visibility(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Test",
            },
        })
        layer_id = body["layer_id"]
        status, body = _api_request(port, "PUT", f"/api/layer/{layer_id}", {
            "visible": False,
        })
        assert status == 200
        assert body["visible"] is False

    def test_delete_layer(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Test",
            },
        })
        layer_id = body["layer_id"]
        status, body = _api_request(port, "DELETE", f"/api/layer/{layer_id}")
        assert status == 200

        # Verify removed
        status, state = _api_request(port, "GET", "/api/state")
        assert len(state["layers"]) == 0

    def test_get_czml_nonexistent_returns_404(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "GET", "/api/czml/nonexistent")
        assert status == 404

    def test_delete_nonexistent_returns_404(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "DELETE", "/api/layer/nonexistent")
        assert status == 404

    def test_post_constellation_invalid_type_returns_400(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "invalid_type",
            "params": {},
        })
        assert status == 400

    def test_post_analysis_missing_source_returns_400(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "POST", "/api/analysis", {
            "type": "eclipse",
            "source_layer": "nonexistent",
            "params": {},
        })
        assert status == 404

    def test_cors_headers_present(self, running_server):
        """CORS headers allow local browser access."""
        port, mgr = running_server
        url = f"http://localhost:{port}/api/state"
        resp = urllib.request.urlopen(url, timeout=5)
        assert resp.headers.get("Access-Control-Allow-Origin") == f"http://localhost:{port}"

    def test_state_includes_epoch(self, running_server):
        port, mgr = running_server
        status, body = _api_request(port, "GET", "/api/state")
        assert "epoch" in body


# ---------------------------------------------------------------------------
# Purity
# ---------------------------------------------------------------------------


class TestThreadedServer:
    """Verify the server uses ThreadingMixIn for concurrent requests."""

    def test_server_uses_threading_mixin(self):
        """Server should use ThreadingMixIn so analysis doesn't block UI."""
        from humeris.adapters.viewer_server import create_viewer_server, LayerManager
        import socketserver
        mgr = LayerManager(epoch=EPOCH)
        server = create_viewer_server(mgr, port=0)
        assert isinstance(server, socketserver.ThreadingMixIn), \
            "Server should use ThreadingMixIn"
        server.server_close()


class TestCapMetadata:
    """Verify cap metadata is surfaced when satellite count is capped."""

    def test_state_includes_capped_from_for_isl(self):
        """When ISL caps satellite count, state response shows original count."""
        from humeris.adapters.viewer_server import LayerManager, _MAX_TOPOLOGY_SATS
        mgr = LayerManager(epoch=EPOCH)
        # Create enough states to trigger capping
        states = _make_states(n_planes=6, n_sats=20)  # 120 > _MAX_TOPOLOGY_SATS
        assert len(states) > _MAX_TOPOLOGY_SATS

        layer_id = mgr.add_layer(
            name="Analysis:ISL", category="Analysis",
            layer_type="isl", states=states, params={},
        )
        state = mgr.get_state()
        layer_info = [l for l in state["layers"] if l["layer_id"] == layer_id][0]
        assert "capped_from" in layer_info, \
            "Layer state should include capped_from when satellite count is capped"
        assert layer_info["capped_from"] == len(states)

    def test_state_includes_capped_from_for_precession(self):
        """When precession caps satellite count, state response shows original count."""
        from humeris.adapters.viewer_server import LayerManager, _MAX_PRECESSION_SATS
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states(n_planes=6, n_sats=20)  # 120 > _MAX_PRECESSION_SATS
        assert len(states) > _MAX_PRECESSION_SATS

        layer_id = mgr.add_layer(
            name="Analysis:Precession", category="Analysis",
            layer_type="precession", states=states, params={},
        )
        state = mgr.get_state()
        layer_info = [l for l in state["layers"] if l["layer_id"] == layer_id][0]
        assert "capped_from" in layer_info
        assert layer_info["capped_from"] == len(states)

    def test_no_capped_from_when_under_limit(self):
        """No capped_from when satellite count is under the cap."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states(n_planes=2, n_sats=2)  # 4 sats
        layer_id = mgr.add_layer(
            name="Analysis:ISL", category="Analysis",
            layer_type="isl", states=states, params={},
        )
        state = mgr.get_state()
        layer_info = [l for l in state["layers"] if l["layer_id"] == layer_id][0]
        assert "capped_from" not in layer_info


class TestErrorForwarding:
    """Verify analysis errors include actual error message."""

    def test_analysis_error_includes_details(self, running_server):
        """Analysis failure should include the actual error message, not generic text."""
        port, mgr = running_server
        # Add a source constellation first
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Err-Test",
            },
        })
        source_id = body["layer_id"]

        # Patch _generate_czml to raise an error
        with patch(
            "humeris.adapters.viewer_server._generate_czml",
            side_effect=ValueError("test error detail"),
        ):
            status, body = _api_request(port, "POST", "/api/analysis", {
                "type": "eclipse",
                "source_layer": source_id,
                "params": {},
            })
        assert status == 500
        assert "test error detail" in body.get("error", ""), \
            f"Error response should contain actual error: {body}"


class TestAnalysisParamsPassthrough:
    """Verify analysis params from request are passed to _generate_czml."""

    def test_coverage_params_passed(self):
        """Coverage analysis params (lat_step, lon_step, min_elev) should pass through."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        # First add a constellation as source
        source_id = mgr.add_layer(
            name="Constellation:Source", category="Constellation",
            layer_type="walker", states=states, params={},
        )
        # Now add coverage with explicit params
        layer_id = mgr.add_layer(
            name="Analysis:Coverage", category="Analysis",
            layer_type="coverage", states=states,
            params={"lat_step_deg": 20.0, "lon_step_deg": 20.0, "min_elevation_deg": 15.0},
        )
        layer = mgr.layers[layer_id]
        # The params should have been stored and used
        assert layer.params.get("lat_step_deg") == 20.0
        assert layer.params.get("lon_step_deg") == 20.0
        assert layer.params.get("min_elevation_deg") == 15.0

    def test_isl_max_range_passed(self):
        """ISL analysis max_range_km param should pass through."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:ISL", category="Analysis",
            layer_type="isl", states=states,
            params={"max_range_km": 3000.0},
        )
        layer = mgr.layers[layer_id]
        assert layer.params.get("max_range_km") == 3000.0

    def test_analysis_api_forwards_params(self, running_server):
        """POST /api/analysis should forward params to the layer."""
        port, mgr = running_server
        # Add source
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "ParamTest",
            },
        })
        source_id = body["layer_id"]

        # Add coverage with params
        status, body = _api_request(port, "POST", "/api/analysis", {
            "type": "coverage",
            "source_layer": source_id,
            "params": {"lat_step_deg": 20.0, "lon_step_deg": 20.0},
        })
        assert status == 201
        layer_id = body["layer_id"]

        # Check state includes the params
        status, state = _api_request(port, "GET", "/api/state")
        layer_info = [l for l in state["layers"] if l["layer_id"] == layer_id][0]
        assert layer_info["params"].get("lat_step_deg") == 20.0


class TestColorLegendData:
    """Verify color legend metadata is available in state response."""

    def test_state_includes_legend_for_eclipse(self):
        """Eclipse analysis layers should include legend color mapping."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Eclipse", category="Analysis",
            layer_type="eclipse", states=states, params={},
        )
        state = mgr.get_state()
        layer_info = [l for l in state["layers"] if l["layer_id"] == layer_id][0]
        assert "legend" in layer_info, \
            "Eclipse layer should include legend data in state response"

    def test_legend_has_entries(self):
        """Legend should have label+color entries."""
        from humeris.adapters.viewer_server import LayerManager
        mgr = LayerManager(epoch=EPOCH)
        states = _make_states()
        layer_id = mgr.add_layer(
            name="Analysis:Eclipse", category="Analysis",
            layer_type="eclipse", states=states, params={},
        )
        state = mgr.get_state()
        layer_info = [l for l in state["layers"] if l["layer_id"] == layer_id][0]
        legend = layer_info["legend"]
        assert len(legend) > 0
        assert "label" in legend[0]
        assert "color" in legend[0]


class TestExportEndpoint:
    """Verify CZML export endpoint."""

    def test_export_czml_returns_downloadable(self, running_server):
        """GET /api/export/{layer_id} should return CZML as downloadable JSON."""
        port, mgr = running_server
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Export-Test",
            },
        })
        layer_id = body["layer_id"]
        status, czml = _api_request(port, "GET", f"/api/export/{layer_id}")
        assert status == 200
        assert isinstance(czml, list)
        assert czml[0]["id"] == "document"

    def test_export_nonexistent_returns_404(self, running_server):
        """GET /api/export/nonexistent should return 404."""
        port, mgr = running_server
        status, body = _api_request(port, "GET", "/api/export/nonexistent")
        assert status == 404


class TestGroundStationSatLimit:
    """Verify ground station satellite limit is configurable."""

    def test_ground_station_uses_more_than_six_sats(self, running_server):
        """Ground station should use configurable sat limit, not hardcoded 6."""
        port, mgr = running_server
        # Add a large constellation
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 4, "sats_per_plane": 5,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "GS-Test",
            },
        })
        source_id = body["layer_id"]
        source_layer = mgr.layers[source_id]
        assert len(source_layer.states) == 20

        # Add ground station — should use more than 6 sats
        status, body = _api_request(port, "POST", "/api/ground-station", {
            "name": "Test", "lat": 0.0, "lon": 0.0,
        })
        assert status == 201
        gs_layer = mgr.layers[body["layer_id"]]
        # The ground station should have access to more than 6 source states
        assert len(gs_layer.states) > 6, \
            f"Ground station only got {len(gs_layer.states)} sats, should be >6"


class TestSessionSaveLoad:
    """Verify session save/load endpoints."""

    def test_save_session_returns_data(self, running_server):
        """POST /api/session/save should return serializable session data."""
        port, mgr = running_server
        # Add a constellation
        _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Save-Test",
            },
        })
        status, body = _api_request(port, "POST", "/api/session/save")
        assert status == 200
        assert "session" in body
        assert "layers" in body["session"]

    def test_load_session_restores_layers(self, running_server):
        """POST /api/session/load should restore previously saved session."""
        port, mgr = running_server
        # Add a constellation
        _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Load-Test",
            },
        })
        # Save
        _, save_resp = _api_request(port, "POST", "/api/session/save")
        session_data = save_resp["session"]

        # Clear all layers
        _, state = _api_request(port, "GET", "/api/state")
        for layer in state["layers"]:
            _api_request(port, "DELETE", f"/api/layer/{layer['layer_id']}")

        # Verify empty
        _, state = _api_request(port, "GET", "/api/state")
        assert len(state["layers"]) == 0

        # Load
        status, body = _api_request(port, "POST", "/api/session/load", {
            "session": session_data,
        })
        assert status == 200

        # Verify restored
        _, state = _api_request(port, "GET", "/api/state")
        assert len(state["layers"]) >= 1


class TestAnalysisRecompute:
    """Verify analysis recomputation with updated params."""

    def test_put_analysis_updates_params_and_regenerates(self, running_server):
        """PUT /api/analysis/{layer_id} should update params and regenerate CZML."""
        port, mgr = running_server
        # Add source
        status, body = _api_request(port, "POST", "/api/constellation", {
            "type": "walker",
            "params": {
                "altitude_km": 550, "inclination_deg": 53,
                "num_planes": 2, "sats_per_plane": 2,
                "phase_factor": 1, "raan_offset_deg": 0,
                "shell_name": "Recomp-Test",
            },
        })
        source_id = body["layer_id"]

        # Add coverage analysis
        status, body = _api_request(port, "POST", "/api/analysis", {
            "type": "coverage",
            "source_layer": source_id,
            "params": {"lat_step_deg": 10.0, "lon_step_deg": 10.0},
        })
        analysis_id = body["layer_id"]

        # Get original CZML
        _, original_czml = _api_request(port, "GET", f"/api/czml/{analysis_id}")

        # Recompute with different params
        status, body = _api_request(port, "PUT", f"/api/analysis/{analysis_id}", {
            "params": {"lat_step_deg": 30.0, "lon_step_deg": 30.0},
        })
        assert status == 200

        # CZML should be different
        _, new_czml = _api_request(port, "GET", f"/api/czml/{analysis_id}")
        assert new_czml != original_czml, "CZML should change after param update"


class TestDurationStepSettings:
    """Verify global simulation duration/step settings endpoint."""

    def test_state_includes_duration_step(self, running_server):
        """GET /api/state should include current duration and step settings."""
        port, mgr = running_server
        status, state = _api_request(port, "GET", "/api/state")
        assert "duration_s" in state, "State should include duration_s"
        assert "step_s" in state, "State should include step_s"

    def test_put_settings_updates_duration(self, running_server):
        """PUT /api/settings should update duration and step."""
        port, mgr = running_server
        status, body = _api_request(port, "PUT", "/api/settings", {
            "duration_s": 14400,  # 4 hours
            "step_s": 120,  # 2 minutes
        })
        assert status == 200

        # Verify state reflects new settings
        _, state = _api_request(port, "GET", "/api/state")
        assert state["duration_s"] == 14400
        assert state["step_s"] == 120


class TestViewerServerPurity:
    """Adapter purity: only stdlib + internal imports allowed."""

    def test_no_external_deps(self):
        import humeris.adapters.viewer_server as mod

        with open(mod.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        allowed_stdlib = {
            "json", "http", "threading", "datetime", "dataclasses",
            "uuid", "urllib", "functools", "math", "numpy", "logging", "typing",
            "socketserver",
        }
        allowed_internal = {"humeris"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top in allowed_stdlib or top in allowed_internal, \
                        f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    top = node.module.split(".")[0]
                    assert top in allowed_stdlib or top in allowed_internal, \
                        f"Forbidden import from: {node.module}"
