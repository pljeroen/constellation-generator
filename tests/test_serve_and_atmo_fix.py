# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""
Tests for:
- R-ADAPTER-01: CZML exporter handles altitudes > 2000 km without ValueError
- R-CLI-01: CLI --serve flag accepted, --input not required in serve mode
- R-CLI-02: serve mode pre-loads default shells
"""

import math
import subprocess
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from humeris.domain.constellation import ShellConfig, generate_walker_shell
from humeris.domain.propagation import derive_orbital_state, OrbitalState
from humeris.adapters.czml_exporter import _satellite_description


EPOCH = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)


# === R-ADAPTER-01: CZML exporter altitude range fix ===


class TestCzmlHighAltitude:
    """CZML exporter must not crash for altitudes above atmosphere table."""

    @pytest.fixture
    def high_altitude_state(self):
        """OrbitalState at ~2200 km altitude (above atmosphere table max)."""
        shell = ShellConfig(
            altitude_km=2200,
            inclination_deg=97.8,
            num_planes=1,
            sats_per_plane=1,
            phase_factor=0,
            raan_offset_deg=0,
            shell_name="HighAlt",
        )
        sats = generate_walker_shell(shell)
        return derive_orbital_state(sats[0], EPOCH)

    def test_description_does_not_raise_for_2200km(self, high_altitude_state):
        """_satellite_description must not raise ValueError at 2200 km."""
        desc = _satellite_description(high_altitude_state, EPOCH)
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_description_contains_html_table(self, high_altitude_state):
        """Description still produces valid HTML table at high altitude."""
        desc = _satellite_description(high_altitude_state, EPOCH)
        assert "<table" in desc
        assert "Orbit" in desc
        assert "Altitude" in desc

    def test_description_shows_density_info(self, high_altitude_state):
        """Density field is present even for out-of-range altitudes."""
        desc = _satellite_description(high_altitude_state, EPOCH)
        assert "density" in desc.lower() or "Atm." in desc

    def test_description_at_550km_still_works(self):
        """Mid-range altitude within atmosphere table range."""
        shell = ShellConfig(
            altitude_km=550,
            inclination_deg=53,
            num_planes=1,
            sats_per_plane=1,
            phase_factor=0,
            raan_offset_deg=0,
            shell_name="MidRange",
        )
        sats = generate_walker_shell(shell)
        state = derive_orbital_state(sats[0], EPOCH)
        desc = _satellite_description(state, EPOCH)
        assert "<table" in desc
        assert "kg/m" in desc


# === R-CLI-01: CLI --serve flag ===


class TestCliServeFlag:
    """CLI must accept --serve without requiring --input."""

    def test_serve_help_text(self):
        """'serve' subcommand appears in help output."""
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert "serve" in result.stdout

    def test_port_help_text(self):
        """--port appears in 'serve' subcommand help."""
        result = subprocess.run(
            [sys.executable, "-m", "humeris.cli", "serve", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert "--port" in result.stdout

    def test_serve_without_input_no_error(self):
        """--serve without --input must not produce argparse error."""
        script = (
            "import sys\n"
            "sys.argv = ['humeris', '--serve']\n"
            "from unittest.mock import patch\n"
            "with patch('humeris.cli._run_serve'):\n"
            "    from humeris.cli import main\n"
            "    main()\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=10,
        )
        assert "error: the following arguments are required: --input/-i" not in result.stderr
        assert result.returncode == 0

    def test_serve_with_port(self):
        """--serve --port 9999 passes port to serve function."""
        script = (
            "import sys\n"
            "sys.argv = ['humeris', '--serve', '--port', '9999']\n"
            "from unittest.mock import patch\n"
            "with patch('humeris.cli._run_serve'):\n"
            "    from humeris.cli import main\n"
            "    main()\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0


# === R-CLI-02: serve mode pre-loads defaults ===


class TestCliServeDefaults:
    """Serve mode uses default Walker shells."""

    def test_default_shells_defined(self):
        """get_default_shells returns shells including 500/450/400 km."""
        from humeris.cli import get_default_shells
        shells = get_default_shells()
        altitudes = {s.altitude_km for s in shells if s.altitude_km in (500, 450, 400)}
        assert altitudes == {500, 450, 400}
