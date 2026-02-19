# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.
"""
Tests for KML satellite exporter.

Verifies KML structure, satellite positions, orbit paths, and return count.
"""
import math
import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import pytest

from humeris.domain.constellation import (
    ShellConfig,
    generate_walker_shell,
)
from humeris.domain.orbital_mechanics import OrbitalConstants
from humeris.ports.export import SatelliteExporter
from humeris.adapters.kml_exporter import KmlExporter


EPOCH = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)

SHELL = ShellConfig(
    altitude_km=550,
    inclination_deg=53,
    num_planes=2,
    sats_per_plane=3,
    phase_factor=1,
    raan_offset_deg=0,
    shell_name="Test",
)

KML_NS = "http://www.opengis.net/kml/2.2"


def _ns(tag: str) -> str:
    """Return namespaced tag."""
    return f"{{{KML_NS}}}{tag}"


@pytest.fixture
def satellites():
    return generate_walker_shell(SHELL)


@pytest.fixture
def kml_path():
    """Provide a temp file path, cleaned up after test."""
    fd, path = tempfile.mkstemp(suffix=".kml")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def kml_tree(satellites, kml_path):
    """Export satellites to KML and return parsed ElementTree."""
    exporter = KmlExporter(name="TestConstellation")
    exporter.export(satellites, kml_path, epoch=EPOCH)
    return ET.parse(kml_path)


