# GMAT Mirror Parity Report

- Status: **PASS**
- Timestamp (UTC): `2026-02-17T00:39:01.220045+00:00`
- Humeris git: `e67a7fc-dirty` (commit `e67a7fc`, dirty=`dirty`)
- GMAT testsuite git: `f53e60b-dirty` (commit `f53e60b`, dirty=`dirty`)
- GMAT testsuite repo: `https://github.com/pljeroen/testsuite_gmat`
- GMAT run reference: `run-0009-f53e60b-clean`
- Replay bundle: `replay_bundle.json`
- Profile behavior history: `profile_behavior_history.json`

This is a reference-comparison report. It is intended as a learning and validation artifact, not a certification claim.

## Executive Summary
- Confidence: `0.86`
- Known limitations:
  - Sun-centric force model remains an approximation in current mirror.
  - External live-data dependencies can introduce run-to-run variance.
- Recommended next actions:
  - Promote Sun-centric residual budget checks to hard CI gate.
  - Capture deterministic replay bundle for each parity run.

## Case: `basic_leo_two_body`
- Case status: **PASS**

| Metric | GMAT | Humeris | Abs delta | Tolerance | Pass |
|---|---:|---:|---:|---:|:---:|
| `startSMA` | 7000 | 7000 | 9.094947e-13 | 5 | yes |
| `startECC` | 0.001 | 0.000999999999999 | 1.116728e-16 | 0.001 | yes |
| `endSMA` | 7000 | 7000.00000083 | 8.259276e-07 | 5 | yes |
| `endECC` | 0.00100000000001 | 0.00099999998181 | 1.819702e-11 | 0.001 | yes |
| `elapsedSecs` | 5400.00000031 | 5400 | 3.143214e-07 | 0.001 | yes |
| `conservation_behavior_match` | true | true |  |  | yes |

## Case: `advanced_j2_raan_drift`
- Case status: **PASS**

| Metric | GMAT | Humeris | Abs delta | Tolerance | Pass |
|---|---:|---:|---:|---:|:---:|
| `startRAAN` | 20 | 20 | 0 | 2 | yes |
| `startINC` | 97.8 | 97.8 | 0 | 0.2 | yes |
| `startECC` | 0.001 | 0.001 | 2.649790e-16 | 0.0005 | yes |
| `elapsedDays` | 7 | 7 | 0 | 1.000000e-06 | yes |
| `raanDriftDeg` | 6.80548074605 | 6.84304855745 | 0.0375678114005 | 2 | yes |
| `j2_regime_match` | true | true |  |  | yes |

## Case: `advanced_oumuamua_hyperbolic`
- Case status: **PASS**

| Metric | GMAT | Humeris | Abs delta | Tolerance | Pass |
|---|---:|---:|---:|---:|:---:|
| `start_ecc_gt_1` | true | true |  |  | yes |
| `end_ecc_gt_1` | true | true |  |  | yes |
| `rmag_changes_materially` | true | true |  |  | yes |
| `elapsed_days_120` | true | true |  |  | yes |

## Assumption Differences
- Current mirror uses Earth-mu propagation for hyperbolic regime parity.
- Dedicated Sun-centric force-model parity is tracked as an incremental extension.

## Residual Mismatch Budget
| Metric | Budget |
|---|---|
| `ecc` | `advisory` |
| `inc_deg` | `advisory` |
| `rmag_km` | `advisory` |
| `energy_sign` | `bounded` |

## Sun-centric Delta Table
| Metric | Delta |
|---|---:|
| `ecc` | `5861.7953631` |
| `inc_deg` | `96.319569357` |
| `rmag_km` | `1.045598e+07` |

## Conjunction Profile Behavior Annex
- Scenario input: miss_distance_m=1.200000e+04, base_collision_probability=2.000000e-05

| Profile | Version | Flagged | Pc Lower | Pc Nominal | Pc Upper |
|---|---|:---:|---:|---:|---:|
| `conservative` | `v1` | yes | 2.100000e-05 | 3.000000e-05 | 3.900000e-05 |
| `nominal` | `v1` | yes | 1.400000e-05 | 2.000000e-05 | 2.600000e-05 |
| `aggressive` | `v1` | no | 1.050000e-05 | 1.500000e-05 | 1.950000e-05 |

