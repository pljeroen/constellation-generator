# Copyright (c) Jeroen Visser. MIT License.
"""Humeris GUI — Satellite Constellation Export Tool.

A standalone graphical tool for exporting constellations to 9 supported
formats. Uses tkinter (stdlib). Designed to be operable by a 12-year-old.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OptionSpec:
    """A format-specific option (checkbox or spin)."""

    key: str
    label: str
    type: str  # "bool" or "int"
    default: Any
    exporter_kwarg: str


@dataclass(frozen=True)
class FormatSpec:
    """Specification for one export format."""

    key: str
    label: str
    description: str
    extension: str
    default_filename: str
    exporter_factory: Callable[..., Any]
    options: list[OptionSpec] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Exporter factories — thin wrappers around adapter constructors
# ---------------------------------------------------------------------------

def _csv_factory(**_kwargs: Any) -> Any:
    from humeris.adapters.csv_exporter import CsvSatelliteExporter
    return CsvSatelliteExporter()


def _geojson_factory(**_kwargs: Any) -> Any:
    from humeris.adapters.geojson_exporter import GeoJsonSatelliteExporter
    return GeoJsonSatelliteExporter()


def _kml_factory(**kwargs: Any) -> Any:
    from humeris.adapters.kml_exporter import KmlExporter
    return KmlExporter(**kwargs)


def _celestia_factory(**_kwargs: Any) -> Any:
    from humeris.adapters.celestia_exporter import CelestiaExporter
    return CelestiaExporter()


def _stellarium_factory(**_kwargs: Any) -> Any:
    from humeris.adapters.stellarium_exporter import StellariumExporter
    return StellariumExporter()


def _blender_factory(**kwargs: Any) -> Any:
    from humeris.adapters.blender_exporter import BlenderExporter
    return BlenderExporter(**kwargs)


def _spaceengine_factory(**_kwargs: Any) -> Any:
    from humeris.adapters.spaceengine_exporter import SpaceEngineExporter
    return SpaceEngineExporter()


def _ksp_factory(**kwargs: Any) -> Any:
    from humeris.adapters.ksp_exporter import KspExporter
    return KspExporter(**kwargs)


def _ubox_factory(**_kwargs: Any) -> Any:
    from humeris.adapters.ubox_exporter import UboxExporter
    return UboxExporter()


# ---------------------------------------------------------------------------
# Format specifications
# ---------------------------------------------------------------------------

FORMAT_SPECS: list[FormatSpec] = [
    FormatSpec(
        key="csv",
        label="CSV",
        description="Spreadsheet data (.csv)",
        extension=".csv",
        default_filename="constellation.csv",
        exporter_factory=_csv_factory,
        options=[],
    ),
    FormatSpec(
        key="geojson",
        label="GeoJSON",
        description="For mapping tools (.geojson)",
        extension=".geojson",
        default_filename="constellation.geojson",
        exporter_factory=_geojson_factory,
        options=[],
    ),
    FormatSpec(
        key="kml",
        label="KML",
        description="For Google Earth (.kml)",
        extension=".kml",
        default_filename="constellation.kml",
        exporter_factory=_kml_factory,
        options=[
            OptionSpec("include_orbits", "Show orbit lines", "bool", True, "include_orbits"),
            OptionSpec("include_planes", "Group by plane", "bool", False, "include_planes"),
            OptionSpec("include_isl", "Show links between satellites", "bool", False, "include_isl"),
        ],
    ),
    FormatSpec(
        key="celestia",
        label="Celestia",
        description="Celestia planetarium (.ssc)",
        extension=".ssc",
        default_filename="constellation.ssc",
        exporter_factory=_celestia_factory,
        options=[],
    ),
    FormatSpec(
        key="stellarium",
        label="Stellarium",
        description="Planetarium app (.tle)",
        extension=".tle",
        default_filename="constellation.tle",
        exporter_factory=_stellarium_factory,
        options=[],
    ),
    FormatSpec(
        key="blender",
        label="Blender",
        description="3D modeling script (.py)",
        extension=".py",
        default_filename="constellation.py",
        exporter_factory=_blender_factory,
        options=[
            OptionSpec("include_orbits", "Show orbit lines", "bool", True, "include_orbits"),
            OptionSpec("color_by_plane", "Color by plane", "bool", False, "color_by_plane"),
        ],
    ),
    FormatSpec(
        key="spaceengine",
        label="SpaceEngine",
        description="SpaceEngine catalog (.sc)",
        extension=".sc",
        default_filename="constellation.sc",
        exporter_factory=_spaceengine_factory,
        options=[],
    ),
    FormatSpec(
        key="ksp",
        label="KSP",
        description="Kerbal Space Program (.sfs)",
        extension=".sfs",
        default_filename="constellation.sfs",
        exporter_factory=_ksp_factory,
        options=[
            OptionSpec("scale_to_kerbin", "Scale orbits to Kerbin", "bool", True, "scale_to_kerbin"),
        ],
    ),
    FormatSpec(
        key="ubox",
        label="Universe Sandbox",
        description="Universe Sandbox simulation (.ubox)",
        extension=".ubox",
        default_filename="constellation.ubox",
        exporter_factory=_ubox_factory,
        options=[],
    ),
]

# ---------------------------------------------------------------------------
# CelesTrak groups
# ---------------------------------------------------------------------------

CELESTRAK_GROUPS: list[str] = [
    "STARLINK",
    "ONEWEB",
    "STATIONS",
    "ACTIVE",
    "VISUAL",
    "WEATHER",
    "NOAA",
    "GOES",
    "RESOURCE",
    "SARSAT",
    "GPS-OPS",
    "GALILEO",
    "BEIDOU",
    "IRIDIUM",
    "IRIDIUM-NEXT",
    "GLOBALSTAR",
    "ORBCOMM",
    "AMATEUR",
    "SCIENCE",
    "GEODETIC",
]


# ---------------------------------------------------------------------------
# Satellite loading
# ---------------------------------------------------------------------------

MAX_SATS_PER_SHELL = 5000
MAX_TOTAL_SATS = 50000


def validate_shell_dict(d: dict[str, Any]) -> str | None:
    """Validate a shell config dict. Returns error string or None if valid."""
    alt = d.get("altitude_km", 0)
    if not (0 < alt < 50000):
        return f"Altitude must be between 0 and 50,000 km (got {alt})"

    inc = d.get("inclination_deg", 0)
    if not (0 <= inc <= 180):
        return f"Inclination must be between 0 and 180 degrees (got {inc})"

    planes = d.get("num_planes", 0)
    if not (1 <= planes <= 100):
        return f"Planes must be between 1 and 100 (got {planes})"

    spp = d.get("sats_per_plane", 0)
    if not (1 <= spp <= 100):
        return f"Sats per plane must be between 1 and 100 (got {spp})"

    total = planes * spp
    if total > MAX_SATS_PER_SHELL:
        return f"Too many satellites in one shell: {total:,} (max {MAX_SATS_PER_SHELL:,})"

    return None


def build_shell_configs(shell_dicts: list[dict[str, Any]]) -> list[Any]:
    """Build ShellConfig objects from a list of parameter dicts."""
    from humeris.domain.constellation import ShellConfig

    configs = []
    for d in shell_dicts:
        configs.append(ShellConfig(
            altitude_km=float(d["altitude_km"]),
            inclination_deg=float(d["inclination_deg"]),
            num_planes=int(d["num_planes"]),
            sats_per_plane=int(d["sats_per_plane"]),
            phase_factor=int(d["phase_factor"]),
            raan_offset_deg=float(d["raan_offset_deg"]),
            shell_name=str(d["shell_name"]),
        ))
    return configs


def generate_from_configs(configs: list[Any]) -> list[Any]:
    """Generate satellites from a list of ShellConfig objects."""
    from humeris.domain.constellation import generate_walker_shell

    satellites: list[Any] = []
    for config in configs:
        satellites.extend(generate_walker_shell(config))
    return satellites


def load_default_satellites() -> list[Any]:
    """Load the default constellation (Walker shells + SSO band)."""
    from humeris.cli import get_default_shells

    return generate_from_configs(get_default_shells())


# ---------------------------------------------------------------------------
# Export orchestration
# ---------------------------------------------------------------------------

def run_export(
    satellites: list[Any],
    spec: FormatSpec,
    output_dir: str,
    filename: str,
    options: dict[str, Any],
) -> int:
    """Run a single export. Returns number of satellites exported."""
    # Map option keys to exporter kwargs
    factory_kwargs: dict[str, Any] = {}
    for opt in spec.options:
        if opt.key in options:
            factory_kwargs[opt.exporter_kwarg] = options[opt.key]
        else:
            factory_kwargs[opt.exporter_kwarg] = opt.default

    exporter = spec.exporter_factory(**factory_kwargs)
    path = os.path.join(output_dir, filename)
    return exporter.export(satellites, path)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class HumerisGui:
    """Main GUI window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Humeris — Satellite Constellation Export")
        self.root.geometry("620x780")
        self.root.resizable(True, True)

        self._satellites: list[Any] = []
        self._format_vars: dict[str, tk.BooleanVar] = {}
        self._filename_vars: dict[str, tk.StringVar] = {}
        self._option_vars: dict[str, dict[str, tk.BooleanVar]] = {}
        self._option_frames: dict[str, tk.Frame] = {}
        self._source_var = tk.StringVar(value="default")
        self._celestrak_group_var = tk.StringVar(value="STARLINK")
        self._status_var = tk.StringVar(value="Loading default constellation...")
        self._export_status_var = tk.StringVar(value="")
        self._shell_rows: list[dict[str, tk.StringVar]] = []

        # Default output directory
        docs = Path.home() / "Documents"
        desktop = Path.home() / "Desktop"
        if docs.exists():
            default_dir = str(docs / "humeris-export")
        elif desktop.exists():
            default_dir = str(desktop / "humeris-export")
        else:
            default_dir = str(Path.home() / "humeris-export")
        self._output_dir_var = tk.StringVar(value=default_dir)

        self._build_ui()
        self._load_defaults_async()

    def _build_ui(self) -> None:
        """Build the complete UI."""
        # Main scrollable frame
        canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel
        def _on_mousewheel(event: Any) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_linux_scroll_up(event: Any) -> None:
            canvas.yview_scroll(-1, "units")

        def _on_linux_scroll_down(event: Any) -> None:
            canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_linux_scroll_up)
        canvas.bind_all("<Button-5>", _on_linux_scroll_down)

        pad = {"padx": 10, "pady": 5}

        # --- Source section ---
        src_frame = ttk.LabelFrame(scroll_frame, text="WHERE DO THE SATELLITES COME FROM?")
        src_frame.pack(fill="x", **pad)

        ttk.Radiobutton(
            src_frame,
            text="Default constellation (4,752 satellites)",
            variable=self._source_var,
            value="default",
            command=self._on_source_change,
        ).pack(anchor="w", padx=5, pady=2)

        cel_frame = ttk.Frame(src_frame)
        cel_frame.pack(fill="x", padx=5, pady=2)
        ttk.Radiobutton(
            cel_frame,
            text="Live from CelesTrak:",
            variable=self._source_var,
            value="celestrak",
            command=self._on_source_change,
        ).pack(side="left")
        self._celestrak_combo = ttk.Combobox(
            cel_frame,
            textvariable=self._celestrak_group_var,
            values=CELESTRAK_GROUPS,
            state="readonly",
            width=20,
        )
        self._celestrak_combo.pack(side="left", padx=5)
        self._celestrak_combo.bind("<<ComboboxSelected>>", lambda _: self._on_source_change())

        ttk.Radiobutton(
            src_frame,
            text="Custom constellation",
            variable=self._source_var,
            value="custom",
            command=self._on_source_change,
        ).pack(anchor="w", padx=5, pady=2)

        # Custom shell editor (hidden until "custom" selected)
        self._custom_frame = ttk.Frame(src_frame)
        self._shell_list_frame = ttk.Frame(self._custom_frame)
        self._shell_list_frame.pack(fill="x", padx=5, pady=2)

        btn_row = ttk.Frame(self._custom_frame)
        btn_row.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_row, text="+ Add shell", command=self._add_shell_row).pack(side="left", padx=2)
        ttk.Button(btn_row, text="- Remove last", command=self._remove_shell_row).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Generate", command=self._generate_custom).pack(side="left", padx=10)

        # Start with one default shell row
        self._add_shell_row()

        ttk.Label(src_frame, textvariable=self._status_var).pack(anchor="w", padx=5, pady=2)

        # --- Format section ---
        fmt_frame = ttk.LabelFrame(scroll_frame, text="PICK YOUR EXPORT FORMATS")
        fmt_frame.pack(fill="x", **pad)

        for spec in FORMAT_SPECS:
            self._build_format_row(fmt_frame, spec)

        # --- Output directory ---
        dir_frame = ttk.LabelFrame(scroll_frame, text="SAVE TO")
        dir_frame.pack(fill="x", **pad)

        dir_row = ttk.Frame(dir_frame)
        dir_row.pack(fill="x", padx=5, pady=5)
        ttk.Entry(dir_row, textvariable=self._output_dir_var, width=50).pack(side="left", fill="x", expand=True)
        ttk.Button(dir_row, text="Pick", command=self._pick_directory).pack(side="left", padx=5)

        # --- Export button ---
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill="x", **pad)

        self._export_btn = ttk.Button(
            btn_frame,
            text="EXPORT!",
            command=self._on_export,
        )
        self._export_btn.pack(fill="x", padx=20, pady=10, ipady=8)

        ttk.Label(btn_frame, textvariable=self._export_status_var).pack(anchor="center", pady=5)

    def _build_format_row(self, parent: ttk.Frame, spec: FormatSpec) -> None:
        """Build a single format row with checkbox, filename, and options."""
        var = tk.BooleanVar(value=(spec.key == "csv"))
        self._format_vars[spec.key] = var

        row = ttk.Frame(parent)
        row.pack(fill="x", padx=5, pady=2)

        ttk.Checkbutton(
            row,
            text=f"{spec.label} — {spec.description}",
            variable=var,
            command=lambda k=spec.key: self._on_format_toggle(k),
        ).pack(anchor="w")

        # Filename entry + browse
        file_frame = ttk.Frame(row)
        file_frame.pack(fill="x", padx=20, pady=1)

        fn_var = tk.StringVar(value=spec.default_filename)
        self._filename_vars[spec.key] = fn_var
        ttk.Entry(file_frame, textvariable=fn_var, width=35).pack(side="left")
        ttk.Button(
            file_frame,
            text="Browse",
            command=lambda k=spec.key, ext=spec.extension: self._browse_filename(k, ext),
        ).pack(side="left", padx=5)

        # Format-specific options
        if spec.options:
            opt_frame = ttk.Frame(row)
            opt_frame.pack(fill="x", padx=20, pady=1)
            self._option_frames[spec.key] = opt_frame
            self._option_vars[spec.key] = {}

            for opt in spec.options:
                opt_var = tk.BooleanVar(value=opt.default)
                self._option_vars[spec.key][opt.key] = opt_var
                ttk.Checkbutton(opt_frame, text=opt.label, variable=opt_var).pack(
                    side="left", padx=5,
                )

    def _on_format_toggle(self, key: str) -> None:
        """Show/hide options when format is toggled."""
        if key in self._option_frames:
            if self._format_vars[key].get():
                self._option_frames[key].pack(fill="x", padx=20, pady=1)
            else:
                self._option_frames[key].pack_forget()

    def _pick_directory(self) -> None:
        """Open folder picker for output directory."""
        d = filedialog.askdirectory(
            title="Select output folder",
            initialdir=self._output_dir_var.get(),
        )
        if d:
            self._output_dir_var.set(d)

    def _browse_filename(self, key: str, ext: str) -> None:
        """Open file save dialog for a specific format."""
        f = filedialog.asksaveasfilename(
            title=f"Save {key} file",
            defaultextension=ext,
            initialfile=self._filename_vars[key].get(),
            initialdir=self._output_dir_var.get(),
        )
        if f:
            self._filename_vars[key].set(os.path.basename(f))
            self._output_dir_var.set(os.path.dirname(f))

    def _add_shell_row(self) -> None:
        """Add a new shell configuration row."""
        if len(self._shell_rows) >= 10:
            return

        idx = len(self._shell_rows) + 1
        row_vars: dict[str, tk.StringVar] = {
            "altitude_km": tk.StringVar(value="550"),
            "inclination_deg": tk.StringVar(value="53"),
            "num_planes": tk.StringVar(value="6"),
            "sats_per_plane": tk.StringVar(value="22"),
            "phase_factor": tk.StringVar(value="1"),
            "raan_offset_deg": tk.StringVar(value="0.0"),
            "shell_name": tk.StringVar(value=f"Shell {idx}"),
        }

        frame = ttk.LabelFrame(self._shell_list_frame, text=f"Shell {idx}")
        frame.pack(fill="x", padx=2, pady=2)
        row_vars["_frame"] = frame  # type: ignore[assignment]

        # Row 1: altitude, inclination, name
        r1 = ttk.Frame(frame)
        r1.pack(fill="x", padx=5, pady=1)
        ttk.Label(r1, text="Altitude (km):").pack(side="left")
        ttk.Entry(r1, textvariable=row_vars["altitude_km"], width=8).pack(side="left", padx=2)
        ttk.Label(r1, text="Inclination (°):").pack(side="left", padx=(10, 0))
        ttk.Entry(r1, textvariable=row_vars["inclination_deg"], width=6).pack(side="left", padx=2)
        ttk.Label(r1, text="Name:").pack(side="left", padx=(10, 0))
        ttk.Entry(r1, textvariable=row_vars["shell_name"], width=15).pack(side="left", padx=2)

        # Row 2: planes, sats/plane, phase factor, RAAN offset
        r2 = ttk.Frame(frame)
        r2.pack(fill="x", padx=5, pady=1)
        ttk.Label(r2, text="Planes:").pack(side="left")
        ttk.Entry(r2, textvariable=row_vars["num_planes"], width=5).pack(side="left", padx=2)
        ttk.Label(r2, text="Sats/plane:").pack(side="left", padx=(10, 0))
        ttk.Entry(r2, textvariable=row_vars["sats_per_plane"], width=5).pack(side="left", padx=2)
        ttk.Label(r2, text="Phase factor:").pack(side="left", padx=(10, 0))
        ttk.Entry(r2, textvariable=row_vars["phase_factor"], width=4).pack(side="left", padx=2)
        ttk.Label(r2, text="RAAN offset (°):").pack(side="left", padx=(10, 0))
        ttk.Entry(r2, textvariable=row_vars["raan_offset_deg"], width=6).pack(side="left", padx=2)

        self._shell_rows.append(row_vars)

    def _remove_shell_row(self) -> None:
        """Remove the last shell configuration row."""
        if len(self._shell_rows) <= 1:
            return
        row = self._shell_rows.pop()
        row["_frame"].destroy()  # type: ignore[union-attr]

    def _get_shell_dicts(self) -> list[dict[str, Any]]:
        """Read current shell rows into dicts."""
        result = []
        for row in self._shell_rows:
            try:
                result.append({
                    "altitude_km": float(row["altitude_km"].get()),
                    "inclination_deg": float(row["inclination_deg"].get()),
                    "num_planes": int(row["num_planes"].get()),
                    "sats_per_plane": int(row["sats_per_plane"].get()),
                    "phase_factor": int(row["phase_factor"].get()),
                    "raan_offset_deg": float(row["raan_offset_deg"].get()),
                    "shell_name": row["shell_name"].get(),
                })
            except ValueError as e:
                self._status_var.set(f"Invalid number: {e}")
                return []
        return result

    def _generate_custom(self) -> None:
        """Generate satellites from custom shell specifications."""
        shell_dicts = self._get_shell_dicts()
        if not shell_dicts:
            return

        # Validate each shell
        for i, d in enumerate(shell_dicts):
            error = validate_shell_dict(d)
            if error:
                self._status_var.set(f"Shell {i + 1}: {error}")
                return

        # Check total count
        total = sum(d["num_planes"] * d["sats_per_plane"] for d in shell_dicts)
        if total > MAX_TOTAL_SATS:
            self._status_var.set(f"Too many satellites total: {total:,} (max {MAX_TOTAL_SATS:,})")
            return

        self._status_var.set("Generating custom constellation...")

        def _gen() -> None:
            try:
                configs = build_shell_configs(shell_dicts)
                sats = generate_from_configs(configs)
                self.root.after(0, lambda: self._on_satellites_loaded(sats))
            except Exception as e:
                self.root.after(0, lambda: self._status_var.set(f"Error: {e}"))

        threading.Thread(target=_gen, daemon=True).start()

    def _on_source_change(self) -> None:
        """Handle source radio button change."""
        source = self._source_var.get()
        if source == "custom":
            self._custom_frame.pack(fill="x", padx=5, pady=2)
        else:
            self._custom_frame.pack_forget()

        if source == "default":
            self._load_defaults_async()
        elif source == "celestrak":
            self._fetch_celestrak_async()

    def _load_defaults_async(self) -> None:
        """Load default constellation in background thread."""
        self._status_var.set("Loading default constellation...")

        def _load() -> None:
            try:
                sats = load_default_satellites()
                self.root.after(0, lambda: self._on_satellites_loaded(sats))
            except Exception as e:
                self.root.after(0, lambda: self._status_var.set(f"Error: {e}"))

        threading.Thread(target=_load, daemon=True).start()

    def _fetch_celestrak_async(self) -> None:
        """Fetch satellites from CelesTrak in background thread."""
        group = self._celestrak_group_var.get()
        self._status_var.set(f"Fetching {group} from CelesTrak...")

        def _fetch() -> None:
            try:
                from humeris.adapters.celestrak import CelesTrakAdapter
                adapter = CelesTrakAdapter()
                sats = adapter.fetch_satellites(group=group.lower())
                self.root.after(0, lambda: self._on_satellites_loaded(sats))
            except ImportError:
                self.root.after(
                    0,
                    lambda: self._status_var.set(
                        "CelesTrak requires sgp4: pip install humeris-core[live]"
                    ),
                )
            except Exception as e:
                self.root.after(0, lambda: self._status_var.set(f"Error: {e}"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_satellites_loaded(self, satellites: list[Any]) -> None:
        """Callback when satellites are loaded."""
        self._satellites = satellites
        count = len(satellites)
        self._status_var.set(f"{count:,} satellites ready")

    def _on_export(self) -> None:
        """Run export for all checked formats."""
        if not self._satellites:
            messagebox.showwarning("No satellites", "No satellites loaded yet. Please wait.")
            return

        selected = [s for s in FORMAT_SPECS if self._format_vars[s.key].get()]
        if not selected:
            messagebox.showwarning("No formats", "Please select at least one export format.")
            return

        output_dir = self._output_dir_var.get()
        os.makedirs(output_dir, exist_ok=True)

        self._export_btn.configure(state="disabled")
        self._export_status_var.set("Exporting...")

        def _do_export() -> None:
            results: list[str] = []
            errors: list[str] = []

            for spec in selected:
                filename = self._filename_vars[spec.key].get()
                options: dict[str, Any] = {}
                if spec.key in self._option_vars:
                    for opt_key, opt_var in self._option_vars[spec.key].items():
                        options[opt_key] = opt_var.get()

                try:
                    count = run_export(self._satellites, spec, output_dir, filename, options)
                    results.append(f"{spec.label}: {count:,} satellites → {filename}")
                except Exception as e:
                    errors.append(f"{spec.label}: {e}")

            def _done() -> None:
                self._export_btn.configure(state="normal")
                if errors:
                    msg = "\n".join(results + [""] + ["ERRORS:"] + errors)
                    self._export_status_var.set(f"Exported with {len(errors)} error(s)")
                    messagebox.showwarning("Export completed with errors", msg)
                else:
                    self._export_status_var.set(
                        f"Exported {len(self._satellites):,} satellites to {len(results)} file(s)"
                    )
                    if len(results) <= 5:
                        messagebox.showinfo("Export complete", "\n".join(results))

            self.root.after(0, _done)

        threading.Thread(target=_do_export, daemon=True).start()

    def run(self) -> None:
        """Start the GUI main loop."""
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Console script entry point."""
    gui = HumerisGui()
    gui.run()


if __name__ == "__main__":
    main()
