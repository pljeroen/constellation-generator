"""
Ground track computation for circular orbits.

Propagates a satellite's position over time using Keplerian two-body
mechanics and converts to geodetic coordinates (lat/lon/alt) via the
existing ECI -> ECEF -> Geodetic pipeline.

Limitation: This uses pure Keplerian propagation (no drag, no J2, no
perturbations). For satellites from TLE data, SGP4 propagation via
the adapter layer will give more accurate results. This function is
appropriate for synthetic Walker shell satellites and short-duration
ground track visualization.

No external dependencies — only stdlib math/dataclasses/datetime.
"""
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from constellation_generator.domain.orbital_mechanics import (
    OrbitalConstants,
    kepler_to_cartesian,
)
from constellation_generator.domain.coordinate_frames import (
    gmst_rad,
    eci_to_ecef,
    ecef_to_geodetic,
)


@dataclass(frozen=True)
class GroundTrackPoint:
    """A single point on a satellite's ground track."""
    time: datetime
    lat_deg: float
    lon_deg: float
    alt_km: float


def compute_ground_track(
    satellite,
    start: datetime,
    duration: timedelta,
    step: timedelta,
) -> list[GroundTrackPoint]:
    """
    Compute the ground track of a satellite over a time interval.

    Uses Keplerian two-body propagation for circular orbits:
    - Derives mean motion from position magnitude (a = |r|)
    - Derives inclination from angular momentum vector
    - Advances true anomaly linearly (circular orbit assumption)
    - Converts each position through ECI -> ECEF -> Geodetic pipeline

    For satellites with epoch=None (synthetic), the start time is used
    as the reference epoch. For satellites with an epoch, the true
    anomaly offset from epoch to start is computed.

    Args:
        satellite: Satellite domain object with position_eci, velocity_eci,
            raan_deg, true_anomaly_deg, and optional epoch.
        start: UTC datetime for the first ground track point.
        duration: Total time span to compute.
        step: Time between consecutive points.

    Returns:
        List of GroundTrackPoint objects from start to start+duration.

    Raises:
        ValueError: If step is zero or negative.
    """
    step_seconds = step.total_seconds()
    if step_seconds <= 0:
        raise ValueError(f"Step must be positive, got {step}")

    duration_seconds = duration.total_seconds()

    # Derive orbital elements from satellite state
    px, py, pz = satellite.position_eci
    vx, vy, vz = satellite.velocity_eci

    r_mag = math.sqrt(px**2 + py**2 + pz**2)
    a = r_mag  # circular orbit: a = r

    mu = OrbitalConstants.MU_EARTH
    n = math.sqrt(mu / a**3)  # mean motion (rad/s)

    # Inclination from angular momentum vector h = r x v
    hx = py * vz - pz * vy
    hy = pz * vx - px * vz
    hz = px * vy - py * vx
    h_mag = math.sqrt(hx**2 + hy**2 + hz**2)
    inc_rad = math.acos(hz / h_mag) if h_mag > 0 else 0.0

    raan_rad = math.radians(satellite.raan_deg)
    omega_small_rad = 0.0  # argument of perigee = 0 for circular
    e = 0.0

    nu_0_rad = math.radians(satellite.true_anomaly_deg)

    # Reference epoch: satellite.epoch if available, else start
    if satellite.epoch is not None:
        epoch_offset = (start - satellite.epoch).total_seconds()
        nu_at_start = nu_0_rad + n * epoch_offset
    else:
        nu_at_start = nu_0_rad

    points: list[GroundTrackPoint] = []
    elapsed = 0.0

    while elapsed <= duration_seconds + 1e-9:  # small epsilon for float comparison
        current_time = start + timedelta(seconds=elapsed)
        nu_rad = nu_at_start + n * elapsed

        pos_eci, _ = kepler_to_cartesian(
            a=a, e=e, i_rad=inc_rad,
            omega_big_rad=raan_rad,
            omega_small_rad=omega_small_rad,
            nu_rad=nu_rad,
        )

        gmst_angle = gmst_rad(current_time)
        pos_ecef, _ = eci_to_ecef(
            (pos_eci[0], pos_eci[1], pos_eci[2]),
            (0.0, 0.0, 0.0),
            gmst_angle,
        )

        lat_deg, lon_deg, alt_m = ecef_to_geodetic(pos_ecef)

        points.append(GroundTrackPoint(
            time=current_time,
            lat_deg=lat_deg,
            lon_deg=lon_deg,
            alt_km=alt_m / 1000.0,
        ))

        elapsed += step_seconds

    return points
