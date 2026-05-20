#!/usr/bin/env python3
"""Emit mock non-authoritative policy actions from RoMi JSONL samples."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"
POLICY_SCHEMA_ID = "romi.ml.policy_io/0.1.0"
DIAGNOSTIC_SCHEMA_ID = "romi.core.diagnostic_event/0.1.0"


class JsonlWriter:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        if path is None:
            self.file = sys.stdout
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.file = path.open("w", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        self.file.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
        self.file.write("\n")
        self.file.flush()

    def close(self) -> None:
        if self.path is not None:
            self.file.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a RoMi mock policy over JSONL samples")
    parser.add_argument("--input", required=True, type=Path, help="Input bridge or replay JSONL.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output policy JSONL path. Defaults to stdout.",
    )
    parser.add_argument(
        "--policy-id",
        default="mock_nav_manip_policy",
        help="Policy identifier.",
    )
    parser.add_argument(
        "--trigger-stream",
        action="append",
        default=[],
        help="Stream that triggers policy output. Can be repeated. Defaults to task.goal.",
    )
    parser.add_argument(
        "--required-stream",
        action="append",
        default=[],
        help="Stream required before emitting actions. Can be repeated. Defaults to task.goal.",
    )
    parser.add_argument(
        "--freshness-max-age-ms",
        type=float,
        default=500.0,
        help="Maximum input age considered fresh.",
    )
    parser.add_argument(
        "--max-actions",
        type=int,
        default=None,
        help="Maximum proposed action samples to emit.",
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


def event_time_ns(event: dict[str, Any]) -> int:
    value = event.get("event_time_ns")
    if isinstance(value, int):
        return value
    replay = event.get("replay")
    if isinstance(replay, dict) and isinstance(replay.get("original_event_time_ns"), int):
        return replay["original_event_time_ns"]
    return time.time_ns()


def clock_domain(event: dict[str, Any]) -> str:
    value = event.get("clock_domain")
    if isinstance(value, str):
        return value
    return "unknown"


def position_from_goal(event: dict[str, Any]) -> dict[str, float] | None:
    payload = event.get("payload_summary")
    if not isinstance(payload, dict):
        return None
    position = payload.get("position")
    if not isinstance(position, dict):
        return None
    try:
        return {
            "x": float(position.get("x", 0.0)),
            "y": float(position.get("y", 0.0)),
            "z": float(position.get("z", 0.0)),
        }
    except (TypeError, ValueError):
        return None


def freshness_report(
    *,
    latest: dict[str, dict[str, Any]],
    current_time_ns: int,
    required_streams: list[str],
    freshness_max_age_ms: float,
) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for stream_id, sample in sorted(latest.items()):
        sample_time_ns = event_time_ns(sample)
        age_ms = (current_time_ns - sample_time_ns) / 1_000_000.0
        if age_ms < 0:
            status = "future"
        elif age_ms <= freshness_max_age_ms:
            status = "ok"
        else:
            status = "stale"
        report[stream_id] = {
            "age_ms": age_ms,
            "status": status,
            "required": stream_id in required_streams,
        }
    for stream_id in required_streams:
        if stream_id not in report:
            report[stream_id] = {
                "age_ms": None,
                "status": "missing",
                "required": True,
            }
    return report


def required_inputs_ready(freshness: dict[str, dict[str, Any]], required_streams: list[str]) -> bool:
    for stream_id in required_streams:
        status = freshness.get(stream_id, {}).get("status")
        if status not in {"ok", "future"}:
            return False
    return True


def diagnostic_event(
    *,
    policy_id: str,
    severity: str,
    message: str,
    attributes: dict[str, Any],
    category: str = "policy",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": DIAGNOSTIC_SCHEMA_ID,
        "kind": "diagnostic_event",
        "event_id": f"policy_{category}_{time.time_ns()}",
        "time": {
            "event_time_ns": time.time_ns(),
            "clock_domain": "wall_time",
        },
        "severity": severity,
        "source": policy_id,
        "category": category,
        "message": message,
        "attributes": attributes,
    }


def proposed_actions(trigger: dict[str, Any]) -> list[dict[str, Any]]:
    frame_id = trigger.get("frame_id") or "map"
    goal_position = position_from_goal(trigger)
    base_values: dict[str, Any] = {
        "frame_id": frame_id,
        "mode": "demo_navigation_goal",
    }
    if goal_position is not None:
        base_values["goal_position"] = goal_position

    return [
        {
            "target": "base",
            "action_type": "navigate_to_goal",
            "values": base_values,
            "authority": "proposed_only",
        },
        {
            "target": "end_effector",
            "action_type": "hold_ready_pose",
            "values": {
                "frame_id": "base_link",
                "reason": "mock_navigation_manipulation_demo",
            },
            "authority": "proposed_only",
        },
        {
            "target": "gripper",
            "action_type": "hold_open",
            "values": {
                "reason": "mock_policy_does_not_command_actuators",
            },
            "authority": "proposed_only",
        },
    ]


def policy_sample(
    *,
    policy_id: str,
    trigger: dict[str, Any],
    latest: dict[str, dict[str, Any]],
    required_streams: list[str],
    freshness_max_age_ms: float,
    sequence_index: int,
) -> dict[str, Any]:
    inference_start_ns = time.time_ns()
    current_time_ns = event_time_ns(trigger)
    freshness = freshness_report(
        latest=latest,
        current_time_ns=current_time_ns,
        required_streams=required_streams,
        freshness_max_age_ms=freshness_max_age_ms,
    )
    actions = proposed_actions(trigger)
    inference_end_ns = time.time_ns()
    inference_latency_ms = (inference_end_ns - inference_start_ns) / 1_000_000.0

    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "proposed_action",
        "policy_id": policy_id,
        "time": {
            "event_time_ns": current_time_ns,
            "clock_domain": clock_domain(trigger),
        },
        "input_streams": sorted(latest.keys()),
        "freshness": freshness,
        "proposed_actions": actions,
        "inference_latency_ms": inference_latency_ms,
        "metadata": {
            "trigger_stream": trigger.get("stream_id"),
            "authority": "proposed_only",
            "sequence_index": sequence_index,
        },
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": POLICY_SCHEMA_ID,
        "kind": "stream_sample",
        "stream_id": "policy.proposed_action",
        "semantic_type": "command",
        "source_system": "romi",
        "source_topic": None,
        "source_message_type": "romi/ml/PolicyProposedAction",
        "event_time_ns": current_time_ns,
        "policy_emit_wall_time_ns": inference_end_ns,
        "clock_domain": clock_domain(trigger),
        "frame_id": trigger.get("frame_id"),
        "payload_summary": payload,
        "metadata": {
            "policy_id": policy_id,
            "trigger_stream": trigger.get("stream_id"),
            "authority": "proposed_only",
            "sequence_index": sequence_index,
        },
    }


def run_policy(args: argparse.Namespace) -> int:
    if not args.input.exists():
        raise FileNotFoundError(f"Input JSONL does not exist: {args.input}")

    trigger_streams = args.trigger_stream or ["task.goal"]
    required_streams = args.required_stream or ["task.goal"]
    trigger_set = set(trigger_streams)

    events = load_jsonl(args.input)
    writer = JsonlWriter(args.output)
    latest: dict[str, dict[str, Any]] = {}
    emitted = 0

    try:
        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "policy_start",
                "policy_id": args.policy_id,
                "input": str(args.input),
                "trigger_streams": trigger_streams,
                "required_streams": required_streams,
                "freshness_max_age_ms": args.freshness_max_age_ms,
                "wall_time_ns": time.time_ns(),
            }
        )

        for event in events:
            if event.get("kind") != "stream_sample":
                continue

            stream_id = event.get("stream_id")
            if not isinstance(stream_id, str):
                continue

            latest[stream_id] = event
            if stream_id not in trigger_set:
                continue

            now_ns = event_time_ns(event)
            freshness = freshness_report(
                latest=latest,
                current_time_ns=now_ns,
                required_streams=required_streams,
                freshness_max_age_ms=args.freshness_max_age_ms,
            )
            if not required_inputs_ready(freshness, required_streams):
                writer.write(
                    diagnostic_event(
                        policy_id=args.policy_id,
                        severity="warning",
                        message="Skipping policy output because required inputs are missing or stale.",
                        attributes={
                            "trigger_stream": stream_id,
                            "freshness": freshness,
                        },
                    )
                )
                continue

            writer.write(
                policy_sample(
                    policy_id=args.policy_id,
                    trigger=event,
                    latest=latest,
                    required_streams=required_streams,
                    freshness_max_age_ms=args.freshness_max_age_ms,
                    sequence_index=emitted,
                )
            )
            emitted += 1
            if args.max_actions is not None and emitted >= args.max_actions:
                break

        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "policy_stop",
                "policy_id": args.policy_id,
                "emitted_actions": emitted,
                "observed_streams": sorted(latest.keys()),
                "wall_time_ns": time.time_ns(),
            }
        )
    finally:
        writer.close()

    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run_policy(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
