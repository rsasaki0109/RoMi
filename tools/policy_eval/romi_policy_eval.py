#!/usr/bin/env python3
"""Counterfactually evaluate proposed policy actions against recorded expert actions.

This reads a RoMi episode JSONL (containing ``expert.action`` recorded
demonstration samples) and a policy JSONL (containing ``policy.proposed_action``
proposals), aligns them by event time, and measures how far the policy's
proposed navigation goals are from the recorded expert goals - before any
actuator is touched.

Output is a structured JSON report plus a readable Markdown summary. Policy
authority stays ``proposed_only`` and actuator authority stays ``none``; this
tool only evaluates proposals, it never promotes them to commands.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.1.0"
REPORT_KIND = "romi.counterfactual_policy_eval"
SPARK = "▁▂▃▄▅▆▇█"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Counterfactually evaluate proposed actions vs recorded expert actions.",
    )
    parser.add_argument("--episode", required=True, type=Path, help="Episode JSONL with expert.action samples.")
    parser.add_argument("--policy", required=True, type=Path, help="Policy JSONL with policy.proposed_action samples.")
    parser.add_argument("--json-output", type=Path, default=None, help="Path for the JSON report.")
    parser.add_argument("--md-output", type=Path, default=None, help="Path for the Markdown report.")
    parser.add_argument(
        "--tolerance-px",
        type=float,
        default=20.0,
        help="Action error (pixels) considered agreement with the expert.",
    )
    parser.add_argument(
        "--match-tolerance-ns",
        type=int,
        default=1_000_000,
        help="Max event-time difference to pair a proposal with an expert action.",
    )
    return parser.parse_args(argv)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
    return events


def goal_from_expert(event: dict[str, Any]) -> dict[str, float] | None:
    payload = event.get("payload_summary")
    if not isinstance(payload, dict):
        return None
    values = payload.get("values")
    if not isinstance(values, dict):
        return None
    goal = values.get("goal_position")
    if not isinstance(goal, dict):
        return None
    return {"x": float(goal.get("x", 0.0)), "y": float(goal.get("y", 0.0))}


def goal_from_proposal(event: dict[str, Any]) -> dict[str, float] | None:
    payload = event.get("payload_summary")
    if not isinstance(payload, dict):
        return None
    actions = payload.get("proposed_actions")
    if not isinstance(actions, list):
        return None
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action_type") != "navigate_to_goal":
            continue
        values = action.get("values")
        if isinstance(values, dict) and isinstance(values.get("goal_position"), dict):
            goal = values["goal_position"]
            return {"x": float(goal.get("x", 0.0)), "y": float(goal.get("y", 0.0))}
    return None


def collect(events: list[dict[str, Any]], stream_id: str, extractor) -> list[tuple[int, dict[str, float]]]:
    out: list[tuple[int, dict[str, float]]] = []
    for event in events:
        if event.get("kind") != "stream_sample" or event.get("stream_id") != stream_id:
            continue
        goal = extractor(event)
        time_ns = event.get("event_time_ns")
        if goal is not None and isinstance(time_ns, int):
            out.append((time_ns, goal))
    out.sort(key=lambda item: item[0])
    return out


def latency_values(events: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for event in events:
        payload = event.get("payload_summary")
        if isinstance(payload, dict) and isinstance(payload.get("inference_latency_ms"), (int, float)):
            values.append(float(payload["inference_latency_ms"]))
    return values


def metadata(events: list[dict[str, Any]], key: str, default: Any = None) -> Any:
    for event in events:
        if key in event:
            return event[key]
    return default


def pair_by_time(
    expert: list[tuple[int, dict[str, float]]],
    proposals: list[tuple[int, dict[str, float]]],
    tolerance_ns: int,
) -> list[tuple[int, dict[str, float], dict[str, float]]]:
    """Pair each proposal with the nearest expert action within a time window."""
    paired: list[tuple[int, dict[str, float], dict[str, float]]] = []
    j = 0
    for time_ns, proposed_goal in proposals:
        while j + 1 < len(expert) and abs(expert[j + 1][0] - time_ns) <= abs(expert[j][0] - time_ns):
            j += 1
        if not expert:
            break
        exp_time, exp_goal = expert[j]
        if abs(exp_time - time_ns) <= tolerance_ns:
            paired.append((time_ns, exp_goal, proposed_goal))
    return paired


def l2(a: dict[str, float], b: dict[str, float]) -> float:
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5


def sparkline(values: list[float], width: int = 60) -> str:
    if not values:
        return ""
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values
    lo, hi = min(sampled), max(sampled)
    span = hi - lo or 1.0
    return "".join(SPARK[min(len(SPARK) - 1, int((v - lo) / span * (len(SPARK) - 1)))] for v in sampled)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    episode_events = load_jsonl(args.episode)
    policy_events = load_jsonl(args.policy)

    expert = collect(episode_events, "expert.action", goal_from_expert)
    proposals = collect(policy_events, "policy.proposed_action", goal_from_proposal)
    if not expert:
        raise ValueError("No expert.action samples found in the episode JSONL.")
    if not proposals:
        raise ValueError("No policy.proposed_action samples found in the policy JSONL.")

    paired = pair_by_time(expert, proposals, args.match_tolerance_ns)
    if not paired:
        raise ValueError("No proposals could be time-aligned with expert actions.")

    samples = []
    errors = []
    for time_ns, exp_goal, proposed_goal in paired:
        error_px = l2(exp_goal, proposed_goal)
        errors.append(error_px)
        samples.append(
            {
                "time_sec": round(time_ns / 1_000_000_000, 4),
                "expert_goal": {"x": round(exp_goal["x"], 3), "y": round(exp_goal["y"], 3)},
                "proposed_goal": {"x": round(proposed_goal["x"], 3), "y": round(proposed_goal["y"], 3)},
                "error_px": round(error_px, 4),
                "within_tolerance": error_px <= args.tolerance_px,
            }
        )

    within = sum(1 for e in errors if e <= args.tolerance_px)
    max_index = max(range(len(errors)), key=lambda i: errors[i])
    latencies = latency_values(policy_events)

    episode_id = metadata(episode_events, "episode_id", "unknown_episode")
    dataset = metadata(episode_events, "dataset")
    policy_id = metadata(policy_events, "policy_id", "unknown_policy")
    backend = metadata(policy_events, "backend", "unknown")

    return {
        "schema_version": SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "episode_id": episode_id,
        "dataset": dataset,
        "policy_id": policy_id,
        "backend": backend,
        "clock_domain": "episode_time",
        "reference": "recorded_expert_action",
        "action_space": "navigate_to_goal_2d_pixel",
        "tolerance_px": args.tolerance_px,
        "matched_steps": len(paired),
        "expert_steps": len(expert),
        "proposal_steps": len(proposals),
        "summary": {
            "mean_action_error_px": round(statistics.fmean(errors), 4),
            "median_action_error_px": round(statistics.median(errors), 4),
            "p95_action_error_px": round(sorted(errors)[min(len(errors) - 1, int(0.95 * len(errors)))], 4),
            "max_action_error_px": round(errors[max_index], 4),
            "agreement_rate_within_tolerance": round(within / len(errors), 4),
            "max_divergence": {
                "time_sec": samples[max_index]["time_sec"],
                "error_px": round(errors[max_index], 4),
            },
            "mean_inference_latency_ms": round(statistics.fmean(latencies), 6) if latencies else None,
        },
        "safety_boundary": {
            "policy_authority": "proposed_only",
            "actuator_authority": "none",
            "command_stream_emitted": False,
            "blocked_reason": "proposal_not_actuator_authority",
        },
        "samples": samples,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    errors = [sample["error_px"] for sample in report["samples"]]
    spark = sparkline(errors)
    agreement_pct = round(s["agreement_rate_within_tolerance"] * 100, 1)
    lines = [
        "# RoMi Counterfactual Policy Evaluation",
        "",
        f"**Policy `{report['policy_id']}` (backend: `{report['backend']}`) vs recorded expert "
        f"actions** on `{report['dataset']}` episode `{report['episode_id']}`.",
        "",
        "> Replayed the episode, ran the policy, and measured how far its proposed "
        "navigation goals are from the recorded expert demonstration - before any actuator "
        "is touched.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Matched steps | {report['matched_steps']} |",
        f"| Mean action error | {s['mean_action_error_px']} px |",
        f"| Median action error | {s['median_action_error_px']} px |",
        f"| P95 action error | {s['p95_action_error_px']} px |",
        f"| Max action error | {s['max_action_error_px']} px (t={s['max_divergence']['time_sec']}s) |",
        f"| Agreement within {report['tolerance_px']} px | {agreement_pct}% |",
        f"| Mean inference latency | {s['mean_inference_latency_ms']} ms |",
        "",
        "## Action error over replay",
        "",
        f"```\n{spark}\n```",
        f"_(left = episode start, right = episode end; error in pixels vs expert goal)_",
        "",
        "## Safety boundary",
        "",
        f"- policy_authority: `{report['safety_boundary']['policy_authority']}`",
        f"- actuator_authority: `{report['safety_boundary']['actuator_authority']}`",
        f"- command_stream_emitted: `{str(report['safety_boundary']['command_stream_emitted']).lower()}`",
        "",
        "The policy only proposes. Promoting a proposal to an actuator command requires an "
        "external supervisor; this evaluation never does so.",
        "",
        f"_Generated by `tools/policy_eval/romi_policy_eval.py` ({report['report_kind']})._",
    ]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    report = build_report(args)
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json_text, encoding="utf-8")
    md_text = render_markdown(report)
    if args.md_output is not None:
        args.md_output.parent.mkdir(parents=True, exist_ok=True)
        args.md_output.write_text(md_text, encoding="utf-8")

    if args.json_output is None and args.md_output is None:
        sys.stdout.write(md_text)

    s = report["summary"]
    print(
        f"eval: {report['policy_id']} mean={s['mean_action_error_px']}px "
        f"agreement={round(s['agreement_rate_within_tolerance'] * 100, 1)}% "
        f"over {report['matched_steps']} steps",
        file=sys.stderr,
    )
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
