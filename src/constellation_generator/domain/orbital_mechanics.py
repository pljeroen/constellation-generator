"""
Orbital mechanics functions.

Pure mathematical conversions for orbital element transformations.
No external dependencies — only stdlib math.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class OrbitalConstants:
    """Standard orbital constants (IAU values)."""
    MU_EARTH: float = 3.986004418e14   # m³/s² — gravitational parameter
    R_EARTH: float = 6_371_000          # m — mean radius
    J2_EARTH: float = 1.08263e-3        # J2 perturbation coefficient
    EARTH_OMEGA: float = 1.99e-7        # rad/s — rotation rate for SSO


# Module-level singleton
OrbitalConstants = OrbitalConstants()


def kepler_to_cartesian(
    a: float,
    e: float,
    i_rad: float,
    omega_big_rad: float,
    omega_small_rad: float,
    nu_rad: float,
) -> tuple[list[float], list[float]]:
    """
    Convert Keplerian orbital elements to ECI Cartesian position/velocity.

    Args:
        a: Semi-major axis (m)
        e: Eccentricity (0 for circular)
        i_rad: Inclination (radians)
        omega_big_rad: RAAN / longitude of ascending node (radians)
        omega_small_rad: Argument of perigee (radians)
        nu_rad: True anomaly (radians)

    Returns:
        (position_eci [x,y,z] in m, velocity_eci [vx,vy,vz] in m/s)
    """
    mu = OrbitalConstants.MU_EARTH

    r = a * (1 - e**2) / (1 + e * math.cos(nu_rad))

    p_factor = math.sqrt(mu / (a * (1 - e**2)))
    pos_pqw = [r * math.cos(nu_rad), r * math.sin(nu_rad), 0.0]
    vel_pqw = [
        -p_factor * math.sin(nu_rad),
        p_factor * (e + math.cos(nu_rad)),
        0.0,
    ]

    cO = math.cos(omega_big_rad)
    sO = math.sin(omega_big_rad)
    co = math.cos(omega_small_rad)
    so = math.sin(omega_small_rad)
    ci = math.cos(i_rad)
    si = math.sin(i_rad)

    rotation = [
        [cO * co - sO * so * ci, -cO * so - sO * co * ci, sO * si],
        [sO * co + cO * so * ci, -sO * so + cO * co * ci, -cO * si],
        [so * si, co * si, ci],
    ]

    pos_eci = [
        sum(rotation[j][k] * pos_pqw[k] for k in range(3)) for j in range(3)
    ]
    vel_eci = [
        sum(rotation[j][k] * vel_pqw[k] for k in range(3)) for j in range(3)
    ]

    return pos_eci, vel_eci


def sso_inclination_deg(altitude_km: float) -> float:
    """
    Calculate Sun-synchronous orbit inclination for a given altitude.

    Uses the J2 perturbation-based SSO condition:
        cos(i) = -(2 * ω_earth / (3 * J2 * R²)) * ((alt + R)^3.5 / √μ)

    Args:
        altitude_km: Orbital altitude above Earth surface (km)

    Returns:
        Inclination in degrees (retrograde, > 90°)
    """
    c = OrbitalConstants
    r = altitude_km * 1000 + c.R_EARTH
    cos_i = -(2 * c.EARTH_OMEGA / (3 * c.J2_EARTH * c.R_EARTH**2)) * (
        r**3.5 / math.sqrt(c.MU_EARTH)
    )
    return math.degrees(math.acos(cos_i))
