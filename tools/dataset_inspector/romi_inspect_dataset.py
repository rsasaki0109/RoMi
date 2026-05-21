#!/usr/bin/env python3
"""Create a dataset-style inspection report for a prototype RoMi episode."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"
PAYLOAD_SCHEMA_IDS = {
    "romi.robotics.ImageSummary": "https://romi.dev/schemas/robotics/image_summary.schema.json",
    "romi.robotics.CameraInfoSummary": "https://romi.dev/schemas/robotics/camera_info_summary.schema.json",
    "romi.robotics.JointStateSummary": "https://romi.dev/schemas/robotics/joint_state_summary.schema.json",
    "romi.robotics.OdometrySummary": "https://romi.dev/schemas/robotics/odometry_summary.schema.json",
    "romi.robotics.TransformTreeSummary": "https://romi.dev/schemas/robotics/transform_tree_summary.schema.json",
    "romi.robotics.PoseGoalSummary": "https://romi.dev/schemas/robotics/task_goal_summary.schema.json",
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a RoMi prototype episode")
    parser.add_argument("--episode", required=True, type=Path, help="Episode directory.")
    parser.add_argument(
        "--policy-events",
        type=Path,
        default=None,
        help="Optional policy output JSONL.",
    )
    parser.add_argument("--output-dir", required=True, type=Path, help="Output report directory.")
    parser.add_argument(
        "--window-ms",
        type=float,
        default=250.0,
        help="Observation window half-width around target time.",
    )
    parser.add_argument(
        "--target-time-ns",
        type=int,
        default=None,
        help="Optional target event time for synchronized window.",
    )
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def event_time_ns(event: dict[str, Any]) -> int | None:
    value = event.get("event_time_ns")
    if isinstance(value, int):
        return value
    replay = event.get("replay")
    if isinstance(replay, dict) and isinstance(replay.get("original_event_time_ns"), int):
        return replay["original_event_time_ns"]
    payload = event.get("payload_summary")
    if isinstance(payload, dict):
        payload_time = payload.get("time")
        if isinstance(payload_time, dict) and isinstance(payload_time.get("event_time_ns"), int):
            return payload_time["event_time_ns"]
    return None


def stream_samples(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event.get("kind") == "stream_sample"]


def policy_samples(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in stream_samples(events)
        if event.get("stream_id") == "policy.proposed_action"
    ]


def choose_target_time(
    *,
    episode: dict[str, Any],
    episode_samples: list[dict[str, Any]],
    policy_events: list[dict[str, Any]],
    requested_target_time_ns: int | None,
) -> int:
    if requested_target_time_ns is not None:
        return requested_target_time_ns

    policy = policy_samples(policy_events)
    if policy:
        policy_time = event_time_ns(policy[0])
        if policy_time is not None:
            return policy_time

    if episode_samples:
        sample_time = event_time_ns(episode_samples[0])
        if sample_time is not None:
            return sample_time

    return int(episode.get("clock", {}).get("start_time_ns") or 0)


def summarize_streams(streams_json: dict[str, Any]) -> list[dict[str, Any]]:
    summaries = []
    for stream in streams_json.get("streams", []):
        summaries.append(
            {
                "stream_id": stream.get("stream_id"),
                "semantic_type": stream.get("semantic_type"),
                "source_topic": stream.get("source_topic"),
                "source_message_type": stream.get("source_message_type"),
                "message_count": stream.get("message_count", 0),
                "clock_domain": stream.get("clock_domain"),
                "frame_ids": stream.get("frame_ids", []),
                "first_event_time_ns": stream.get("first_event_time_ns"),
                "last_event_time_ns": stream.get("last_event_time_ns"),
            }
        )
    return summaries


def sample_for_window(
    *,
    samples: list[dict[str, Any]],
    stream_id: str,
    target_time_ns: int,
    window_ns: int,
) -> dict[str, Any] | None:
    candidates = [sample for sample in samples if sample.get("stream_id") == stream_id]
    best: dict[str, Any] | None = None
    best_delta: int | None = None
    for sample in candidates:
        sample_time = event_time_ns(sample)
        if sample_time is None:
            continue
        delta = abs(sample_time - target_time_ns)
        if delta > window_ns:
            continue
        if best_delta is None or delta < best_delta:
            best = sample
            best_delta = delta
    return best


def payload_schema_id(source_message_type: Any) -> str | None:
    if not isinstance(source_message_type, str):
        return None
    return PAYLOAD_SCHEMA_IDS.get(source_message_type)


def build_observation_window(
    *,
    samples: list[dict[str, Any]],
    stream_summaries: list[dict[str, Any]],
    target_time_ns: int,
    window_ms: float,
) -> dict[str, Any]:
    window_ns = int(window_ms * 1_000_000)
    window_start_time_ns = max(0, target_time_ns - window_ns)
    window_end_time_ns = target_time_ns + window_ns
    entries = []
    for stream in stream_summaries:
        stream_id = stream.get("stream_id")
        if not isinstance(stream_id, str):
            continue
        source_message_type = stream.get("source_message_type")
        sample = sample_for_window(
            samples=samples,
            stream_id=stream_id,
            target_time_ns=target_time_ns,
            window_ns=window_ns,
        )
        if sample is None:
            entries.append(
                {
                    "stream_id": stream_id,
                    "semantic_type": stream.get("semantic_type"),
                    "source_topic": stream.get("source_topic"),
                    "source_message_type": source_message_type,
                    "payload_schema_id": payload_schema_id(source_message_type),
                    "status": "missing_in_window",
                    "delta_ms": None,
                    "delta_abs_ms": None,
                    "event_time_ns": None,
                    "frame_id": None,
                    "sample_index": None,
                    "payload_summary": None,
                }
            )
            continue
        sample_time = event_time_ns(sample)
        delta_ms = (
            (sample_time - target_time_ns) / 1_000_000.0
            if sample_time is not None
            else None
        )
        entries.append(
            {
                "stream_id": stream_id,
                "semantic_type": sample.get("semantic_type") or stream.get("semantic_type"),
                "source_topic": sample.get("source_topic", stream.get("source_topic")),
                "source_message_type": sample.get("source_message_type") or source_message_type,
                "payload_schema_id": payload_schema_id(sample.get("source_message_type") or source_message_type),
                "status": "ok",
                "delta_ms": delta_ms,
                "delta_abs_ms": abs(delta_ms) if delta_ms is not None else None,
                "event_time_ns": sample_time,
                "frame_id": sample.get("frame_id"),
                "sample_index": (sample.get("metadata") or {}).get("sample_index"),
                "payload_summary": sample.get("payload_summary"),
            }
        )

    available_stream_count = sum(1 for entry in entries if entry["status"] == "ok")
    return {
        "target_time_ns": target_time_ns,
        "window_start_time_ns": window_start_time_ns,
        "window_end_time_ns": window_end_time_ns,
        "window_ms": window_ms,
        "required_stream_count": len(entries),
        "available_stream_count": available_stream_count,
        "missing_stream_count": len(entries) - available_stream_count,
        "streams": entries,
    }


def summarize_policy(policy_events: list[dict[str, Any]]) -> dict[str, Any]:
    samples = policy_samples(policy_events)
    actions = []
    freshness_status: dict[str, int] = {}
    for sample in samples:
        payload = sample.get("payload_summary")
        if not isinstance(payload, dict):
            continue
        for stream_id, freshness in (payload.get("freshness") or {}).items():
            if not isinstance(freshness, dict):
                continue
            status = str(freshness.get("status", "unknown"))
            key = f"{stream_id}:{status}"
            freshness_status[key] = freshness_status.get(key, 0) + 1
        actions.append(
            {
                "event_time_ns": event_time_ns(sample),
                "inference_latency_ms": payload.get("inference_latency_ms"),
                "authority": payload.get("metadata", {}).get("authority"),
                "proposed_action_count": len(payload.get("proposed_actions") or []),
                "proposed_actions": payload.get("proposed_actions") or [],
            }
        )
    return {
        "sample_count": len(samples),
        "freshness_status": freshness_status,
        "actions": actions[:20],
    }


def build_report(
    *,
    episode_dir: Path,
    episode: dict[str, Any],
    streams_json: dict[str, Any],
    diagnostics: dict[str, Any],
    episode_samples: list[dict[str, Any]],
    policy_events: list[dict[str, Any]],
    target_time_ns: int,
    window_ms: float,
) -> dict[str, Any]:
    stream_summaries = summarize_streams(streams_json)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "dataset_inspection_report",
        "generated_at_unix_ns": time.time_ns(),
        "episode_dir": str(episode_dir),
        "episode": {
            "episode_id": episode.get("episode_id"),
            "scenario": episode.get("scenario"),
            "clock": episode.get("clock"),
            "runtime_graph": episode.get("runtime_graph"),
        },
        "streams": stream_summaries,
        "diagnostics": {
            "event_count": diagnostics.get("event_count", 0),
            "by_severity": diagnostics.get("by_severity", {}),
            "by_category": diagnostics.get("by_category", {}),
        },
        "policy": summarize_policy(policy_events),
        "observation_window": build_observation_window(
            samples=episode_samples,
            stream_summaries=stream_summaries,
            target_time_ns=target_time_ns,
            window_ms=window_ms,
        ),
    }


def json_dump(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_ns(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    return ""


def build_markdown(report: dict[str, Any]) -> str:
    episode = report["episode"]
    scenario = episode.get("scenario") or {}
    clock = episode.get("clock") or {}
    diagnostics = report["diagnostics"]
    policy = report["policy"]
    window = report["observation_window"]

    lines = [
        f"# Dataset Report: {episode.get('episode_id')}",
        "",
        "Prototype RoMi dataset inspection report.",
        "",
        "## Episode",
        "",
        f"- Scenario: `{scenario.get('name')}`",
        f"- Mode: `{scenario.get('mode')}`",
        f"- World: `{scenario.get('world_id')}`",
        f"- Robot: `{scenario.get('robot_id')}`",
        f"- Clock domain: `{clock.get('clock_domain')}`",
        f"- Start time ns: `{format_ns(clock.get('start_time_ns'))}`",
        f"- End time ns: `{format_ns(clock.get('end_time_ns'))}`",
        "",
        "## Streams",
        "",
        "| Stream | Samples | Type | Frames |",
        "| --- | ---: | --- | --- |",
    ]

    for stream in report["streams"]:
        frames = ", ".join(stream.get("frame_ids") or [])
        lines.append(
            "| {stream_id} | {count} | {message_type} | {frames} |".format(
                stream_id=stream.get("stream_id") or "",
                count=stream.get("message_count") or 0,
                message_type=stream.get("source_message_type") or "",
                frames=frames,
            )
        )

    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            f"- Events: `{diagnostics.get('event_count', 0)}`",
            f"- By severity: `{diagnostics.get('by_severity', {})}`",
            f"- By category: `{diagnostics.get('by_category', {})}`",
            "",
            "## Policy",
            "",
            f"- Proposed action samples: `{policy.get('sample_count', 0)}`",
            f"- Freshness status: `{policy.get('freshness_status', {})}`",
            "",
        ]
    )

    if policy.get("actions"):
        lines.extend(["| Time ns | Actions | Authority | Latency ms |", "| ---: | ---: | --- | ---: |"])
        for action in policy["actions"][:10]:
            lines.append(
                "| {time_ns} | {count} | {authority} | {latency} |".format(
                    time_ns=format_ns(action.get("event_time_ns")),
                    count=action.get("proposed_action_count", 0),
                    authority=action.get("authority") or "",
                    latency=action.get("inference_latency_ms"),
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Observation Window",
            "",
            f"- Target time ns: `{window.get('target_time_ns')}`",
            f"- Window ms: `{window.get('window_ms')}`",
            "",
            "| Stream | Status | Delta ms | Frame | Payload Summary |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )

    for entry in window["streams"]:
        payload = entry.get("payload_summary")
        payload_text = ""
        if isinstance(payload, dict):
            payload_text = json.dumps(payload, sort_keys=True)[:160]
        lines.append(
            "| {stream_id} | {status} | {delta} | {frame} | `{payload}` |".format(
                stream_id=entry.get("stream_id") or "",
                status=entry.get("status") or "",
                delta=entry.get("delta_ms"),
                frame=entry.get("frame_id") or "",
                payload=payload_text,
            )
        )

    lines.extend(
        [
            "",
            "This report is a prototype dataset view. It preserves stream, time, frame, diagnostics, and policy metadata for inspection.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    episode_dir = args.episode
    episode_path = episode_dir / "episode.json"
    streams_path = episode_dir / "streams.json"
    diagnostics_path = episode_dir / "diagnostics.json"
    events_path = episode_dir / "events.jsonl"

    for path in (episode_path, streams_path, diagnostics_path, events_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing episode file: {path}")

    episode = load_json(episode_path)
    streams_json = load_json(streams_path)
    diagnostics = load_json(diagnostics_path)
    episode_events = load_jsonl(events_path)
    episode_samples = stream_samples(episode_events)

    policy_events: list[dict[str, Any]] = []
    if args.policy_events is not None:
        if not args.policy_events.exists():
            raise FileNotFoundError(f"Policy events file does not exist: {args.policy_events}")
        policy_events = load_jsonl(args.policy_events)

    target_time_ns = choose_target_time(
        episode=episode,
        episode_samples=episode_samples,
        policy_events=policy_events,
        requested_target_time_ns=args.target_time_ns,
    )
    report = build_report(
        episode_dir=episode_dir,
        episode=episode,
        streams_json=streams_json,
        diagnostics=diagnostics,
        episode_samples=episode_samples,
        policy_events=policy_events,
        target_time_ns=target_time_ns,
        window_ms=args.window_ms,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_dump(args.output_dir / "report.json", report)
    (args.output_dir / "report.md").write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "episode_id": episode.get("episode_id")}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
