# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the MIT License — see LICENSE.
"""
Command-line interface for satellite constellation analysis.

Usage:
    humeris serve                                       # 3D viewer
    humeris generate -i sim.json -o out.json            # synthetic shells
    humeris generate -i sim.json -o out.json --live-group GPS-OPS
    humeris generate -i sim.json -o out.json --export-csv sats.csv
    humeris import opm satellite.opm                    # CCSDS OPM
    humeris import oem satellite.oem                    # CCSDS OEM
    humeris sweep --param alt:400:600:50 --metric coverage -o sweep.csv
    humeris --version
"""
import argparse
import math
import sys
import warnings

from humeris.domain.constellation import (
    ShellConfig,
    Satellite,
    generate_walker_shell,
    generate_sso_band_configs,
)
from humeris.domain.serialization import build_satellite_entity
from humeris.adapters.json_io import JsonSimulationReader, JsonSimulationWriter
from humeris.adapters.csv_exporter import CsvSatelliteExporter
from humeris.adapters.geojson_exporter import GeoJsonSatelliteExporter
from humeris.adapters.celestia_exporter import CelestiaExporter
from humeris.adapters.kml_exporter import KmlExporter
from humeris.adapters.stellarium_exporter import StellariumExporter
from humeris.adapters.blender_exporter import BlenderExporter
from humeris.adapters.spaceengine_exporter import SpaceEngineExporter
from humeris.adapters.ksp_exporter import KspExporter
from humeris.adapters.ubox_exporter import UboxExporter
from humeris.domain.orbital_mechanics import OrbitalConstants
from humeris.domain.propagation import derive_orbital_state


def get_default_shells() -> list[ShellConfig]:
    """
    Default constellation: 3 Walker shells + SSO band.

    - 3 Walker shells at 500/450/400 km, 30° inc, 22 planes × 72 sats
    - SSO band from 525–2200 km in 50 km steps, 1 plane × 72 sats
    """
    walker_shells = [
        ShellConfig(
            altitude_km=500, inclination_deg=30,
            num_planes=22, sats_per_plane=72,
            phase_factor=17, raan_offset_deg=0.0,
            shell_name='LEO-Shell500',
        ),
        ShellConfig(
            altitude_km=450, inclination_deg=30,
            num_planes=22, sats_per_plane=72,
            phase_factor=17, raan_offset_deg=5.45,
            shell_name='LEO-Shell450',
        ),
        ShellConfig(
            altitude_km=400, inclination_deg=30,
            num_planes=22, sats_per_plane=72,
            phase_factor=17, raan_offset_deg=10.9,
            shell_name='LEO-Shell400',
        ),
    ]

    sso_shells = generate_sso_band_configs(
        start_alt_km=525, end_alt_km=2200,
        step_km=50, sats_per_plane=72,
    )

    return walker_shells + sso_shells


def run(
    input_path: str,
    output_path: str,
    shells: list[ShellConfig] | None = None,
    base_id: int = 100,
    template_name: str = "Satellite",
) -> tuple[int, list[Satellite]]:
    """
    Generate synthetic constellation and write to simulation JSON.

    Returns:
        (count, satellites) — number generated and list of Satellite objects.
    """
    reader = JsonSimulationReader()
    writer = JsonSimulationWriter()

    sim = reader.read_simulation(input_path)
    template = reader.extract_template_entity(sim, template_name)
    earth = reader.extract_earth_entity(sim)

    earth['Position'] = "0;0;0"
    earth['Velocity'] = "0;0;0"

    if shells is None:
        shells = get_default_shells()

    all_satellites: list[Satellite] = []
    entities = sim.get('Entities', [])
    next_id = base_id

    for shell in shells:
        satellites = generate_walker_shell(shell)
        all_satellites.extend(satellites)
        for sat in satellites:
            entity = build_satellite_entity(sat, template, base_id=next_id)
            entities.append(entity)
            next_id += 1

    writer.write_simulation(sim, output_path)
    return len(all_satellites), all_satellites


