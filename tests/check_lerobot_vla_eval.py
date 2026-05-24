#!/usr/bin/env python3
"""Contract checks for the LeRobot VLA counterfactual evaluation example.

Runs fully offline against committed sample artifacts. It:

1. Validates the committed episode stream samples against the core stream
   sample schema and the policy proposals against the policy IO schema.
2. Validates the committed evaluation reports against the policy eval schema.
3. Re-runs each policy backend and evaluation from the committed episode JSONL
   and asserts the deterministic results match the committed reports.
4. Asserts the policy/actuator authority boundary stays explicit.
5. Asserts the learned bc_knn policy tracks the expert better than the naive
   heuristic baseline.
"""

from __future__ import annotations

import argparse
import importlib.util
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

    # 1. episode envelope conformance
    stream_samples = [e for e in episode if e.get("kind") == "stream_sample"]
    require(len(stream_samples) > 0, "episode has no stream samples")
    for event in stream_samples:
        jsonschema.validate(event, core_schema)

    vla = repo_root / "tools" / "vla_policy" / "romi_vla_policy.py"
    eval_tool = repo_root / "tools" / "policy_eval" / "romi_policy_eval.py"

    cases = [
        {
            "name": "heuristic",
            "policy": "policy.heuristic.jsonl",
            "report": "policy_eval.json",
            "extra": ["--backend", "heuristic"],
        },
        {
            "name": "bc_knn",
            "policy": "policy.bc_knn.jsonl",
            "report": "policy_eval.bc_knn.json",
            "extra": ["--backend", "bc_knn", "--bc-memory", str(sample / "bc_memory.json"), "--bc-k", "5"],
        },
        {
            "name": "neural_bc",
            "policy": "policy.neural_bc.jsonl",
            "report": "policy_eval.neural_bc.json",
            "extra": ["--backend", "neural_bc", "--neural-weights", str(sample / "bc_mlp_weights.json"), "--device", "cpu"],
            "needs_torch": True,
        },
    ]

    torch_available = importlib.util.find_spec("torch") is not None

    mean_error: dict[str, float] = {}
    for case in cases:
        policy = load_jsonl(sample / case["policy"])
        report = load_json(sample / case["report"])

        proposals = [
            e for e in policy
            if e.get("kind") == "stream_sample" and e.get("stream_id") == "policy.proposed_action"
        ]
        require(len(proposals) > 0, f"{case['name']}: no proposed_action samples")
        for event in proposals:
            jsonschema.validate(event["payload_summary"], policy_io_schema)
            require(
                event["payload_summary"]["safety_boundary"]["actuator_authority"] == "none",
                f"{case['name']}: proposal must not claim actuator authority",
            )

        jsonschema.validate(report, eval_schema)
        require(
            report["safety_boundary"]["actuator_authority"] == "none"
            and report["safety_boundary"]["command_stream_emitted"] is False
            and report["safety_boundary"]["policy_authority"] == "proposed_only",
            f"{case['name']}: report safety boundary must stay proposed_only / actuator none",
        )

        mean_error[case["name"]] = report["summary"]["mean_action_error_px"]

        # deterministic reproduction (neural_bc needs torch; skip cleanly without it)
        if case.get("needs_torch") and not torch_available:
            print(f"  (skip {case['name']} reproduction: torch not installed)")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            repro_policy = tmp_dir / "policy.jsonl"
            repro_report = tmp_dir / "eval.json"
            subprocess.run(
                [sys.executable, str(vla), "--input", str(sample / "episode.jsonl"),
                 "--output", str(repro_policy), *case["extra"]],
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
                f"{case['name']}: re-running policy + eval did not reproduce the committed report",
            )

    # 5. the learned policies should track the expert better than the naive baseline
    for learned in ("bc_knn", "neural_bc"):
        require(
            mean_error[learned] < mean_error["heuristic"],
            f"{learned} mean error ({mean_error[learned]}) should beat heuristic ({mean_error['heuristic']})",
        )

    # 6. dataset-scale leaderboard: schema, safety, and ranking invariants
    leaderboard_schema = load_json(schemas / "ml" / "policy_eval_leaderboard.schema.json")
    leaderboard = load_json(sample / "leaderboard.json")
    jsonschema.validate(leaderboard, leaderboard_schema)
    require(
        leaderboard["safety_boundary"]["actuator_authority"] == "none"
        and leaderboard["safety_boundary"]["command_stream_emitted"] is False,
        "leaderboard safety boundary must stay actuator none / no command stream",
    )
    ranked = leaderboard["leaderboard"]
    require(
        ranked == sorted(ranked, key=lambda e: e["mean_action_error_px"]),
        "leaderboard entries must be sorted by mean action error",
    )
    require(
        leaderboard["best_policy"] == ranked[0]["policy_id"] == "neural_bc",
        "neural_bc should top the held-out leaderboard",
    )
    require(
        {"heuristic", "bc_knn", "neural_bc"} <= {e["policy_id"] for e in ranked},
        "leaderboard should rank all three policies",
    )

    # 7. MCAP export round-trips to valid Foxglove-schema channels
    from mcap.reader import make_reader

    exporter = repo_root / "tools" / "mcap_export" / "romi_mcap_export.py"
    with tempfile.TemporaryDirectory() as tmp:
        out_mcap = Path(tmp) / "episode.mcap"
        subprocess.run(
            [sys.executable, str(exporter), "--episode", str(sample / "episode.jsonl"),
             "--policy", str(sample / "policy.bc_knn.jsonl"), "--output", str(out_mcap)],
            check=True, capture_output=True,
        )
        with out_mcap.open("rb") as handle:
            reader = make_reader(handle)
            summary = reader.get_summary()
            topics = {channel.topic for channel in summary.channels.values()}
            schema_names = {schema.name for schema in summary.schemas.values()}
        require(
            {"/robot/base/pose", "/expert/goal", "/policy/proposed_goal"} <= topics,
            f"MCAP export missing expected channels, got {topics}",
        )
        require(
            "foxglove.PoseInFrame" in schema_names,
            f"MCAP export missing foxglove.PoseInFrame schema, got {schema_names}",
        )
        require(summary.statistics.message_count > 0, "MCAP export has no messages")

    print(
        "OK lerobot_vla_eval: "
        f"{len(stream_samples)} stream samples; ep0 mean error "
        f"heuristic={mean_error['heuristic']}px > bc_knn={mean_error['bc_knn']}px > "
        f"neural_bc={mean_error['neural_bc']}px; "
        f"leaderboard best={leaderboard['best_policy']} over "
        f"{len(leaderboard['held_out_episodes'])} held-out episodes; "
        "MCAP export valid (foxglove.PoseInFrame)"
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
