# Constellation Generator

Generate Walker constellation satellite shells and fetch live orbital data for orbit simulation tools.

## Install

```bash
# Core (synthetic constellations only, no external deps)
pip install .

# With live CelesTrak support
pip install ".[live]"

# Development
pip install ".[dev]"
```

## Usage

### Synthetic constellations (Walker shells)

```bash
# Default: 3 Walker shells + SSO band → 7200 satellites
constellation-generator -i simulation_old.json -o simulation.json

# Custom base ID
constellation-generator -i sim_old.json -o sim.json --base-id 200
```

### Live data from CelesTrak

```bash
# Real GPS constellation (32 satellites)
constellation-generator -i sim.json -o out.json --live-group GPS-OPS

# All Starlink satellites (~6000+) with concurrent SGP4 propagation
constellation-generator -i sim.json -o out.json --live-group STARLINK --concurrent

# Search by name
constellation-generator -i sim.json -o out.json --live-name "ISS (ZARYA)"

# By NORAD catalog number
constellation-generator -i sim.json -o out.json --live-catnr 25544
```

#### Available CelesTrak groups

`STATIONS`, `GPS-OPS`, `STARLINK`, `ONEWEB`, `ACTIVE`, `WEATHER`,
`GALILEO`, `BEIDOU`, `IRIDIUM-NEXT`, `PLANET`, `SPIRE`, `GEO`,
`INTELSAT`, `SES`, `TELESAT`, `AMATEUR`, `SCIENCE`, `NOAA`, `GOES`

### Export formats

Export satellite positions as geodetic coordinates (lat/lon/alt) alongside
the simulation JSON:

```bash
# CSV export
constellation-generator -i sim.json -o out.json --export-csv satellites.csv

# GeoJSON export
constellation-generator -i sim.json -o out.json --export-geojson satellites.geojson

# Both at once
constellation-generator -i sim.json -o out.json --export-csv sats.csv --export-geojson sats.geojson
```

CSV columns: `name`, `lat_deg`, `lon_deg`, `alt_km`, `epoch`, `plane_index`,
`sat_index`, `raan_deg`, `true_anomaly_deg`.

GeoJSON produces a FeatureCollection with Point geometries. Coordinates
follow the GeoJSON spec: `[longitude, latitude, altitude_km]`.

### Programmatic

#### Walker shell generation

```python
from constellation_generator import ShellConfig, generate_walker_shell

shell = ShellConfig(
    altitude_km=550, inclination_deg=53,
    num_planes=10, sats_per_plane=20,
    phase_factor=1, raan_offset_deg=0,
    shell_name="Custom-Shell",
)
satellites = generate_walker_shell(shell)
```

#### Live data from CelesTrak

```python
from constellation_generator.adapters.celestrak import CelesTrakAdapter

celestrak = CelesTrakAdapter()
gps_sats = celestrak.fetch_satellites(group="GPS-OPS")
iss = celestrak.fetch_satellites(name="ISS (ZARYA)")
```

#### Concurrent mode

SGP4 propagation is the bottleneck when fetching large groups (not HTTP).
`ConcurrentCelesTrakAdapter` parallelizes propagation across threads
using `ThreadPoolExecutor`:

```python
from constellation_generator.adapters.concurrent_celestrak import ConcurrentCelesTrakAdapter

concurrent = ConcurrentCelesTrakAdapter(max_workers=16)
starlink = concurrent.fetch_satellites(group="STARLINK")
```

#### Coordinate frames

ECI to ECEF conversion applies a Z-axis rotation by the Greenwich Mean
Sidereal Time (GMST) angle. ECEF to Geodetic uses the iterative Bowring
method on the WGS84 ellipsoid:

```python
from datetime import datetime, timezone
from constellation_generator import gmst_rad, eci_to_ecef, ecef_to_geodetic

sat = gps_sats[0]
gmst = gmst_rad(sat.epoch)
pos_ecef, vel_ecef = eci_to_ecef(sat.position_eci, sat.velocity_eci, gmst)
lat, lon, alt = ecef_to_geodetic(pos_ecef)
print(f"{sat.name}: {lat:.4f}°N, {lon:.4f}°E, {alt/1000:.1f} km")
```

#### Ground track

