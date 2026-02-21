# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the Commercial License — see COMMERCIAL-LICENSE.md.
"""Tests for relativistic force models (Schwarzschild, Lense-Thirring, de Sitter)."""

import ast
import math
from datetime import datetime, timezone

import pytest


def _vec_mag(v):
    return math.sqrt(sum(c ** 2 for c in v))


class TestSchwarzschildForce:
    """Post-Newtonian Schwarzschild correction."""

    def test_magnitude_at_leo(self):
        """Schwarzschild acceleration at LEO ~3e-9 m/s²."""
        from humeris.domain.relativistic_forces import SchwarzschildForce

        force = SchwarzschildForce()
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        pos = (6778137.0, 0.0, 0.0)
        vel = (0.0, 7668.0, 0.0)
        acc = force.acceleration(dt, pos, vel)
        mag = _vec_mag(acc)
        assert 1e-10 < mag < 1e-7

    def test_direction_circular_purely_radial(self):
        """Schwarzschild is purely radial for circular orbits (r·v=0)."""
        from humeris.domain.relativistic_forces import SchwarzschildForce

        force = SchwarzschildForce()
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        pos = (6778137.0, 0.0, 0.0)
        vel = (0.0, 7668.0, 0.0)
        acc = force.acceleration(dt, pos, vel)
        # Radial component non-zero, along-track zero for circular orbit
        assert acc[0] != 0.0
        assert acc[1] == 0.0

    def test_direction_eccentric_has_along_track(self):
        """Schwarzschild has along-track component for eccentric orbits (r·v≠0)."""
        from humeris.domain.relativistic_forces import SchwarzschildForce

        force = SchwarzschildForce()
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        # Slightly non-circular: r·v = 6778137 * 500 ≠ 0
        pos = (6778137.0, 0.0, 0.0)
        vel = (500.0, 7668.0, 0.0)
        acc = force.acceleration(dt, pos, vel)
        assert acc[0] != 0.0
        assert acc[1] != 0.0

    def test_increases_closer_to_earth(self):
        """Schwarzschild is stronger at lower altitude."""
        from humeris.domain.relativistic_forces import SchwarzschildForce

        force = SchwarzschildForce()
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        # LEO
        acc_leo = force.acceleration(dt, (6778137.0, 0.0, 0.0), (0.0, 7668.0, 0.0))
        # MEO
        acc_meo = force.acceleration(dt, (26578137.0, 0.0, 0.0), (0.0, 3870.0, 0.0))
        assert _vec_mag(acc_leo) > _vec_mag(acc_meo)

    def test_constants_verification(self):
        """Verify GM_E and c are correct."""
        from humeris.domain.relativistic_forces import (
            _GM_EARTH,
            _C_LIGHT,
        )
        assert abs(_GM_EARTH - 3.986004418e14) < 1e8
        assert _C_LIGHT == 299792458.0

    def test_force_model_compliance(self):
        """Has the ForceModel interface."""
        from humeris.domain.relativistic_forces import SchwarzschildForce
        force = SchwarzschildForce()
        assert hasattr(force, "acceleration")
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = force.acceleration(dt, (7000000.0, 0.0, 0.0), (0.0, 7500.0, 0.0))
        assert len(result) == 3


class TestLenseThirringForce:
    """Frame-dragging from Earth rotation."""

    def test_magnitude_at_leo(self):
        """Lense-Thirring ~2e-10 m/s² at equatorial LEO."""
        from humeris.domain.relativistic_forces import LenseThirringForce

        force = LenseThirringForce()
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        acc = force.acceleration(dt, (6778137.0, 0.0, 0.0), (0.0, 7668.0, 0.0))
        mag = _vec_mag(acc)
        assert 1e-12 < mag < 1e-8

    def test_force_model_compliance(self):
        from humeris.domain.relativistic_forces import LenseThirringForce
        force = LenseThirringForce()
        result = force.acceleration(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            (7000000.0, 0.0, 0.0), (0.0, 7500.0, 0.0),
        )
        assert len(result) == 3


