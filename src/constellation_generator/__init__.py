"""
Constellation Generator

Generate Walker constellation satellite shells and fetch live orbital data
for orbit simulation tools. Includes J2-corrected propagation, topocentric
observation geometry, access window prediction, coverage analysis,
atmospheric drag modeling, orbit lifetime prediction, station-keeping
delta-V budgets, and conjunction/collision probability assessment.
"""

from constellation_generator.domain.orbital_mechanics import (
    OrbitalConstants,
    kepler_to_cartesian,
    sso_inclination_deg,
    j2_raan_rate,
    j2_arg_perigee_rate,
    j2_mean_motion_correction,
)
from constellation_generator.domain.constellation import (
    ShellConfig,
    Satellite,
    generate_walker_shell,
    generate_sso_band_configs,
)
from constellation_generator.domain.serialization import (
    format_position,
    format_velocity,
    build_satellite_entity,
)
from constellation_generator.domain.omm import (
    OrbitalElements,
    parse_omm_record,
)
from constellation_generator.domain.coordinate_frames import (
    gmst_rad,
    eci_to_ecef,
    ecef_to_geodetic,
    geodetic_to_ecef,
)
from constellation_generator.domain.ground_track import (
    GroundTrackPoint,
    compute_ground_track,
)
from constellation_generator.domain.propagation import (
    OrbitalState,
    derive_orbital_state,
    propagate_to,
    propagate_ecef_to,
)
from constellation_generator.domain.observation import (
    GroundStation,
    Observation,
    compute_observation,
)
from constellation_generator.domain.access_windows import (
    AccessWindow,
    compute_access_windows,
)
from constellation_generator.domain.coverage import (
    CoveragePoint,
    compute_coverage_snapshot,
)
from constellation_generator.domain.atmosphere import (
    DragConfig,
    atmospheric_density,
    drag_acceleration,
    semi_major_axis_decay_rate,
)
from constellation_generator.domain.lifetime import (
    DecayPoint,
    OrbitLifetimeResult,
    compute_orbit_lifetime,
    compute_altitude_at_time,
)
from constellation_generator.domain.station_keeping import (
    StationKeepingConfig,
    StationKeepingBudget,
    drag_compensation_dv_per_year,
    plane_maintenance_dv_per_year,
    tsiolkovsky_dv,
    propellant_mass_for_dv,
    compute_station_keeping_budget,
)
from constellation_generator.domain.conjunction import (
    PositionCovariance,
    ConjunctionEvent,
    screen_conjunctions,
    refine_tca,
    compute_b_plane,
    foster_max_collision_probability,
    collision_probability_2d,
    assess_conjunction,
)

__version__ = "1.5.0"

__all__ = [
    "OrbitalConstants",
    "kepler_to_cartesian",
    "sso_inclination_deg",
    "j2_raan_rate",
    "j2_arg_perigee_rate",
    "j2_mean_motion_correction",
    "ShellConfig",
    "Satellite",
    "generate_walker_shell",
    "generate_sso_band_configs",
    "format_position",
    "format_velocity",
    "build_satellite_entity",
    "OrbitalElements",
    "parse_omm_record",
    "gmst_rad",
    "eci_to_ecef",
    "ecef_to_geodetic",
    "geodetic_to_ecef",
    "GroundTrackPoint",
    "compute_ground_track",
    "OrbitalState",
    "derive_orbital_state",
    "propagate_to",
    "propagate_ecef_to",
    "GroundStation",
    "Observation",
    "compute_observation",
    "AccessWindow",
    "compute_access_windows",
    "CoveragePoint",
    "compute_coverage_snapshot",
    "DragConfig",
    "atmospheric_density",
    "drag_acceleration",
    "semi_major_axis_decay_rate",
    "DecayPoint",
    "OrbitLifetimeResult",
    "compute_orbit_lifetime",
    "compute_altitude_at_time",
    "StationKeepingConfig",
    "StationKeepingBudget",
    "drag_compensation_dv_per_year",
    "plane_maintenance_dv_per_year",
    "tsiolkovsky_dv",
    "propellant_mass_for_dv",
    "compute_station_keeping_budget",
    "PositionCovariance",
    "ConjunctionEvent",
    "screen_conjunctions",
    "refine_tca",
    "compute_b_plane",
    "foster_max_collision_probability",
    "collision_probability_2d",
    "assess_conjunction",
]
