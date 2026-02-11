"""
Constellation Generator

Generate Walker constellation satellite shells and fetch live orbital data
for orbit simulation tools.
"""

from constellation_generator.domain.orbital_mechanics import (
    OrbitalConstants,
    kepler_to_cartesian,
    sso_inclination_deg,
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
)

__version__ = "1.2.0"

__all__ = [
    "OrbitalConstants",
    "kepler_to_cartesian",
    "sso_inclination_deg",
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
]
