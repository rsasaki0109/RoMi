#!/usr/bin/env python3
"""Fail CI when a policy regresses against recorded expert actions.

Re-runs the deterministic, offline policies (heuristic, bc_knn) on a committed
episode, evaluates them counterfactually against the recorded expert actions, and
compares the mean action error against a committed baseline. If any policy's
error grows beyond the baseline plus a tolerance, the gate exits non-zero so CI
fails.

This turns the counterfactual eval into a regression check: a change that makes a
policy (or the eval/runtime) drift away from expert behavior is caught before it
lands. It uses only the offline state policies, so it needs no torch or GPU.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parents[1]
POLICY = TOOLS / "vla_policy" / "romi_vla_policy.py"
EVAL = TOOLS / "policy_eval" / "romi_policy_eval.py"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True, type=Path, help="Committed episode JSONL.")
    parser.add_argument("--baseline", required=True, type=Path, help="Baseline thresholds JSON.")
    parser.add_argument("--bc-memory", type=Path, default=None, help="bc_knn memory JSON. Defaults to <episode dir>/bc_memory.json.")
    return parser.parse_args(argv)


def policy_specs(bc_memory: Path) -> list[dict[str, Any]]:
    return [
        {"policy_id": "romi_heuristic_goto", "name": "heuristic", "extra": ["--backend", "heuristic"]},
        {"policy_id": "romi_bc_knn", "name": "bc_knn", "extra": ["--backend", "bc_knn", "--bc-memory", str(bc_memory)]},
    ]


def measure(episode: Path, spec: dict[str, Any], tmp_dir: Path) -> float:
    policy_jsonl = tmp_dir / f"{spec['name']}.jsonl"
    eval_json = tmp_dir / f"{spec['name']}.eval.json"
    subprocess.run(
        [sys.executable, str(POLICY), "--input", str(episode), "--output", str(policy_jsonl), *spec["extra"]],
        check=True, capture_output=True,
    )
    subprocess.run(
        [sys.executable, str(EVAL), "--episode", str(episode), "--policy", str(policy_jsonl), "--json-output", str(eval_json)],
        check=True, capture_output=True,
    )
    report = json.loads(eval_json.read_text(encoding="utf-8"))
    return float(report["summary"]["mean_action_error_px"])


def run(args: argparse.Namespace) -> int:
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    tolerance = float(baseline.get("tolerance_px", 1.0))
    thresholds: dict[str, float] = baseline["max_mean_action_error_px"]
    bc_memory = args.bc_memory or (args.episode.parent / "bc_memory.json")

    regressions: list[str] = []
    rows: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for spec in policy_specs(bc_memory):
            name = spec["name"]
            if name not in thresholds:
                continue
            measured = measure(args.episode, spec, tmp_dir)
            limit = float(thresholds[name]) + tolerance
            status = "ok" if measured <= limit else "REGRESSED"
            rows.append(f"  {name:12s} mean={measured:7.3f}px  limit={limit:7.3f}px  {status}")
            if measured > limit:
                regressions.append(f"{name}: {measured:.3f}px > {limit:.3f}px")

    print("policy regression gate:")
    print("\n".join(rows))
    if regressions:
        print("FAIL: policy regression detected:", file=sys.stderr)
        for item in regressions:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print(f"PASS: no regression beyond {tolerance}px tolerance.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