Compute the sub-satellite ground track over time using Keplerian two-body
propagation. Appropriate for synthetic Walker shell satellites. For TLE
data, SGP4 propagation via the adapter layer gives more accurate results.

```python
from datetime import datetime, timedelta, timezone
from constellation_generator import compute_ground_track, generate_walker_shell, ShellConfig

shell = ShellConfig(
    altitude_km=500, inclination_deg=53,
    num_planes=2, sats_per_plane=3,
    phase_factor=1, raan_offset_deg=0,
    shell_name="Demo",
)
sats = generate_walker_shell(shell)

start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
track = compute_ground_track(sats[0], start, timedelta(minutes=90), timedelta(minutes=1))
print(f"Ground track: {len(track)} points")
print(f"Lat range: [{min(p.lat_deg for p in track):.1f}, {max(p.lat_deg for p in track):.1f}]")
```

#### Export formats (programmatic)

```python
from constellation_generator.adapters.csv_exporter import CsvSatelliteExporter
from constellation_generator.adapters.geojson_exporter import GeoJsonSatelliteExporter

# CSV
CsvSatelliteExporter().export(sats, "satellites.csv")

# GeoJSON
GeoJsonSatelliteExporter().export(sats, "satellites.geojson")
```

#### Mixing sources

Combine synthetic and live satellites, then serialise for simulation:

```python
from constellation_generator import build_satellite_entity

template = {"Name": "Sat", "Id": 0}
all_sats = satellites + gps_sats
entities = [
    build_satellite_entity(s, template, base_id=100 + i)
    for i, s in enumerate(all_sats)
]
```

## Default Shell Configuration

| Shell | Altitude | Inclination | Planes × Sats | Phase Factor |
|-------|----------|-------------|----------------|--------------|
| LEO-Shell500 | 500 km | 30° | 22 × 72 | 17 |
| LEO-Shell450 | 450 km | 30° | 22 × 72 | 17 |
| LEO-Shell400 | 400 km | 30° | 22 × 72 | 17 |
| SSO Band | 525–2200 km (50 km step) | SSO-computed | 1 × 72 | 0 |

## Architecture

```
src/constellation_generator/
├── domain/                    # Pure logic — only stdlib math/dataclasses/datetime
│   ├── orbital_mechanics.py   # Kepler → Cartesian, SSO inclination, WGS84 constants
│   ├── constellation.py       # Walker shells, SSO bands, ShellConfig, Satellite
│   ├── coordinate_frames.py   # ECI → ECEF → Geodetic (GMST, Bowring)
│   ├── ground_track.py        # Keplerian ground track computation
│   ├── serialization.py       # Simulation format (Y/Z swap, precision)
│   └── omm.py                 # CelesTrak OMM record → OrbitalElements
├── ports/                     # Abstract interfaces (ABC)
│   ├── __init__.py            # SimulationReader, SimulationWriter
│   ├── orbital_data.py        # OrbitalDataSource
│   └── export.py              # SatelliteExporter
├── adapters/                  # Infrastructure (JSON I/O, HTTP, SGP4, export)
│   ├── __init__.py            # JsonSimulationReader/Writer, exporters
│   ├── celestrak.py           # CelesTrakAdapter, SGP4Adapter
│   ├── concurrent_celestrak.py # ConcurrentCelesTrakAdapter (ThreadPoolExecutor)
│   ├── csv_exporter.py        # CsvSatelliteExporter
│   └── geojson_exporter.py    # GeoJsonSatelliteExporter
└── cli.py                     # CLI entry point (--concurrent, --export-csv, --export-geojson)
```

The domain layer has zero external dependencies. All I/O (file access,
HTTP, SGP4 propagation, export) is confined to the adapter layer behind
port interfaces.

## Tests

```bash
pytest                                    # all 101 tests
pytest tests/test_constellation.py        # 21 synthetic tests (offline)
pytest tests/test_coordinate_frames.py    # 21 coordinate frame tests (offline)
pytest tests/test_ground_track.py         # 16 ground track tests (offline)
pytest tests/test_export.py               # 18 export tests (offline)
pytest tests/test_concurrent_celestrak.py # 12 concurrent adapter tests (offline)
pytest tests/test_live_data.py            # 13 live data tests (network)
```

## Credits

Original code by [Scott Manley](https://www.youtube.com/@scottmanley). Refactored and extended by Jeroen.

## License

MIT
