# Delta 2 — Deterministic Capability Upgrades

**Scope**: Physics fidelity, EKF upgrades, sustainability composition, optimization.
Cloud/agent/serverless explicitly deferred — but interfaces defined now to prevent future refactors.

**Constraint**: All new domain code is stdlib-only. All new interfaces use `Protocol` (structural typing).
External dependencies confined to adapter layer.

---

## Phase 1: High-Value Connects (days)

These connect existing modules that currently don't talk to each other.

### 1.1 Perturbation-Aware EKF

**Problem**: `orbit_determination.run_ekf()` uses hardcoded two-body dynamics in `_two_body_propagate()`.
The numerical propagator already supports J2/J3/drag/SRP/third-body via `ForceModel` composition.
These two systems don't talk.

**Change**: Replace `_two_body_propagate()` with a call through `ForceModel` composition.
Add optional `force_models: list[ForceModel] | None` parameter to `run_ekf()`.
When `None`, fall back to two-body (backward compatible).

**Files**:
- Modify: `domain/orbit_determination.py`
- Touch: none else — `ForceModel` protocol already exists in `domain/numerical_propagation.py`

**Acceptance**: EKF residuals decrease measurably when J2 is included vs two-body-only,
tested against a known J2-perturbed reference trajectory.

### 1.2 Incremental EKF API

**Problem**: `run_ekf()` takes a batch of observations. No way to process one observation
at a time for streaming use cases.

**Change**: Extract `EKFState` dataclass (frozen) holding current state, covariance, epoch.
Add `ekf_predict(state, dt, force_models) -> EKFState` and
`ekf_update(state, observation) -> EKFState`. The existing `run_ekf()` becomes a
loop over these two functions (no behavior change).

**Files**:
- Modify: `domain/orbit_determination.py`

**Acceptance**: `run_ekf()` produces identical results before and after refactor.
New incremental API processes observations one-at-a-time and matches batch output.

### 1.3 Constraint Handling in Pareto

**Problem**: `multi_objective_design._dominates()` has no constraint awareness.
Infeasible designs can appear on the Pareto front.

**Change**: Add Deb's constrained-domination rule: feasible always dominates infeasible;
among infeasible, lower total constraint violation dominates;
among feasible, standard Pareto domination applies.

Add `DesignConstraint` protocol:
```python
class DesignConstraint(Protocol):
    def violation(self, point: ParetoPoint) -> float: ...
    # 0.0 = feasible, >0.0 = magnitude of violation
```

Pass `constraints: list[DesignConstraint]` to `compute_pareto_surface()`.
Default empty list (backward compatible).

**Files**:
- Modify: `domain/multi_objective_design.py`

**Acceptance**: Known infeasible points excluded from Pareto front.
Empty constraint list reproduces current behavior exactly.

---

## Phase 2: New Physics (1-2 weeks each)

New `ForceModel` implementations. Plug directly into existing `propagate_numerical()` via
force composition — no changes to propagator or integrators needed.

### 2.1 Earth Albedo Radiation Pressure

**What**: Sunlight reflected off Earth's surface pushes satellites.
Effect: ~5-15% of direct SRP. Ignored by most commercial tools, not by NASA.

**Approach**: Discretize visible Earth disk into surface patches.
Each patch: compute reflected irradiance (Lambertian, albedo coefficient per latitude band),
view factor to satellite, integrate pressure over visible disk.
Albedo coefficients: monthly zonal averages (hardcoded lookup table from CERES climatology,
~20 latitude bands × 12 months — small enough to embed in source).

**Files**:
- New: `domain/albedo.py` — `EarthAlbedoForce(ForceModel)`, albedo coefficient table
- Uses: `domain/solar.py` (Sun position for illuminated fraction)
- Uses: `domain/coordinate_frames.py` (ECI↔ECEF for surface patch geometry)

**Acceptance**: Acceleration magnitude 1e-9 to 1e-8 m/s² at LEO.
Sign test: force vector has component away from sub-solar point.
Null test: force is zero during eclipse (no reflected light).

### 2.2 Relativistic Corrections

**What**: General relativistic perturbations per IERS Conventions 2010, Chapter 10.

**Schwarzschild** (dominant): Perihelion-like precession from spacetime curvature.
```
a_S = (GM/c²r³) * [(2(β+γ)GM/r - γv²)r + 2(1+γ)(r·v)v]
```
With PPN parameters β=γ=1 for GR.

**Lense-Thirring** (frame-dragging): Earth's rotation drags spacetime.
```
a_LT = (2GJ/c²r³) * [(3/r²)(r×v)(r·J) + v×J]
```
Where J is Earth's angular momentum vector.