def run_live(
    input_path: str,
    output_path: str,
    group: str | None = None,
    name: str | None = None,
    catnr: int | None = None,
    base_id: int = 100,
    template_name: str = "Satellite",
    concurrent: bool = False,
) -> tuple[int, list[Satellite]]:
    """
    Fetch live satellite data from CelesTrak and write to simulation JSON.

    Requires: pip install humeris[live]

    Returns:
        (count, satellites) — number generated and list of Satellite objects.
    """
    try:
        from humeris.adapters.celestrak import CelesTrakAdapter
        from humeris.adapters.concurrent_celestrak import ConcurrentCelesTrakAdapter
    except ImportError:
        print(
            "Live data requires the sgp4 package.\n"
            "Install with: pip install humeris[live]",
            file=sys.stderr,
        )
        sys.exit(1)

    reader = JsonSimulationReader()
    writer = JsonSimulationWriter()

    sim = reader.read_simulation(input_path)
    template = reader.extract_template_entity(sim, template_name)
    earth = reader.extract_earth_entity(sim)
    earth['Position'] = "0;0;0"
    earth['Velocity'] = "0;0;0"

    celestrak = ConcurrentCelesTrakAdapter() if concurrent else CelesTrakAdapter()
    mode_label = "concurrent" if concurrent else "sequential"
    print(f"Fetching live data from CelesTrak ({mode_label})...")
    satellites = celestrak.fetch_satellites(group=group, name=name, catnr=catnr)
    print(f"Received {len(satellites)} satellites")

    entities = sim.get('Entities', [])
    next_id = base_id
    for sat in satellites:
        entity = build_satellite_entity(sat, template, base_id=next_id)
        entities.append(entity)
        next_id += 1

    writer.write_simulation(sim, output_path)
    return len(satellites), satellites


