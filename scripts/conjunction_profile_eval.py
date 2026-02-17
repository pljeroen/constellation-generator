#!/usr/bin/env python3
# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""CLI for conjunction profile-pack evaluation."""
from __future__ import annotations

import argparse
import json

from humeris.domain.conjunction_profiles import evaluate_profiled_screening


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Evaluate conjunction risk under a profile pack")
    p.add_argument("--profile", required=True, choices=["conservative", "nominal", "aggressive"])
    p.add_argument("--miss-distance-m", required=True, type=float)
    p.add_argument("--base-pc", required=True, type=float)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = evaluate_profiled_screening(
        miss_distance_m=args.miss_distance_m,
        base_collision_probability=args.base_pc,
        profile_name=args.profile,
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