At LEO: Schwarzschild ~1e-9 m/s², Lense-Thirring ~1e-12 m/s².
Relevant for PNT constellations requiring sub-centimeter accuracy.

**Files**:
- New: `domain/relativistic.py` — `SchwarzschildForce(ForceModel)`, `LenseThirringForce(ForceModel)`

**Acceptance**: Schwarzschild precession rate matches analytical prediction (≈2 mm/rev at LEO).
Lense-Thirring effect visible in RAAN drift over multi-day propagation.
Both are zero when c→∞ (sanity check with artificially large c).

---

## Phase 3: Sustainability Composition (1-2 weeks each)

Composing existing modules into higher-level assessments.

### 3.1 Sustainability Score

**What**: Composite metric combining existing analyses into a single auditable assessment.

**Components** (all already implemented):
- Deorbit compliance probability → `deorbit.py`
- Collision contribution to background → `conjunction.py` + `statistical_analysis.py`
- Cascade amplification factor → `cascade_analysis.py`
- Maneuverability margin → `station_keeping.py`

**Score structure** (not a single number — a structured report):
```python
@dataclass(frozen=True)
class SustainabilityAssessment:
    deorbit_compliance: DeorbitAssessment           # from deorbit.py
    collision_contribution: float                    # added ΔPoC to background
    cascade_amplification: CascadeIndicator          # from cascade_analysis.py
    maneuver_margin_years: float                     # fuel reserve beyond mission life
    regulatory_status: dict[str, bool]               # FCC 5yr, ESA 25yr, etc.
    grade: str                                       # A-F, deterministic from above
```

Grading: deterministic threshold-based (not weighted). A = all pass.
F = deorbit non-compliant OR cascade risk. No subjective weights.

**Files**:
- New: `domain/sustainability_score.py`
- Uses: `domain/deorbit.py`, `domain/conjunction.py`, `domain/cascade_analysis.py`,
  `domain/station_keeping.py`, `domain/statistical_analysis.py`

**Acceptance**: Grade F if and only if deorbit non-compliant or cascade risk flagged.
Grade A requires all four components in "green" thresholds.
Reproducible: same inputs always produce same grade.

### 3.2 Adversarial Self-Review

**What**: Automated "red team" report that stress-tests a mission plan against failure modes.

**Pipeline** (deterministic, no LLM):
1. Run sustainability score (3.1)
2. For each satellite: simulate single-satellite failure → recompute cascade indicator
3. Identify worst-case failure (highest cascade amplification)
4. Compute coverage degradation under worst-case failure
5. Compute fuel budget impact of evasive maneuvers for remaining constellation
6. Package as structured `MissionReview` result

```python
@dataclass(frozen=True)
class MissionReview:
    sustainability: SustainabilityAssessment
    worst_case_failure: WorstCaseFailure
    coverage_degradation_percent: float
    evasion_fuel_cost_kg: float
    single_points_of_failure: tuple[int, ...]    # satellite indices
    review_pass: bool                             # all criteria met
```

**Files**:
- New: `domain/mission_review.py`
- Uses: `domain/sustainability_score.py` (3.1), `domain/coverage.py`,
  `domain/conjunction.py`, `domain/station_keeping.py`

**Acceptance**: Review fails if any single-satellite failure triggers cascade risk.
Review fails if coverage drops below configurable threshold under worst case.
Deterministic: same constellation always produces same review.

---

## Phase 4: Optimization & Live Data (2-4 weeks each)

### 4.1 NSGA-II Multi-Objective Optimizer

**What**: Non-dominated Sorting Genetic Algorithm II. Replaces parametric sweep for
high-dimensional design spaces (>3 parameters).

**Why not earlier**: Walker constellations are inherently low-dimensional (altitude, inclination,
planes, sats/plane, phase factor). Parametric sweep is appropriate there.
NSGA-II becomes necessary for continuous design spaces or hybrid constellations.

**Implementation** (stdlib only — no DEAP, no pymoo):
- Non-dominated sorting with crowding distance
- SBX crossover + polynomial mutation
- Population: configurable (default 200)
- Generations: configurable (default 100)
- Objective functions: any `Callable[[DesignPoint], tuple[float, ...]]`
- Constraint handling: Deb's method (from 1.3)

```python
@dataclass(frozen=True)
class NSGAIIConfig:
    population_size: int
    generations: int
    crossover_prob: float
    mutation_prob: float
    seed: int                    # deterministic reproducibility

def nsga2_optimize(
    objectives: list[Callable[[DesignPoint], float]],
    bounds: list[tuple[float, float]],
    constraints: list[DesignConstraint],
    config: NSGAIIConfig,
) -> ParetoSurface: ...
```

**Files**:
- New: `domain/nsga2.py`
- Modify: `domain/multi_objective_design.py` (add NSGA-II as alternative to parametric sweep)

