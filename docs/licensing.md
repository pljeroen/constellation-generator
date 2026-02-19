# Licensing

## Dual-license model

This project uses a dual-license model: MIT open core with commercial
extended modules. The two licenses are distributed as separate pip packages
sharing the `humeris` namespace via PEP 420 implicit namespace packages.

### Package structure

| Package | License | Install |
|---------|---------|---------|
| `humeris-core` | MIT | `pip install humeris-core` |
| `humeris-pro` | Commercial | `pip install humeris-pro` |

`humeris-pro` depends on `humeris-core`. Installing pro automatically
installs core. Core works standalone for constellation generation,
Keplerian propagation, coverage analysis, and export.

### MIT (core) — `packages/core/`

The foundation is MIT-licensed. Copyright "Jeroen Visser".

Covers 11 domain modules, 13 adapters, 3 ports, CLI, and their tests:

**Domain**: `orbital_mechanics`, `constellation`, `coordinate_frames`,
`propagation`, `coverage`, `access_windows`, `ground_track`, `observation`,
`omm`, `serialization`, `ccsds_contracts`

**Adapters**: `json_io`, `enrichment`, `celestrak`, `concurrent_celestrak`,
`csv_exporter`, `geojson_exporter`, `kml_exporter`, `blender_exporter`,
`stellarium_exporter`, `celestia_exporter`, `spaceengine_exporter`,
`ksp_exporter`, `ubox_exporter`

**Ports**: `SimulationReader`, `SimulationWriter`, `OrbitalDataSource`,
`SatelliteExporter`

Use freely for any purpose. See [LICENSE](../LICENSE).

### Commercial (extended modules) — `packages/pro/`

71 domain modules and 4 adapters. Copyright "Jeroen Visser".

**Free for**: personal use, educational use, academic research.

**Requires paid license for**: commercial use by companies. Starting at
EUR 2,000.

See [COMMERCIAL-LICENSE.md](../COMMERCIAL-LICENSE.md) for full terms.

## What's commercial

| Category | Count | Examples |
|----------|-------|---------|
| Propagation | 4 | numerical propagation (RK4), adaptive integration (Dormand-Prince), Koopman propagation (DMD), functorial force composition |
| Analysis | 8 | revisit, conjunction, eclipse, sensor, pass analysis, constellation metrics, DOP, thermal |
| Design | 7 | orbit design, trade studies, multi-objective, optimization, sensitivity, orbit properties, Gramian reconfiguration |
| Environment | 9 | atmosphere, NRLMSISE-00, lifetime, station-keeping, deorbit, radiation, torques, third-body, solar |
| Topology | 5 | ISL, link budget, graph analysis, spectral topology, Hodge-CUSUM |
| Composition | 16 | mission analysis, conjunction management, communication, coverage optimization, environment, maintenance, economics, operability, cascade, competing risks, conjunction profiles, compliance profiles, replay bundle, mission digital twin, API contracts, trade cost energy |
| Math | 4 | linalg, information theory, statistical analysis, relative motion |
| Research | 4 | decay analysis, temporal correlation, operational prediction, SP3 parser |
| Early warning | 5 | orbit determination (EKF), maneuver detection, hazard reporting, Kessler heatmap, control analysis |
| Fidelity | 7 | time systems, precession/nutation, earth orientation, planetary ephemeris, gravity field, relativistic forces, tidal forces, albedo/SRP |
| Maneuvers | 2 | maneuvers (Hohmann, bi-elliptic, plane change, phasing), deorbit |
| **Total domain** | **71** | |
| Adapters | 4 | czml_exporter, czml_visualization, cesium_viewer, viewer_server |

## Identifying license type

Check the copyright line at the top of any file:

```python
# MIT:
# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.

# Commercial:
# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
```

## What you get with the commercial modules

The 71 commercial modules extend the MIT core into a broader analysis
toolkit. A few things worth knowing:

**Analytical and numerical in one place.** The MIT core gives you Keplerian
and J2 secular propagation. The commercial modules add RK4 numerical
integration with pluggable forces — drag, SRP, third-body, J2/J3,
relativistic, tidal, albedo. You can switch between fast analytical
estimates and higher-fidelity numerical runs without changing your workflow.

**Things compose.** Conjunction screening flows into collision probability,
which flows into avoidance maneuver planning. Coverage analysis combines
with eclipse prediction, link budgets, and lifetime estimates into a
single mission assessment. These compositions encode domain knowledge that
would take time to build from scratch.

**Pure Python, inspectable.** No C extensions, no compiled binaries, no
platform-specific builds. Every computation — the RK4 integrator, the
Jacobi eigensolver, the NRLMSISE-00 atmosphere model — is plain Python
you can step through in your debugger.

**What it is not.** This library is not certified for operational flight
decisions, regulatory compliance determination, or safety-of-flight
assessment. It provides engineering analysis tools for research, education,
and design exploration. Operational use requires independent validation
against authoritative sources.

## Contact

For commercial licensing: see COMMERCIAL-LICENSE.md for contact details.
