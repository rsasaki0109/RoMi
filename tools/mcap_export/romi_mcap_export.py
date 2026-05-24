#!/usr/bin/env python3
"""Export a RoMi episode (and optional policy proposals) to an MCAP file.

Writes the RoMi stream samples into an [MCAP](https://mcap.dev) file using
Foxglove well-known schemas so the result opens directly in Foxglove Studio:

- ``robot.base.odom``        -> ``/robot/base/pose``      (foxglove.PoseInFrame)
- ``expert.action``          -> ``/expert/goal``          (foxglove.PoseInFrame)
- ``policy.proposed_action`` -> ``/policy/proposed_goal`` (foxglove.PoseInFrame)
- ``task.goal``              -> ``/task/goal``            (foxglove.Log)

This is RoMi's first MCAP-compatible export. It is intentionally a mapping from
the existing stream envelope, not a new storage layer: event time, frame id, and
stream identity are preserved. RoMi stays MCAP-compatible, not MCAP-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from mcap.writer import Writer

POSE_IN_FRAME_SCHEMA = {
    "type": "object",
    "title": "foxglove.PoseInFrame",
    "properties": {
        "timestamp": {
            "type": "object",
            "properties": {"sec": {"type": "integer"}, "nsec": {"type": "integer"}},
        },
        "frame_id": {"type": "string"},
        "pose": {
            "type": "object",
            "properties": {
                "position": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"},
                    },
                },
                "orientation": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"},
                        "w": {"type": "number"},
                    },
                },
            },
        },
    },
}

LOG_SCHEMA = {
    "type": "object",
    "title": "foxglove.Log",
    "properties": {
        "timestamp": {
            "type": "object",
            "properties": {"sec": {"type": "integer"}, "nsec": {"type": "integer"}},
        },
        "level": {"type": "integer"},
        "message": {"type": "string"},
        "name": {"type": "string"},
    },
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True, type=Path, help="Episode JSONL.")
    parser.add_argument("--policy", type=Path, default=None, help="Optional policy proposals JSONL.")
    parser.add_argument("--output", required=True, type=Path, help="Output .mcap path.")
    parser.add_argument("--frame-id", default="world", help="Frame id for poses. Defaults to world.")
    return parser.parse_args(argv)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ts(event_time_ns: int) -> dict[str, int]:
    return {"sec": event_time_ns // 1_000_000_000, "nsec": event_time_ns % 1_000_000_000}


def pose_message(*, event_time_ns: int, frame_id: str, x: float, y: float) -> dict[str, Any]:
    return {
        "timestamp": ts(event_time_ns),
        "frame_id": frame_id,
        "pose": {
            "position": {"x": x, "y": y, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }


def expert_goal(event: dict[str, Any]) -> tuple[float, float] | None:
    values = event.get("payload_summary", {}).get("values", {})
    goal = values.get("goal_position")
    if isinstance(goal, dict):
        return float(goal.get("x", 0.0)), float(goal.get("y", 0.0))
    return None


def proposed_goal(event: dict[str, Any]) -> tuple[float, float] | None:
    for action in event.get("payload_summary", {}).get("proposed_actions", []):
        if isinstance(action, dict) and action.get("action_type") == "navigate_to_goal":
            goal = action.get("values", {}).get("goal_position")
            if isinstance(goal, dict):
                return float(goal.get("x", 0.0)), float(goal.get("y", 0.0))
    return None


def agent_position(event: dict[str, Any]) -> tuple[float, float] | None:
    position = event.get("payload_summary", {}).get("position")
    if isinstance(position, dict):
        return float(position.get("x", 0.0)), float(position.get("y", 0.0))
    return None


def run(args: argparse.Namespace) -> int:
    events = load_jsonl(args.episode)
    if args.policy is not None:
        events = events + load_jsonl(args.policy)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with args.output.open("wb") as handle:
        writer = Writer(handle)
        writer.start()
        pose_schema = writer.register_schema(
            name="foxglove.PoseInFrame", encoding="jsonschema",
            data=json.dumps(POSE_IN_FRAME_SCHEMA).encode("utf-8"),
        )
        log_schema = writer.register_schema(
            name="foxglove.Log", encoding="jsonschema",
            data=json.dumps(LOG_SCHEMA).encode("utf-8"),
        )
        channels = {
            "/robot/base/pose": writer.register_channel(topic="/robot/base/pose", message_encoding="json", schema_id=pose_schema),
            "/expert/goal": writer.register_channel(topic="/expert/goal", message_encoding="json", schema_id=pose_schema),
            "/policy/proposed_goal": writer.register_channel(topic="/policy/proposed_goal", message_encoding="json", schema_id=pose_schema),
            "/task/goal": writer.register_channel(topic="/task/goal", message_encoding="json", schema_id=log_schema),
        }

        def emit(topic: str, event_time_ns: int, message: dict[str, Any]) -> None:
            writer.add_message(
                channel_id=channels[topic],
                log_time=event_time_ns,
                publish_time=event_time_ns,
                data=json.dumps(message).encode("utf-8"),
            )
            counts[topic] = counts.get(topic, 0) + 1

        for event in events:
            if event.get("kind") != "stream_sample":
                continue
            event_time_ns = int(event.get("event_time_ns", 0))
            stream_id = event.get("stream_id")
            if stream_id == "robot.base.odom":
                pos = agent_position(event)
                if pos:
                    emit("/robot/base/pose", event_time_ns, pose_message(event_time_ns=event_time_ns, frame_id=args.frame_id, x=pos[0], y=pos[1]))
            elif stream_id == "expert.action":
                goal = expert_goal(event)
                if goal:
                    emit("/expert/goal", event_time_ns, pose_message(event_time_ns=event_time_ns, frame_id=args.frame_id, x=goal[0], y=goal[1]))
            elif stream_id == "policy.proposed_action":
                goal = proposed_goal(event)
                if goal:
                    emit("/policy/proposed_goal", event_time_ns, pose_message(event_time_ns=event_time_ns, frame_id=args.frame_id, x=goal[0], y=goal[1]))
            elif stream_id == "task.goal":
                text = event.get("payload_summary", {}).get("task_text", "task")
                emit("/task/goal", event_time_ns, {"timestamp": ts(event_time_ns), "level": 1, "message": str(text), "name": "task.goal"})

        writer.finish()

    total = sum(counts.values())
    summary = ", ".join(f"{topic}={n}" for topic, n in sorted(counts.items()))
    print(f"wrote {args.output}: {total} messages ({summary})", file=sys.stderr)
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
