# Copyright (c) 2026 Jeroen Visser. All rights reserved.
# Licensed under the terms in COMMERCIAL-LICENSE.md.
# Free for personal, educational, and academic use.
# Commercial use requires a paid license — see COMMERCIAL-LICENSE.md.
"""Cross-run profile behavior history tracking tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path



def _load_compare_script_module():
    script_path = Path("scripts/run_gmat_mirror_compare.py").resolve()
    spec = importlib.util.spec_from_file_location("run_gmat_mirror_compare", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_profile_behavior_history_appends_runs(tmp_path: Path):
    module = _load_compare_script_module()
    annex = module._build_profile_behavior_annex()

    p1 = module._update_profile_behavior_history(tmp_path, "run-0001-test", annex)
    p2 = module._update_profile_behavior_history(tmp_path, "run-0002-test", annex)

    assert p1 == p2
    payload = json.loads(p1.read_text(encoding="utf-8"))
    assert len(payload["runs"]) == 2
    assert payload["runs"][0]["run_id"] == "run-0001-test"
    assert payload["runs"][1]["run_id"] == "run-0002-test"
