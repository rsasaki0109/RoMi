#!/usr/bin/env python3
"""Contract checks for the LeRobot VLA counterfactual evaluation example.

Runs fully offline against committed sample artifacts. It:

1. Validates the committed episode stream samples against the core stream
   sample schema and the policy proposals against the policy IO schema.
2. Validates the committed evaluation report against the policy eval schema.
3. Re-runs the heuristic policy and evaluation from the committed episode JSONL
   and asserts the deterministic results match the committed report.
4. Asserts the policy/actuator authority boundary stays explicit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import jsonschema


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def deterministic_view(report: dict[str, Any]) -> dict[str, Any]:
    """Drop wall-clock/latency fields that legitimately vary between runs."""
    view = json.loads(json.dumps(report))
    view["summary"].pop("mean_inference_latency_ms", None)
    return view


def check(repo_root: Path) -> None:
    example = repo_root / "examples" / "lerobot_vla_eval"
    sample = example / "sample_output"
    schemas = repo_root / "schemas"

    core_schema = load_json(schemas / "core" / "stream_sample.schema.json")
    policy_io_schema = load_json(schemas / "ml" / "policy_io.schema.json")
    eval_schema = load_json(schemas / "ml" / "policy_eval.schema.json")

    episode = load_jsonl(sample / "episode.jsonl")
    policy = load_jsonl(sample / "policy.heuristic.jsonl")
    report = load_json(sample / "policy_eval.json")

    # 1. envelope conformance
    stream_samples = [e for e in episode if e.get("kind") == "stream_sample"]
    require(len(stream_samples) > 0, "episode has no stream samples")
    for event in stream_samples:
        jsonschema.validate(event, core_schema)

    proposals = [
        e for e in policy
        if e.get("kind") == "stream_sample" and e.get("stream_id") == "policy.proposed_action"
    ]
    require(len(proposals) > 0, "policy has no proposed_action samples")
    for event in proposals:
        jsonschema.validate(event["payload_summary"], policy_io_schema)
        require(
            event["payload_summary"]["safety_boundary"]["actuator_authority"] == "none",
            "proposal must not claim actuator authority",
        )

    # 2. report schema conformance
    jsonschema.validate(report, eval_schema)
    require(
        report["safety_boundary"]["actuator_authority"] == "none"
        and report["safety_boundary"]["command_stream_emitted"] is False
        and report["safety_boundary"]["policy_authority"] == "proposed_only",
        "eval report safety boundary must stay proposed_only / actuator none",
    )

    # 3. deterministic reproduction from the committed episode
    vla = repo_root / "tools" / "vla_policy" / "romi_vla_policy.py"
    eval_tool = repo_root / "tools" / "policy_eval" / "romi_policy_eval.py"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        repro_policy = tmp_dir / "policy.jsonl"
        repro_report = tmp_dir / "eval.json"
        subprocess.run(
            [sys.executable, str(vla), "--input", str(sample / "episode.jsonl"),
             "--backend", "heuristic", "--output", str(repro_policy)],
            check=True, capture_output=True,
        )
        subprocess.run(
            [sys.executable, str(eval_tool), "--episode", str(sample / "episode.jsonl"),
             "--policy", str(repro_policy), "--json-output", str(repro_report)],
            check=True, capture_output=True,
        )
        reproduced = load_json(repro_report)
        require(
            deterministic_view(reproduced) == deterministic_view(report),
            "re-running the heuristic policy + eval did not reproduce the committed report",
        )

    print(
        f"OK lerobot_vla_eval: {len(stream_samples)} stream samples, "
        f"{len(proposals)} proposals, {report['matched_steps']} matched steps, "
        f"mean={report['summary']['mean_action_error_px']}px "
        f"agreement={round(report['summary']['agreement_rate_within_tolerance'] * 100, 1)}%"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    check(args.repo_root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