**Acceptance**: On ZDT1/ZDT2 test problems, converges to known Pareto front within
hypervolume tolerance. Deterministic given same seed. stdlib only.

### 4.2 Deterministic "What-If" Engine

**What**: Threshold-based rules that trigger recomputation when environmental parameters shift.
Not agentic — fully deterministic trigger conditions.

**Triggers** (each is a pure function `current_value -> bool`):
- Solar flux F10.7 exceeds threshold → recompute atmospheric drag → recompute lifetime
- Conjunction probability exceeds threshold → recompute evasion options
- Fuel margin drops below threshold → recompute maintenance schedule
- Coverage drops below threshold → flag for trade study

**Engine**: Evaluates triggers against current state, returns list of recommended actions.
No autonomous execution — returns a `list[RecommendedAction]` for the caller to act on.

```python
@dataclass(frozen=True)
class WhatIfTrigger:
    name: str
    condition: Callable[[MissionState], bool]
    action: str                    # human-readable description
    recompute: Callable[[MissionState], MissionState]

@dataclass(frozen=True)
class RecommendedAction:
    trigger_name: str
    description: str
    updated_state: MissionState
    delta_from_baseline: dict[str, float]
```

**Files**:
- New: `domain/what_if.py`
- Uses: `domain/atmosphere.py`, `domain/conjunction.py`, `domain/station_keeping.py`,
  `domain/coverage.py`

**Acceptance**: Each trigger fires deterministically at its threshold.
No trigger fires below threshold. Recomputation matches direct module call.

---

## Forward-Compatible Interfaces (Define Now, Implement Later)

These are Protocol definitions created alongside the phases above.
They cost nothing now but prevent refactors when the deferred capabilities are built.

### Port: TelemetrySource

**Purpose**: Live satellite position/velocity observations for incremental EKF (1.2).

```python
# ports/telemetry.py
class TelemetrySource(Protocol):
    def latest_observation(self, satellite_id: str) -> ODObservation | None: ...
    def observations_since(
        self, satellite_id: str, since: datetime
    ) -> list[ODObservation]: ...
```

**Used by**: Incremental EKF (1.2) accepts `ODObservation` directly — any adapter that
produces `ODObservation` works without domain changes.

**Future adapters**: `SpaceTrackAdapter`, `LeoLabsAdapter`, `SatNOGSAdapter`.
Each ~300-500 LOC, confined to adapter layer.

### Port: SpaceWeatherSource

**Purpose**: Solar activity indices for atmosphere model and what-if engine (4.2).

```python
# ports/space_weather.py
class SpaceWeatherSource(Protocol):
    def current_f107(self) -> float: ...          # 10.7 cm solar radio flux (SFU)
    def current_ap(self) -> float: ...            # geomagnetic index
    def predicted_f107(self, horizon_days: int) -> list[float]: ...
```

**Used by**: `atmosphere.py` currently uses hardcoded F10.7=150. Making it accept
a `SpaceWeatherSource` parameter (default: constant) is backward compatible.
What-if engine (4.2) uses `predicted_f107()` for proactive triggers.

**Future adapters**: `NOAASwpcAdapter` (NOAA Space Weather Prediction Center API).

### Port: DebrisPopulationSource

**Purpose**: Background debris density for Kessler risk heatmapping.

```python
# ports/debris_population.py
class DebrisPopulationSource(Protocol):
    def spatial_density(
        self, altitude_km: float, inclination_deg: float, min_size_m: float
    ) -> float: ...    # objects per km³

    def flux(
        self, altitude_km: float, inclination_deg: float, min_size_m: float
    ) -> float: ...    # impacts per m² per year
```

**Used by**: Future `domain/kessler_heatmap.py` (deferred).
The sustainability score (3.1) can optionally consume this to add a
`background_collision_contribution` field — the `SustainabilityAssessment` dataclass
should reserve this field as `Optional[float] = None` now.

**Future adapters**: `ORDEMAdapter` (NASA ORDEM 4.0), `MASTERAdapter` (ESA MASTER).
Both require external data files (~100MB+). Adapter-layer concern.

### Port: SimulationBatch

**Purpose**: Parallel simulation execution for Monte Carlo.

```python
# ports/simulation_batch.py
@dataclass(frozen=True)
class SimulationConfig:
    initial_state: OrbitalState
    force_models: tuple[str, ...]     # force model names, resolved by runner
    duration_s: float
    step_s: float
    parameters: dict[str, float]      # varied parameters for this sample

@dataclass(frozen=True)
class SimulationResult:
    config: SimulationConfig
    result: NumericalPropagationResult
    wall_time_s: float

class SimulationBatch(Protocol):
    def submit(self, configs: list[SimulationConfig]) -> str: ...     # returns batch_id
    def status(self, batch_id: str) -> str: ...                       # pending/running/done/failed
    def results(self, batch_id: str) -> list[SimulationResult]: ...
    def cancel(self, batch_id: str) -> None: ...
```