def _run_serve(
    port: int = 8765,
    load_session_path: str | None = None,
    headless: bool = False,
    export_czml_path: str | None = None,
) -> None:
    """Start the interactive Cesium viewer server with default shells."""
    if headless and not load_session_path:
        print(
            "Error: --headless requires --load-session <file>",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from humeris.adapters.viewer_server import (
            LayerManager,
            create_viewer_server,
        )
    except ImportError:
        print(
            "Interactive viewer requires humeris-pro.\n"
            "Install with: pip install humeris-pro",
            file=sys.stderr,
        )
        sys.exit(1)

    import json as _json
    import webbrowser
    from datetime import datetime, timedelta, timezone

    # If loading a session, validate the file first
    session_data = None
    if load_session_path:
        import os
        if not os.path.exists(load_session_path):
            print(
                f"Error: Session file not found: {load_session_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            with open(load_session_path, encoding="utf-8") as f:
                session_data = _json.load(f)
        except (_json.JSONDecodeError, UnicodeDecodeError) as e:
            print(
                f"Error: Invalid session file: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    epoch = datetime.now(tz=timezone.utc)
    mgr = LayerManager(epoch=epoch)

    if session_data is not None:
        # Load from session file instead of default shells
        print(f"Loading session from {load_session_path}...")
        restored = mgr.load_session(session_data)
        print(f"  Restored {restored} layers")
    else:
        # Pre-load default Walker shells
        walker_shells = [s for s in get_default_shells() if s.altitude_km in (500, 450, 400)]
        for shell in walker_shells:
            print(f"  Generating {shell.shell_name}...")
            sats = generate_walker_shell(shell)
            states = [derive_orbital_state(s, epoch, include_j2=True) for s in sats]
            mgr.add_layer(
                name=f"Constellation:{shell.shell_name}",
                category="Constellation",
                layer_type="walker",
                states=states,
                params={
                    "altitude_km": shell.altitude_km,
                    "inclination_deg": shell.inclination_deg,
                    "num_planes": shell.num_planes,
                    "sats_per_plane": shell.sats_per_plane,
                    "phase_factor": shell.phase_factor,
                    "raan_offset_deg": shell.raan_offset_deg,
                    "shell_name": shell.shell_name,
                },
            )
            print(f"    {len(sats)} satellites")

        # Try to fetch ISS from CelesTrak
        try:
            from humeris.adapters.celestrak import CelesTrakAdapter
            print("  Fetching ISS from CelesTrak...")
            celestrak = CelesTrakAdapter()
            iss_sats = celestrak.fetch_satellites(name="ISS (ZARYA)", epoch=epoch)
            if iss_sats:
                iss_states = [derive_orbital_state(s, epoch, include_j2=True) for s in iss_sats]
                mgr.add_layer(
                    name="Constellation:ISS",
                    category="Constellation",
                    layer_type="celestrak",
                    states=iss_states,
                    params={"name": "ISS (ZARYA)"},
                    mode="animated",
                )
                print(f"    ISS: {len(iss_sats)} object(s)")
        except Exception as e:
            print(f"    ISS fetch skipped: {e}")

    # Headless mode: export and exit without starting server
    if headless:
        if export_czml_path:
            exported = mgr.export_czml_layers(export_czml_path)
            print(f"Exported {exported} CZML files to {export_czml_path}")
        else:
            print(f"Session loaded: {len(mgr.layers)} layers")
            print("No export requested. Use --export-czml <dir> to export.")
        return

    try:
        server = create_viewer_server(mgr, port=port)
    except OSError as e:
        if "Address already in use" in str(e) or e.errno == 98:
            print(
                f"Error: Port {port} is already in use.\n"
                f"Try a different port: humeris serve --port {port + 1}",
                file=sys.stderr,
            )
            sys.exit(1)
        raise

    url = f"http://localhost:{port}"
    print(f"\nInteractive viewer at {url}")
    print("Press Ctrl+C to stop.\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.shutdown()


def _run_sweep(args) -> None:
    """Execute CLI parameter sweep."""
    import csv
    import json
    from datetime import datetime, timezone
    from itertools import product as iterproduct

    try:
        from humeris.adapters.viewer_server import LayerManager
    except ImportError:
        print(
            "Sweep requires humeris-pro.\n"
            "Install with: pip install humeris-pro",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse --param flags: "name:min:max:step"
    sweep_specs: list[tuple[str, float, float, float]] = []
    for p in args.param:
        parts = p.split(":")
        if len(parts) != 4:
            print(
                f"Error: --param must be name:min:max:step, got: {p}",
                file=sys.stderr,
            )
            sys.exit(1)
        name = parts[0]
        try:
            lo, hi, step = float(parts[1]), float(parts[2]), float(parts[3])
        except ValueError:
            print(f"Error: non-numeric values in --param: {p}", file=sys.stderr)
            sys.exit(1)
        if step <= 0:
            print(f"Error: step must be > 0 in --param: {p}", file=sys.stderr)
            sys.exit(1)
        sweep_specs.append((name, lo, hi, step))

    # Generate value ranges for each parameter
    param_ranges: list[list[float]] = []
    param_names: list[str] = []
    for name, lo, hi, step in sweep_specs:
        vals: list[float] = []
        v = lo
        while v <= hi + 1e-9:
            vals.append(round(v, 6))
            v += step
        param_ranges.append(vals)
        param_names.append(name)

    # Base constellation params (defaults)
    base_params: dict[str, float] = {
        "altitude_km": 550,
        "inclination_deg": 53,
        "num_planes": 6,
        "sats_per_plane": 10,
        "phase_factor": 0,
        "raan_offset_deg": 0,
    }

    epoch = datetime.now(tz=timezone.utc)
    mgr = LayerManager(epoch=epoch)

    # Cartesian product of all parameter ranges
    combos = list(iterproduct(*param_ranges))
    total = len(combos)

    results: list[dict] = []
    for idx, combo in enumerate(combos):
        params = dict(base_params)
        for name, val in zip(param_names, combo):
            params[name] = val

        print(
            f"  [{idx + 1}/{total}] {', '.join(f'{n}={v}' for n, v in zip(param_names, combo))}",
            file=sys.stderr,
        )

        sweep_result = mgr.run_sweep(
            base_params=params,
            sweep_param=param_names[0],  # sweep on first param at its value
            sweep_min=combo[0],
            sweep_max=combo[0],
            sweep_step=1.0,  # single value
            metric_type=args.metric,
        )
        if sweep_result:
            results.append(sweep_result[0])

    # Write output
    fmt = getattr(args, "format", "csv")
    output_path = args.output

    if fmt == "json":
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
    else:
        # CSV
        if not results:
            print("No results to write.", file=sys.stderr)
            sys.exit(1)
        # Collect all metric keys
        metric_keys: list[str] = []
        for r in results:
            for k in r.get("metrics", {}):
                if k not in metric_keys:
                    metric_keys.append(k)
        fieldnames = list(param_names) + metric_keys
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                row = {}
                for pn in param_names:
                    row[pn] = r.get("params", {}).get(pn, "")
                for mk in metric_keys:
                    row[mk] = r.get("metrics", {}).get(mk, "")
                writer.writerow(row)

    print(f"Wrote {len(results)} results to {output_path}", file=sys.stderr)


def _run_import_opm(file_path: str) -> None:
    """Import CCSDS OPM file and display satellite info."""
    from humeris.domain.ccsds_parser import parse_opm
    from humeris.domain.ccsds_contracts import CcsdsValidationError
    try:
        result = parse_opm(file_path)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except CcsdsValidationError as e:
        print(f"Error: Invalid OPM file: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Object: {result.object_name} ({result.object_id})")
    print(f"Frame: {result.ref_frame}, Center: {result.center_name}")
    for i, state in enumerate(result.states):
        alt_km = (state.semi_major_axis_m - OrbitalConstants.R_EARTH) / 1000.0
        inc_deg = math.degrees(state.inclination_rad)
        print(f"  State {i}: alt={alt_km:.1f} km, inc={inc_deg:.1f} deg, epoch={state.reference_epoch}")


def _run_import_oem(file_path: str) -> None:
    """Import CCSDS OEM file and display satellite info."""
    from humeris.domain.ccsds_parser import parse_oem
    from humeris.domain.ccsds_contracts import CcsdsValidationError
    try:
        result = parse_oem(file_path)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except CcsdsValidationError as e:
        print(f"Error: Invalid OEM file: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Object: {result.object_name} ({result.object_id})")
    print(f"Frame: {result.ref_frame}, Center: {result.center_name}")
    print(f"Ephemeris points: {len(result.states)}")
    if result.states:
        first = result.states[0]
        last = result.states[-1]
        print(f"  First epoch: {first.reference_epoch}")
        print(f"  Last epoch:  {last.reference_epoch}")


def _run_generate(args) -> None:
    """Generate constellation and optionally export."""
    if not args.input:
        print("Error: generate requires --input/-i", file=sys.stderr)
        sys.exit(2)
    if not args.output:
        print("Error: generate requires --output/-o", file=sys.stderr)
        sys.exit(2)

    try:
        live_mode = args.live_group or args.live_name or args.live_catnr is not None
        if live_mode:
            count, satellites = run_live(
                input_path=args.input,
                output_path=args.output,
                group=args.live_group,
                name=args.live_name,
                catnr=args.live_catnr,
                base_id=args.base_id,
                template_name=args.template_name,
                concurrent=args.concurrent,
            )
        else:
            count, satellites = run(
                input_path=args.input,
                output_path=args.output,
                base_id=args.base_id,
                template_name=args.template_name,
            )
        print(f"Generated {args.output} with {count} satellites.")

        if args.export_csv:
            csv_count = CsvSatelliteExporter().export(satellites, args.export_csv)
            print(f"Exported {csv_count} satellites to {args.export_csv}")

        if args.export_geojson:
            geojson_count = GeoJsonSatelliteExporter().export(satellites, args.export_geojson)
            print(f"Exported {geojson_count} satellites to {args.export_geojson}")

        if args.export_html:
            try:
                from humeris.adapters.czml_exporter import constellation_packets
                from humeris.adapters.cesium_viewer import write_cesium_html
            except ImportError:
                print(
                    "HTML export requires humeris-pro.\n"
                    "Install with: pip install humeris-pro",
                    file=sys.stderr,
                )
                sys.exit(1)
            from datetime import datetime, timedelta, timezone
            epoch = datetime.now(tz=timezone.utc)
            states = [derive_orbital_state(s, epoch) for s in satellites]
            pkts = constellation_packets(
                states, epoch, timedelta(hours=2), timedelta(seconds=60),
            )
            write_cesium_html(pkts, args.export_html, cesium_token=args.cesium_token)
            print(f"Exported interactive viewer to {args.export_html}")

        if args.export_celestia:
            n = CelestiaExporter().export(satellites, args.export_celestia)
            print(f"Exported {n} satellites to {args.export_celestia} (Celestia .ssc)")

        if args.export_kml:
            kml_exporter = KmlExporter(
                include_orbits=not args.no_orbits,
                include_planes=args.kml_planes,
                include_isl=args.kml_isl,
            )
            n = kml_exporter.export(satellites, args.export_kml)
            print(f"Exported {n} satellites to {args.export_kml} (KML)")

        if args.export_tle:
            n = StellariumExporter().export(satellites, args.export_tle)
            print(f"Exported {n} satellites to {args.export_tle} (TLE)")

        if args.export_blender:
            blender_exporter = BlenderExporter(
                include_orbits=not args.no_orbits,
                color_by_plane=args.blender_colors,
            )
            n = blender_exporter.export(satellites, args.export_blender)
            print(f"Exported {n} satellites to {args.export_blender} (Blender .py)")

        if args.export_spaceengine:
            n = SpaceEngineExporter().export(satellites, args.export_spaceengine)
            print(f"Exported {n} satellites to {args.export_spaceengine} (SpaceEngine .sc)")

        if args.export_ksp:
            n = KspExporter().export(satellites, args.export_ksp)
            print(f"Exported {n} satellites to {args.export_ksp} (KSP .sfs)")

        if args.export_ubox:
            n = UboxExporter().export(satellites, args.export_ubox)
            print(f"Exported {n} satellites to {args.export_ubox} (Universe Sandbox .ubox)")

    except FileNotFoundError:
        path = args.input
        print(
            f"Error: Input file not found: {path}\n"
            f"Expected a simulation JSON file with 'Earth' and 'Satellite' entities.",
            file=sys.stderr,
        )
        sys.exit(1)
    except (ValueError, ConnectionError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _rewrite_legacy_argv(argv: list[str]) -> tuple[list[str], list[str]]:
    """Rewrite deprecated CLI flags to subcommand syntax.

    Returns (new_argv, deprecation_warnings).
    Existing tests and scripts using old flags continue to work
    but see a deprecation notice on stderr.
    """
    if len(argv) < 2:
        return argv, []

    # Already using a known subcommand — no rewriting needed
    if argv[1] in ('serve', 'generate', 'import', 'sweep'):
        return argv, []

    args = list(argv)
    dep_warnings: list[str] = []

    # --serve → serve
    if '--serve' in args:
        i = args.index('--serve')
        args = args[:i] + args[i + 1:]
        args.insert(1, 'serve')
        dep_warnings.append(
            "DeprecationWarning: '--serve' is deprecated. Use: humeris serve"
        )
        return args, dep_warnings

    # --import-opm FILE → import opm FILE
    if '--import-opm' in args:
        i = args.index('--import-opm')
        if i + 1 < len(args):
            file_path = args[i + 1]
            args = args[:i] + args[i + 2:]
            args.insert(1, 'import')
            args.insert(2, 'opm')
            args.append(file_path)
            dep_warnings.append(
                "DeprecationWarning: '--import-opm' is deprecated. "
                "Use: humeris import opm FILE"
            )
            return args, dep_warnings

    # --import-oem FILE → import oem FILE
    if '--import-oem' in args:
        i = args.index('--import-oem')
        if i + 1 < len(args):
            file_path = args[i + 1]
            args = args[:i] + args[i + 2:]
            args.insert(1, 'import')
            args.insert(2, 'oem')
            args.append(file_path)
            dep_warnings.append(
                "DeprecationWarning: '--import-oem' is deprecated. "
                "Use: humeris import oem FILE"
            )
            return args, dep_warnings

    # -i / --input present without subcommand → generate
    if '-i' in args or '--input' in args:
        args.insert(1, 'generate')
        dep_warnings.append(
            "DeprecationWarning: Bare mode is deprecated. "
            "Use: humeris generate -i FILE -o FILE"
        )
        return args, dep_warnings

    return args, []


def _add_generate_arguments(parser: argparse.ArgumentParser) -> None:
    """Add generate-specific arguments to a parser."""
    parser.add_argument(
        '--input', '-i', required=True,
        help="Path to input simulation JSON (with Earth + Satellite template)"
    )
    parser.add_argument(
        '--output', '-o', required=True,
        help="Path to write output simulation JSON"
    )
    parser.add_argument(
        '--base-id', type=int, default=100,
        help="Starting entity ID (default: 100)"
    )
    parser.add_argument(
        '--template-name', default='Satellite',
        help="Name of satellite template entity (default: Satellite)"
    )

    live_group = parser.add_argument_group('live data (CelesTrak)')
    live_group.add_argument(
        '--live-group',
        help="CelesTrak group (e.g. STATIONS, GPS-OPS, STARLINK, ONEWEB, ACTIVE)"
    )
    live_group.add_argument('--live-name', help="Search by satellite name")
    live_group.add_argument('--live-catnr', type=int, help="NORAD catalog number")
    live_group.add_argument(
        '--concurrent', action='store_true', default=False,
        help="Use concurrent SGP4 propagation (faster for large groups)"
    )

    export_group = parser.add_argument_group('export')
    export_group.add_argument(
        '--export-csv',
        help="Export satellite positions to CSV (geodetic coordinates)"
    )
    export_group.add_argument(
        '--export-geojson',
        help="Export satellite positions to GeoJSON (FeatureCollection)"
    )
    export_group.add_argument(
        '--export-html',
        help="Export interactive 3D viewer as self-contained HTML (CesiumJS)"
    )
    export_group.add_argument(
        '--cesium-token', default="",
        help="Cesium Ion access token for imagery (optional, viewer works without)"
    )
    export_group.add_argument(
        '--export-celestia',
        help="Export constellation to Celestia Solar System Catalog (.ssc)"
    )
    export_group.add_argument(
        '--export-kml',
        help="Export constellation to KML for Google Earth (.kml)"
    )
    export_group.add_argument(
        '--export-tle',
        help="Export constellation as Two-Line Elements for Stellarium (.tle)"
    )
    export_group.add_argument(
        '--export-blender',
        help="Export constellation as Blender Python script (.py)"
    )
    export_group.add_argument(
        '--export-spaceengine',
        help="Export constellation for SpaceEngine (.sc)"
    )
    export_group.add_argument(
        '--export-ksp',
        help="Export constellation for Kerbal Space Program (.sfs)"
    )
    export_group.add_argument(
        '--export-ubox',
        help="Export constellation for Universe Sandbox (.ubox)"
    )
    export_group.add_argument(
        '--no-orbits', action='store_true', default=False,
        help="Omit orbit path lines from KML and Blender exports"
    )
    export_group.add_argument(
        '--kml-planes', action='store_true', default=False,
        help="Organize KML by orbital plane folders"
    )
    export_group.add_argument(
        '--kml-isl', action='store_true', default=False,
        help="Include ISL topology lines in KML export"
    )
    export_group.add_argument(
        '--blender-colors', action='store_true', default=False,
        help="Color-code satellites by orbital plane in Blender export"
    )


def _get_version() -> str:
    """Get package version string."""
    from humeris.version import __version__
    return __version__


def main():
    # Rewrite legacy argv to subcommand syntax (backward compat)
    rewritten_argv, dep_warnings = _rewrite_legacy_argv(sys.argv)
    for w in dep_warnings:
        print(w, file=sys.stderr)

    parser = argparse.ArgumentParser(
        prog="humeris",
        description="Satellite constellation analysis — generation, propagation, visualization",
    )
    parser.add_argument(
        '--version', action='version',
        version=f"humeris-core {_get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # --- serve ---
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start interactive 3D viewer server (opens browser)",
    )
    serve_parser.add_argument(
        '--port', type=int, default=8765,
        help="Port for viewer server (default: 8765)"
    )
    serve_parser.add_argument(
        '--load-session',
        help="Load a saved session JSON file at startup"
    )
    serve_parser.add_argument(
        '--headless', action='store_true', default=False,
        help="Run without browser or server — load session, export, exit"
    )
    serve_parser.add_argument(
        '--export-czml',
        help="Export all layers as CZML files to directory (used with --headless)"
    )

    # --- generate ---
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate synthetic or live constellation and export",
    )
    _add_generate_arguments(generate_parser)

    # --- import ---
    import_parser = subparsers.add_parser(
        "import",
        help="Import CCSDS orbital data files",
    )
    import_subparsers = import_parser.add_subparsers(dest="import_format")
    opm_parser = import_subparsers.add_parser(
        "opm", help="Import CCSDS OPM file (.opm)"
    )
    opm_parser.add_argument("file", help="Path to OPM file")
    oem_parser = import_subparsers.add_parser(
        "oem", help="Import CCSDS OEM file (.oem)"
    )
    oem_parser.add_argument("file", help="Path to OEM file")

    # --- sweep ---
    sweep_parser = subparsers.add_parser(
        "sweep",
        help="Run parameter sweep for trade studies (batch mode)",
    )
    sweep_parser.add_argument(
        '--param', action='append', required=True,
        help="Parameter sweep spec: name:min:max:step (repeatable)"
    )
    sweep_parser.add_argument(
        '--metric', required=True,
        help="Metric type to compute (coverage, eclipse, beta_angle, deorbit, station_keeping)"
    )
    sweep_parser.add_argument(
        '--output', '-o', required=True,
        help="Output file path (.csv or .json)"
    )
    sweep_parser.add_argument(
        '--format', choices=['csv', 'json'], default='csv',
        help="Output format (default: csv)"
    )

    args = parser.parse_args(rewritten_argv[1:])

    # Dispatch
    if args.command == "serve":
        _run_serve(
            port=args.port,
            load_session_path=args.load_session,
            headless=args.headless,
            export_czml_path=args.export_czml,
        )
    elif args.command == "generate":
        _run_generate(args)
    elif args.command == "import":
        if args.import_format == "opm":
            _run_import_opm(args.file)
        elif args.import_format == "oem":
            _run_import_oem(args.file)
        else:
            import_parser.print_help()
            sys.exit(1)
    elif args.command == "sweep":
        _run_sweep(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