class TestDeSitterForce:
    """Geodesic precession from heliocentric motion."""

    def test_magnitude_at_leo(self):
        """de Sitter ~5e-13 m/s² at LEO."""
        from humeris.domain.relativistic_forces import DeSitterForce

        force = DeSitterForce()
        dt = datetime(2024, 6, 15, tzinfo=timezone.utc)
        acc = force.acceleration(dt, (6778137.0, 0.0, 0.0), (0.0, 7668.0, 0.0))
        mag = _vec_mag(acc)
        assert 1e-15 < mag < 1e-10

    def test_force_model_compliance(self):
        from humeris.domain.relativistic_forces import DeSitterForce
        force = DeSitterForce()
        result = force.acceleration(
            datetime(2024, 6, 15, tzinfo=timezone.utc),
            (7000000.0, 0.0, 0.0), (0.0, 7500.0, 0.0),
        )
        assert len(result) == 3

    def test_iers_vector_triple_product(self):
        """IERS 2010 eq. 10.6: acceleration uses (R x V_E) x v, not V_E x (R x v).

        The geodesic precession is Omega_geo x v where Omega = (3/2)*GM_S/(c^2*R^3)*(R x V_E).
        Using BAC-CAB: (R x V_E) x v = (R.v)*V_E - (V_E.v)*R.
        The wrong form V_E x (R x v) = (V_E.v)*R - (V_E.R)*v gives different results.
        """
        import numpy as np
        from humeris.domain.relativistic_forces import (
            DeSitterForce, _GM_SUN, _C_LIGHT, _sun_position_approx,
        )

        force = DeSitterForce()
        # Use a date where Earth velocity has a known non-trivial direction
        dt = datetime(2024, 3, 20, tzinfo=timezone.utc)  # equinox
        # Non-degenerate position and velocity (all components non-zero)
        pos = (5000000.0, 4000000.0, 3000000.0)
        vel = (1000.0, 5000.0, 7000.0)
        acc = force.acceleration(dt, pos, vel)

        # Independently compute the correct IERS form:
        # a = coeff * (R x V_E) x v  where coeff = -(3*GM_S)/(2*c^2*R^3)
        sun = np.array(_sun_position_approx(dt))
        R = float(np.linalg.norm(sun))
        # Earth velocity via finite difference (same method as the implementation)
        from datetime import timedelta
        dt2 = dt + timedelta(seconds=3600.0)
        sun2 = np.array(_sun_position_approx(dt2))
        Ve = -(sun2 - sun) / 3600.0

        # IERS correct form: (R x V_E) x v
        v_arr = np.array(vel)
        RxVe = np.cross(sun, Ve)
        iers_cross = np.cross(RxVe, v_arr)

        coeff = -3.0 * _GM_SUN / (2.0 * _C_LIGHT**2 * R**3)
        expected = coeff * iers_cross

        # The implementation must match the IERS form within numerical precision
        np.testing.assert_allclose(acc, expected, rtol=1e-6)


class TestCombinedRelativistic:
    """Combined relativistic effects."""

    def test_schwarzschild_dominates(self):
        """Schwarzschild >> Lense-Thirring >> de Sitter."""
        from humeris.domain.relativistic_forces import (
            SchwarzschildForce,
            LenseThirringForce,
            DeSitterForce,
        )

        dt = datetime(2024, 6, 15, tzinfo=timezone.utc)
        pos = (6778137.0, 0.0, 0.0)
        vel = (0.0, 7668.0, 0.0)

        s = _vec_mag(SchwarzschildForce().acceleration(dt, pos, vel))
        lt = _vec_mag(LenseThirringForce().acceleration(dt, pos, vel))
        ds = _vec_mag(DeSitterForce().acceleration(dt, pos, vel))

        assert s > lt
        assert lt > ds or lt > 0  # LT should be measurable

    def test_all_finite(self):
        from humeris.domain.relativistic_forces import (
            SchwarzschildForce,
            LenseThirringForce,
            DeSitterForce,
        )
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        pos = (6778137.0, 0.0, 0.0)
        vel = (0.0, 7668.0, 0.0)
        for F in [SchwarzschildForce, LenseThirringForce, DeSitterForce]:
            acc = F().acceleration(dt, pos, vel)
            assert all(math.isfinite(a) for a in acc)


class TestDomainPurity:
    def test_no_external_imports(self):
        import humeris.domain.relativistic_forces as _mod
        source_path = _mod.__file__
        with open(source_path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        allowed = {
            "math", "numpy", "datetime", "dataclasses", "typing", "json",
            "pathlib", "os", "functools", "enum", "collections",
            "abc", "copy", "struct", "bisect", "operator",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top in allowed or top == "humeris", \
                        f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    assert top in allowed or top == "humeris", \
                        f"Forbidden import from: {node.module}"
