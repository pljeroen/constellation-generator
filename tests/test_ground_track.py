"""
Tests for ground track computation.

Verifies Keplerian propagation to geodetic coordinates for circular orbits.
"""
import ast
import math
from datetime import datetime, timedelta, timezone

import pytest

from constellation_generator.domain.constellation import ShellConfig, generate_walker_shell
from constellation_generator.domain.ground_track import (
    GroundTrackPoint,
    compute_ground_track,
)


class TestGroundTrackPoint:
    """GroundTrackPoint is an immutable value object."""

    def test_frozen_dataclass(self):
        point = GroundTrackPoint(
            time=datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
            lat_deg=0.0,
            lon_deg=0.0,
            alt_km=500.0,
        )
        with pytest.raises(AttributeError):
            point.lat_deg = 10.0

    def test_fields(self):
        t = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        point = GroundTrackPoint(time=t, lat_deg=45.0, lon_deg=-90.0, alt_km=550.0)
        assert point.time == t
        assert point.lat_deg == 45.0
        assert point.lon_deg == -90.0
        assert point.alt_km == 550.0


def _make_satellite(inclination_deg=53.0, altitude_km=500.0):
    shell = ShellConfig(
        altitude_km=altitude_km, inclination_deg=inclination_deg,
        num_planes=1, sats_per_plane=1,
        phase_factor=0, raan_offset_deg=0,
        shell_name='Test',
    )
    return generate_walker_shell(shell)[0]


class TestGroundTrackPointCount:
    """Point count matches time range and step."""

    def test_point_count_90_min(self):
        sat = _make_satellite()
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=90), timedelta(minutes=1))
        assert len(track) == 91  # 0, 1, 2, ..., 90

    def test_point_count_zero_duration(self):
        sat = _make_satellite()
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(0), timedelta(minutes=1))
        assert len(track) == 1  # just the start point

    def test_point_count_single_step(self):
        sat = _make_satellite()
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=5), timedelta(minutes=5))
        assert len(track) == 2  # start and end


class TestGroundTrackLatitude:
    """Latitude bounded by orbital inclination for circular orbits."""

    def test_latitude_bounded_by_inclination(self):
        """For a 53 deg inclined orbit, latitude stays within +/-53 deg (with small geodetic margin)."""
        sat = _make_satellite(inclination_deg=53.0)
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=90), timedelta(minutes=1))

        # Geodetic latitude can slightly exceed geocentric inclination due to
        # WGS84 flattening, but the difference is small (~0.2 deg)
        for point in track:
            assert abs(point.lat_deg) <= 53.5, f"Latitude {point.lat_deg} exceeds inclination bound"

    def test_equatorial_orbit_near_zero_latitude(self):
        """A 0 deg inclined orbit should have latitude near 0 deg."""
        sat = _make_satellite(inclination_deg=0.0)
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=90), timedelta(minutes=1))

        for point in track:
            assert abs(point.lat_deg) < 1.0, f"Equatorial orbit lat {point.lat_deg} too high"


class TestGroundTrackAltitude:
    """Altitude consistent for circular orbits."""

    def test_altitude_consistent(self):
        """For a circular orbit at 500km, altitude should stay near 500km."""
        sat = _make_satellite(altitude_km=500.0)
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=90), timedelta(minutes=1))

        for point in track:
            # Mean radius vs WGS84 ellipsoid gives up to ~20km difference
            assert 470 < point.alt_km < 530, f"Altitude {point.alt_km} km outside expected range"


class TestGroundTrackLongitude:
    """Longitude varies over a full orbit."""

    def test_longitude_varies(self):
        """Over 90 minutes, longitude should change significantly."""
        sat = _make_satellite()
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=90), timedelta(minutes=1))

        lons = [p.lon_deg for p in track]
        lon_range = max(lons) - min(lons)
        assert lon_range > 30, f"Longitude range {lon_range} deg too narrow for full orbit"

    def test_longitude_in_range(self):
        """Longitude should be in [-180, 180]."""
        sat = _make_satellite()
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=180), timedelta(minutes=1))

        for point in track:
            assert -180.0 <= point.lon_deg <= 180.0


class TestGroundTrackEdgeCases:
    """Edge cases for ground track computation."""

    def test_negative_step_raises(self):
        sat = _make_satellite()
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            compute_ground_track(sat, start, timedelta(minutes=90), timedelta(minutes=-1))

    def test_zero_step_raises(self):
        sat = _make_satellite()
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            compute_ground_track(sat, start, timedelta(minutes=90), timedelta(0))

    def test_epoch_none_uses_start(self):
        """Satellites with epoch=None should still produce valid ground tracks."""
        sat = _make_satellite()
        assert sat.epoch is None
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=10), timedelta(minutes=1))
        assert len(track) == 11
        assert -90 <= track[0].lat_deg <= 90
        assert -180 <= track[0].lon_deg <= 180

    def test_first_point_time_is_start(self):
        sat = _make_satellite()
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=10), timedelta(minutes=1))
        assert track[0].time == start

    def test_last_point_time(self):
        sat = _make_satellite()
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        track = compute_ground_track(sat, start, timedelta(minutes=90), timedelta(minutes=1))
        assert track[-1].time == start + timedelta(minutes=90)


class TestGroundTrackPurity:
    """Domain purity: ground_track.py must only import from stdlib and domain."""

    def test_no_external_imports(self):
        import constellation_generator.domain.ground_track as mod
        source_path = mod.__file__
        with open(source_path) as f:
            tree = ast.parse(f.read())

        allowed_top = {'math', 'dataclasses', 'datetime'}
        allowed_internal_prefix = 'constellation_generator.domain'

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split('.')[0]
                    assert top in allowed_top or alias.name.startswith(allowed_internal_prefix), \
                        f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    top = node.module.split('.')[0]
                    assert top in allowed_top or node.module.startswith(allowed_internal_prefix), \
                        f"Forbidden import from: {node.module}"