class TestKmlStructure:
    """KML output has correct XML structure."""

    def test_port_compliance(self):
        assert issubclass(KmlExporter, SatelliteExporter)

    def test_has_export_method(self):
        exporter = KmlExporter()
        assert callable(getattr(exporter, "export", None))

    def test_valid_xml(self, kml_tree):
        root = kml_tree.getroot()
        assert root.tag == _ns("kml")

    def test_document_element(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        assert doc is not None

    def test_document_name(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        name = doc.find(_ns("name"))
        assert name is not None
        assert name.text == "TestConstellation"

    def test_style_element(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        style = doc.find(_ns("Style"))
        assert style is not None
        assert style.get("id") == "sat-style"

    def test_correct_number_of_folders(self, kml_tree, satellites):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        assert len(folders) == len(satellites)

    def test_satellite_names_in_folders(self, kml_tree, satellites):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        folder_names = [f.find(_ns("name")).text for f in folders]
        sat_names = [s.name for s in satellites]
        assert folder_names == sat_names

    def test_each_folder_has_two_placemarks(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            assert len(placemarks) == 2

    def test_default_document_name(self, satellites, kml_path):
        exporter = KmlExporter()
        exporter.export(satellites, kml_path, epoch=EPOCH)
        tree = ET.parse(kml_path)
        root = tree.getroot()
        doc = root.find(_ns("Document"))
        name = doc.find(_ns("name"))
        assert name.text == "Constellation"

    def test_empty_list_produces_valid_kml(self, kml_path):
        exporter = KmlExporter(name="Empty")
        count = exporter.export([], kml_path)
        tree = ET.parse(kml_path)
        root = tree.getroot()
        doc = root.find(_ns("Document"))
        assert doc is not None
        folders = doc.findall(_ns("Folder"))
        assert len(folders) == 0

    def test_style_url_on_placemarks(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            for pm in folder.findall(_ns("Placemark")):
                style_url = pm.find(_ns("styleUrl"))
                assert style_url is not None
                assert style_url.text == "#sat-style"


class TestSatellitePositions:
    """Position Placemarks contain correct geodetic coordinates."""

    def test_point_coordinates_have_three_components(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            point_pm = placemarks[0]
            point = point_pm.find(_ns("Point"))
            assert point is not None
            coords_text = point.find(_ns("coordinates")).text.strip()
            parts = coords_text.split(",")
            assert len(parts) == 3

    def test_coordinates_are_valid_floats(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            point_pm = placemarks[0]
            point = point_pm.find(_ns("Point"))
            coords_text = point.find(_ns("coordinates")).text.strip()
            parts = coords_text.split(",")
            for part in parts:
                float(part)  # must not raise

    def test_altitude_approximately_550km(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            point_pm = placemarks[0]
            point = point_pm.find(_ns("Point"))
            coords_text = point.find(_ns("coordinates")).text.strip()
            alt_m = float(coords_text.split(",")[2])
            # Spherical approximation: altitude should be close to 550 km
            assert abs(alt_m - 550_000) < 15_000

    def test_latitude_within_bounds(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            point_pm = placemarks[0]
            point = point_pm.find(_ns("Point"))
            coords_text = point.find(_ns("coordinates")).text.strip()
            lat = float(coords_text.split(",")[1])
            assert -90.0 <= lat <= 90.0

    def test_longitude_within_bounds(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            point_pm = placemarks[0]
            point = point_pm.find(_ns("Point"))
            coords_text = point.find(_ns("coordinates")).text.strip()
            lon = float(coords_text.split(",")[0])
            assert -180.0 <= lon <= 180.0

    def test_altitude_mode_is_absolute(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            point_pm = placemarks[0]
            point = point_pm.find(_ns("Point"))
            alt_mode = point.find(_ns("altitudeMode"))
            assert alt_mode is not None
            assert alt_mode.text == "absolute"


class TestOrbitPaths:
    """Orbit path Placemarks contain correct LineString coordinates."""

    def test_linestring_has_37_coordinate_tuples(self, kml_tree):
        """36 steps (0,10,...,350) + 1 closing point = 37 tuples."""
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            orbit_pm = placemarks[1]
            linestring = orbit_pm.find(_ns("LineString"))
            assert linestring is not None
            coords_text = linestring.find(_ns("coordinates")).text.strip()
            tuples = coords_text.split()
            assert len(tuples) == 37

    def test_orbit_coordinates_are_valid_floats(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            orbit_pm = placemarks[1]
            linestring = orbit_pm.find(_ns("LineString"))
            coords_text = linestring.find(_ns("coordinates")).text.strip()
            for coord_tuple in coords_text.split():
                parts = coord_tuple.split(",")
                assert len(parts) == 3
                for part in parts:
                    float(part)  # must not raise

    def test_orbit_path_closes(self, kml_tree):
        """First and last coordinate tuples should match."""
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            orbit_pm = placemarks[1]
            linestring = orbit_pm.find(_ns("LineString"))
            coords_text = linestring.find(_ns("coordinates")).text.strip()
            tuples = coords_text.split()
            assert tuples[0] == tuples[-1]

    def test_orbit_altitude_consistent(self, kml_tree):
        """All orbit path altitudes should be approximately equal (circular orbit)."""
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        folder = folders[0]
        placemarks = folder.findall(_ns("Placemark"))
        orbit_pm = placemarks[1]
        linestring = orbit_pm.find(_ns("LineString"))
        coords_text = linestring.find(_ns("coordinates")).text.strip()
        altitudes = []
        for coord_tuple in coords_text.split():
            alt = float(coord_tuple.split(",")[2])
            altitudes.append(alt)
        # All altitudes should be within 1 km of each other (circular orbit)
        alt_range = max(altitudes) - min(altitudes)
        assert alt_range < 1000.0

    def test_orbit_name_has_orbit_suffix(self, kml_tree, satellites):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder, sat in zip(folders, satellites):
            placemarks = folder.findall(_ns("Placemark"))
            orbit_pm = placemarks[1]
            name = orbit_pm.find(_ns("name"))
            assert name.text == f"{sat.name} orbit"

    def test_orbit_altitude_mode_is_absolute(self, kml_tree):
        root = kml_tree.getroot()
        doc = root.find(_ns("Document"))
        folders = doc.findall(_ns("Folder"))
        for folder in folders:
            placemarks = folder.findall(_ns("Placemark"))
            orbit_pm = placemarks[1]
            linestring = orbit_pm.find(_ns("LineString"))
            alt_mode = linestring.find(_ns("altitudeMode"))
            assert alt_mode is not None
            assert alt_mode.text == "absolute"


class TestReturnCount:
    """Export returns the number of satellites exported."""

    def test_return_count_matches(self, satellites, kml_path):
        exporter = KmlExporter(name="CountTest")
        count = exporter.export(satellites, kml_path, epoch=EPOCH)
        assert count == len(satellites)

    def test_return_count_zero_for_empty(self, kml_path):
        exporter = KmlExporter()
        count = exporter.export([], kml_path)
        assert count == 0


class TestEciToEcefRotation:
    """KML longitude must account for GMST rotation (ECI→ECEF)."""

    def test_longitude_offset_by_gmst(self, kml_path):
        """Satellite on ECI X-axis should NOT have lon≈0° in geodetic output.

        A satellite at ECI (r, 0, 0) has right ascension = 0°.
        Geographic longitude = 0° - GMST(epoch).
        The bug: current code outputs lon≈0° because it skips ECI→ECEF rotation.
        """
        from humeris.domain.constellation import Satellite
        from humeris.domain.coordinate_frames import gmst_rad

        r = OrbitalConstants.R_EARTH + 550_000.0
        # Satellite on ECI X-axis: RA=0
        sat = Satellite(
            name="X-Axis",
            plane_index=0,
            sat_index=0,
            position_eci=(r, 0.0, 0.0),
            velocity_eci=(0.0, 7600.0, 0.0),
            raan_deg=0.0,
            true_anomaly_deg=0.0,
        )
        # Use J2000 epoch where GMST ≈ 280.46° — gives ~79.5° offset
        epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        exporter = KmlExporter(name="GMST-Test", include_orbits=False)
        exporter.export([sat], kml_path, epoch=epoch)

        tree = ET.parse(kml_path)
        root = tree.getroot()
        doc = root.find(_ns("Document"))
        folder = doc.find(_ns("Folder"))
        pm = folder.find(_ns("Placemark"))
        point = pm.find(_ns("Point"))
        coords = point.find(_ns("coordinates")).text.strip()
        lon_deg = float(coords.split(",")[0])

        # Expected: lon = -GMST(epoch) mod 360, normalized to [-180, 180]
        gmst = math.degrees(gmst_rad(epoch))
        expected_lon = (-gmst) % 360.0
        if expected_lon > 180.0:
            expected_lon -= 360.0

        # GMST at J2000 ≈ 280.46° → expected lon ≈ 79.5°
        # Bug produces lon ≈ 0° (raw ECI). Tolerance: 1°.
        assert abs(lon_deg - expected_lon) < 1.0, (
            f"Longitude {lon_deg:.2f}° looks like ECI right ascension, "
            f"expected ECEF longitude ≈ {expected_lon:.2f}°"
        )

    def test_orbit_path_longitude_rotated(self, kml_path):
        """Orbit path coordinates must also include GMST rotation."""
        from humeris.domain.constellation import Satellite
        from humeris.domain.coordinate_frames import gmst_rad

        r = OrbitalConstants.R_EARTH + 550_000.0
        # Equatorial orbit — all points should have lat≈0, lon varies
        sat = Satellite(
            name="Equatorial",
            plane_index=0,
            sat_index=0,
            position_eci=(r, 0.0, 0.0),
            velocity_eci=(0.0, 7600.0, 0.0),
            raan_deg=0.0,
            true_anomaly_deg=0.0,
        )
        # Use J2000 epoch where GMST ≈ 280.46°
        epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        exporter = KmlExporter(name="GMST-Orbit", include_orbits=True)
        exporter.export([sat], kml_path, epoch=epoch)

        tree = ET.parse(kml_path)
        root = tree.getroot()
        doc = root.find(_ns("Document"))
        folder = doc.find(_ns("Folder"))
        placemarks = folder.findall(_ns("Placemark"))
        orbit_pm = placemarks[1]  # second placemark is the orbit
        linestring = orbit_pm.find(_ns("LineString"))
        coords_text = linestring.find(_ns("coordinates")).text.strip()

        # First point (angle=0) is at ECI X-axis → should have GMST offset
        first_tuple = coords_text.split()[0]
        first_lon = float(first_tuple.split(",")[0])

        gmst = math.degrees(gmst_rad(epoch))
        expected_lon = (-gmst) % 360.0
        if expected_lon > 180.0:
            expected_lon -= 360.0

        assert abs(first_lon - expected_lon) < 1.0, (
            f"Orbit path lon {first_lon:.2f}° not rotated by GMST, "
            f"expected ≈ {expected_lon:.2f}°"
        )

    def test_zero_position_vector_returns_gracefully(self):
        """Zero position vector should not cause ZeroDivisionError."""
        from humeris.adapters.kml_exporter import _eci_to_geodetic_spherical

        lat, lon, alt = _eci_to_geodetic_spherical(0.0, 0.0, 0.0)
        assert lat == 0.0
        assert lon == 0.0
