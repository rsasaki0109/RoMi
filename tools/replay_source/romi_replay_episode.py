#!/usr/bin/env python3
"""Replay stream samples from a prototype RoMi episode directory."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"
DIAGNOSTIC_SCHEMA_ID = "romi.core.diagnostic_event/0.1.0"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a RoMi prototype episode")
    parser.add_argument("--episode", required=True, type=Path, help="Episode directory.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output replay JSONL path. Defaults to stdout.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier. Ignored when --no-sleep is set.",
    )
    parser.add_argument(
        "--no-sleep",
        action="store_true",
        help="Emit replay events as fast as possible.",
    )
    parser.add_argument(
        "--stream",
        action="append",
        default=[],
        help="Replay only this stream ID. Can be repeated.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Maximum stream_sample events to replay.",
    )
    return parser.parse_args(argv)


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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_stream_events(episode_dir: Path, stream_filter: set[str]) -> list[dict[str, Any]]:
    events_path = episode_dir / "events.jsonl"
    if not events_path.exists():
        raise FileNotFoundError(f"Missing episode events file: {events_path}")

    events: list[dict[str, Any]] = []
    with events_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {events_path}:{line_number}") from exc
            if event.get("kind") != "stream_sample":
                continue
            if stream_filter and event.get("stream_id") not in stream_filter:
                continue
            events.append(event)

    events.sort(key=lambda item: (item.get("event_time_ns", 0), item.get("stream_id", "")))
    return events


def diagnostic_event(
    *,
    episode_id: str,
    severity: str,
    message: str,
    attributes: dict[str, Any],
    category: str = "replay",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": DIAGNOSTIC_SCHEMA_ID,
        "kind": "diagnostic_event",
        "event_id": f"replay_{category}_{time.time_ns()}",
        "time": {
            "event_time_ns": time.time_ns(),
            "clock_domain": "wall_time",
        },
        "severity": severity,
        "source": "replay_source",
        "category": category,
        "message": message,
        "attributes": {
            "episode_id": episode_id,
            **attributes,
        },
    }


def replay_sample(
    *,
    original: dict[str, Any],
    episode_id: str,
    sequence_index: int,
    first_event_time_ns: int,
    replay_start_wall_ns: int,
    speed: float,
    no_sleep: bool,
) -> dict[str, Any]:
    event_time_ns = original.get("event_time_ns", first_event_time_ns)
    if not isinstance(event_time_ns, int):
        event_time_ns = first_event_time_ns

    replay_elapsed_ns = event_time_ns - first_event_time_ns
    replay_emit_wall_ns = time.time_ns()

    replayed = dict(original)
    metadata = dict(replayed.get("metadata") or {})
    metadata["original_source_system"] = replayed.get("source_system")
    metadata["replay_source"] = "romi_replay_episode"

    replayed["source_system"] = "replay"
    replayed["replay_emit_wall_time_ns"] = replay_emit_wall_ns
    replayed["metadata"] = metadata
    replayed["replay"] = {
        "episode_id": episode_id,
        "sequence_index": sequence_index,
        "original_event_time_ns": event_time_ns,
        "replay_elapsed_ns": replay_elapsed_ns,
        "replay_start_wall_time_ns": replay_start_wall_ns,
        "replay_emit_wall_time_ns": replay_emit_wall_ns,
        "speed": speed,
        "no_sleep": no_sleep,
    }
    return replayed


def sleep_until_replay_time(
    *,
    event_time_ns: int,
    first_event_time_ns: int,
    replay_start_monotonic: float,
    speed: float,
) -> None:
    if speed <= 0:
        raise ValueError("--speed must be greater than zero")
    target_elapsed_sec = ((event_time_ns - first_event_time_ns) / 1_000_000_000.0) / speed
    target_monotonic = replay_start_monotonic + max(0.0, target_elapsed_sec)
    remaining = target_monotonic - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)


def run_replay(args: argparse.Namespace) -> int:
    episode_dir = args.episode
    episode_json_path = episode_dir / "episode.json"
    if not episode_json_path.exists():
        raise FileNotFoundError(f"Missing episode metadata: {episode_json_path}")

    episode = load_json(episode_json_path)
    episode_id = episode.get("episode_id", episode_dir.name)
    stream_filter = set(args.stream)
    events = load_stream_events(episode_dir, stream_filter)
    if args.max_events is not None:
        events = events[: args.max_events]

    writer = JsonlWriter(args.output)
    replay_start_wall_ns = time.time_ns()
    replay_start_monotonic = time.monotonic()

    try:
        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "replay_start",
                "episode_id": episode_id,
                "episode_dir": str(episode_dir),
                "stream_filter": sorted(stream_filter),
                "event_count": len(events),
                "speed": args.speed,
                "no_sleep": args.no_sleep,
                "wall_time_ns": replay_start_wall_ns,
            }
        )

        if not events:
            writer.write(
                diagnostic_event(
                    episode_id=episode_id,
                    severity="warning",
                    message="No stream_sample events available for replay.",
                    attributes={"episode_dir": str(episode_dir)},
                )
            )
            return 0

        first_event_time_ns = events[0].get("event_time_ns", 0)
        if not isinstance(first_event_time_ns, int):
            first_event_time_ns = 0

        last_event_time_ns = first_event_time_ns
        for index, event in enumerate(events):
            event_time_ns = event.get("event_time_ns", first_event_time_ns)
            if not isinstance(event_time_ns, int):
                event_time_ns = first_event_time_ns
            if not args.no_sleep:
                sleep_until_replay_time(
                    event_time_ns=event_time_ns,
                    first_event_time_ns=first_event_time_ns,
                    replay_start_monotonic=replay_start_monotonic,
                    speed=args.speed,
                )
            writer.write(
                replay_sample(
                    original=event,
                    episode_id=episode_id,
                    sequence_index=index,
                    first_event_time_ns=first_event_time_ns,
                    replay_start_wall_ns=replay_start_wall_ns,
                    speed=args.speed,
                    no_sleep=args.no_sleep,
                )
            )
            last_event_time_ns = event_time_ns

        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "replay_stop",
                "episode_id": episode_id,
                "event_count": len(events),
                "first_event_time_ns": first_event_time_ns,
                "last_event_time_ns": last_event_time_ns,
                "recorded_duration_ns": max(0, last_event_time_ns - first_event_time_ns),
                "wall_time_ns": time.time_ns(),
            }
        )
    finally:
        writer.close()

    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run_replay(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