**Used by**: Future `domain/monte_carlo.py` (deferred).
Domain defines sampling strategy (Latin Hypercube, parameter distributions, convergence).
Execution delegated through this port. Local `ThreadPoolExecutor` adapter works for
small runs; cloud adapters (Lambda, Ray, Batch) plug in without domain changes.

**Future adapters**: `LocalBatchAdapter` (ThreadPoolExecutor), `AWSBatchAdapter`,
`RayBatchAdapter`.

---

## Explicitly Deferred

Items below are out of scope for delta2. Interfaces above ensure they plug in cleanly.

### Lorentz Force Modeling

**Why deferred**: The magnetic field model (IGRF) is ~300 LOC and straightforward.
The satellite charge model is an unsolved research problem for general spacecraft —
depends on plasma environment, surface materials, photoelectric yields, and secondary
electron emission. Effect magnitude: ~1e-12 m/s², negligible for all current use cases.

**When to revisit**: If electrodynamic tether analysis is requested.
**Interface**: Already covered by `ForceModel` protocol. A future `LorentzForce` class
plugs in with zero changes to propagator.

### Monte Carlo Orchestration

**Why deferred**: Infrastructure project, not physics. Requires serialization of all domain
result types across process boundaries, checkpoint/recovery, cost management.

**When to revisit**: When simulation count exceeds single-machine threading capacity
(~100 parallel on 32-core, minutes per run).
**Interface**: `SimulationBatch` port (defined above). Domain `monte_carlo.py` module
would define `MonteCarloStudy` (sampling strategy, convergence criterion, aggregation)
and delegate execution through the port.

### Cloud/Serverless Adapters

**Why deferred**: Depends on Monte Carlo orchestration. Adds operational complexity
(IaC, monitoring, billing, credentials) that changes the project from library to platform.

**When to revisit**: When `LocalBatchAdapter` via `SimulationBatch` port becomes the
bottleneck.
**Interface**: `SimulationBatch` port (defined above). Cloud adapters implement the same
protocol — no domain changes.

### Agent-Driven Pipeline

**Why deferred**: Conflicts with Replaceability Principle. Deterministic trigger rules (4.2)
cover the concrete use cases. An LLM-in-the-loop requires explicit justification of which
deterministic approaches were considered and why they fail.

**When to revisit**: If deterministic what-if triggers (4.2) prove insufficient for a
specific, documented use case.
**Interface**: The what-if engine (4.2) returns `list[RecommendedAction]`. A future
orchestrator (deterministic or otherwise) consumes these. No domain changes needed.

### ORDEM/MASTER Debris Population

**Why deferred**: Data access is the bottleneck, not code. NASA ORDEM 4.0 is distributed
as a standalone Fortran tool, not a library. ESA MASTER requires registration and has
redistribution restrictions. Need to verify data licensing before building adapters.

**When to revisit**: When data access is secured.
**Interface**: `DebrisPopulationSource` port (defined above). Sustainability score (3.1)
already has the `Optional[float]` field ready.

### Advanced Atmosphere Models (NRLMSISE-00, JB2008)

**Why deferred**: Current exponential model is adequate for lifetime estimation and
station-keeping budgets. NRLMSISE-00 adds ~1500 LOC of coefficient tables.
JB2008 requires real-time solar/geomagnetic indices.

**When to revisit**: When orbit determination residuals are dominated by drag modeling error.
**Interface**: `atmosphere.py` already uses a function-call pattern for density lookup.
Swapping the model is a localized change. `SpaceWeatherSource` port (defined above)
provides the indices advanced models need.

---

## Dependency Graph

```
Phase 1.1 (EKF + ForceModel) ──┐
Phase 1.2 (Incremental EKF) ───┤
Phase 1.3 (Pareto constraints) │
                                │
Phase 2.1 (Albedo) ────────────┤  (independent, uses ForceModel)
Phase 2.2 (Relativistic) ──────┤  (independent, uses ForceModel)
                                │
Phase 3.1 (Sustainability) ────┤  (uses existing modules)
Phase 3.2 (Self-Review) ───────┘── depends on 3.1
                                │
Phase 4.1 (NSGA-II) ───────────┤  (independent, uses 1.3 constraints)
Phase 4.2 (What-If) ───────────┘  (independent, uses SpaceWeatherSource port)
```

Phases 1, 2, and 4 are independent tracks. Phase 3.2 depends on 3.1.
All port definitions are created alongside the phase that first benefits from them.
