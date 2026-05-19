#!/usr/bin/env python3
"""Create a prototype RoMi episode directory from bridge JSONL events."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"


@dataclass
class StreamSummary:
    stream_id: str
    schema_id: str | None = None
    semantic_type: str | None = None
    source_system: str | None = None
    source_topic: str | None = None
    source_message_type: str | None = None
    clock_domain: str | None = None
    count: int = 0
    first_event_time_ns: int | None = None
    last_event_time_ns: int | None = None
    first_receive_time_ns: int | None = None
    last_receive_time_ns: int | None = None
    frame_ids: set[str] = field(default_factory=set)
    qos: dict[str, Any] | None = None
    last_payload_summary: dict[str, Any] | None = None

    def update(self, event: dict[str, Any]) -> None:
        self.count += 1
        self.schema_id = event.get("schema_id") or self.schema_id
        self.semantic_type = event.get("semantic_type") or self.semantic_type
        self.source_system = event.get("source_system") or self.source_system
        self.source_topic = event.get("source_topic") or self.source_topic
        self.source_message_type = event.get("source_message_type") or self.source_message_type
        self.clock_domain = event.get("clock_domain") or self.clock_domain
        self.qos = event.get("qos") or self.qos
        self.last_payload_summary = event.get("payload_summary") or self.last_payload_summary

        frame_id = event.get("frame_id")
        if frame_id:
            self.frame_ids.add(frame_id)

        event_time_ns = event.get("event_time_ns")
        if isinstance(event_time_ns, int):
            if self.first_event_time_ns is None:
                self.first_event_time_ns = event_time_ns
            self.last_event_time_ns = event_time_ns

        receive_time_ns = event.get("bridge_receive_time_ns")
        if isinstance(receive_time_ns, int):
            if self.first_receive_time_ns is None:
                self.first_receive_time_ns = receive_time_ns
            self.last_receive_time_ns = receive_time_ns

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "schema_id": self.schema_id,
            "semantic_type": self.semantic_type,
            "source_system": self.source_system,
            "source_topic": self.source_topic,
            "source_message_type": self.source_message_type,
            "clock_domain": self.clock_domain,
            "message_count": self.count,
            "first_event_time_ns": self.first_event_time_ns,
            "last_event_time_ns": self.last_event_time_ns,
            "first_receive_time_ns": self.first_receive_time_ns,
            "last_receive_time_ns": self.last_receive_time_ns,
            "frame_ids": sorted(self.frame_ids),
            "qos": self.qos,
            "last_payload_summary": self.last_payload_summary,
        }


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def default_runtime_graph() -> Path:
    return repo_root_from_script() / "examples/navigation_manipulation_demo/runtime-graph.example.json"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a RoMi prototype episode from JSONL events")
    parser.add_argument("--input", required=True, type=Path, help="Input bridge JSONL file.")
    parser.add_argument("--output", required=True, type=Path, help="Output episode directory.")
    parser.add_argument("--episode-id", required=True, help="Episode ID.")
    parser.add_argument(
        "--scenario-name",
        default="navigation_to_table_and_mock_pick",
        help="Scenario name.",
    )
    parser.add_argument(
        "--mode",
        choices=["live", "simulation", "replay", "dataset"],
        default="simulation",
        help="Episode mode.",
    )
    parser.add_argument("--world-id", default=None, help="World, map, or scene ID.")
    parser.add_argument("--robot-id", default=None, help="Robot ID or profile.")
    parser.add_argument(
        "--runtime-graph",
        type=Path,
        default=default_runtime_graph(),
        help="Runtime graph JSON to reference in episode metadata.",
    )
    parser.add_argument(
        "--max-diagnostics",
        type=int,
        default=200,
        help="Maximum diagnostic events to include in diagnostics.json.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow writing into a non-empty output directory.",
    )
    return parser.parse_args(argv)


def load_runtime_graph(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"graph_id": "unknown", "nodes": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = []
    for node in data.get("nodes", []):
        if isinstance(node, dict):
            nodes.append(node.get("node_id", "unknown"))
        else:
            nodes.append(str(node))
    return {
        "graph_id": data.get("graph_id", "unknown"),
        "nodes": nodes,
    }


def json_dump(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_bounds(bounds: dict[str, int | None], event: dict[str, Any]) -> None:
    for key in ("event_time_ns", "bridge_receive_time_ns"):
        value = event.get(key)
        if not isinstance(value, int):
            continue
        first_key = f"first_{key}"
        last_key = f"last_{key}"
        if bounds[first_key] is None:
            bounds[first_key] = value
        bounds[last_key] = value


def read_and_copy_events(
    *,
    input_path: Path,
    output_events_path: Path,
    max_diagnostics: int,
) -> tuple[dict[str, StreamSummary], dict[str, Any], dict[str, int | None], dict[str, int]]:
    streams: dict[str, StreamSummary] = {}
    diagnostics: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_count": 0,
        "by_severity": {},
        "by_category": {},
        "events": [],
    }
    bounds: dict[str, int | None] = {
        "first_event_time_ns": None,
        "last_event_time_ns": None,
        "first_bridge_receive_time_ns": None,
        "last_bridge_receive_time_ns": None,
    }
    counts = {
        "total_lines": 0,
        "valid_events": 0,
        "stream_sample_events": 0,
        "diagnostic_events": 0,
        "invalid_lines": 0,
    }

    with input_path.open("r", encoding="utf-8") as source, output_events_path.open(
        "w", encoding="utf-8"
    ) as sink:
        for line in source:
            counts["total_lines"] += 1
            sink.write(line)
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                counts["invalid_lines"] += 1
                continue

            counts["valid_events"] += 1
            kind = event.get("kind")
            if kind == "stream_sample":
                counts["stream_sample_events"] += 1
                stream_id = event.get("stream_id", "unknown")
                stream = streams.setdefault(stream_id, StreamSummary(stream_id=stream_id))
                stream.update(event)
                update_bounds(bounds, event)
            elif kind == "diagnostic_event":
                counts["diagnostic_events"] += 1
                diagnostics["event_count"] += 1
                severity = event.get("severity", "unknown")
                category = event.get("category", "unknown")
                diagnostics["by_severity"][severity] = diagnostics["by_severity"].get(severity, 0) + 1
                diagnostics["by_category"][category] = diagnostics["by_category"].get(category, 0) + 1
                if len(diagnostics["events"]) < max_diagnostics:
                    diagnostics["events"].append(event)

    return streams, diagnostics, bounds, counts


def build_episode_metadata(
    *,
    args: argparse.Namespace,
    streams: dict[str, StreamSummary],
    bounds: dict[str, int | None],
    counts: dict[str, int],
    runtime_graph: dict[str, Any],
) -> dict[str, Any]:
    stream_values = list(streams.values())
    clock_domain = "unknown"
    for stream in stream_values:
        if stream.clock_domain:
            clock_domain = stream.clock_domain
            break

    start_time_ns = bounds["first_event_time_ns"] or 0
    end_time_ns = bounds["last_event_time_ns"] or start_time_ns

    return {
        "schema_version": SCHEMA_VERSION,
        "episode_id": args.episode_id,
        "scenario": {
            "name": args.scenario_name,
            "mode": args.mode,
            "world_id": args.world_id,
            "robot_id": args.robot_id,
        },
        "clock": {
            "clock_domain": clock_domain,
            "start_time_ns": start_time_ns,
            "end_time_ns": end_time_ns,
            "replay_time_scale": 1.0,
        },
        "streams": [
            {
                "stream_id": stream.stream_id,
                "schema_id": stream.schema_id,
                "source": stream.source_topic or stream.source_system,
                "message_count": stream.count,
            }
            for stream in sorted(stream_values, key=lambda item: item.stream_id)
        ],
        "runtime_graph": runtime_graph,
        "metadata": {
            "recording_format": "romi-jsonl-prototype",
            "logging_direction": "mcap-compatible",
            "source_input": str(args.input),
            "events_file": "events.jsonl",
            "streams_file": "streams.json",
            "diagnostics_file": "diagnostics.json",
            "generated_at_unix_ns": time.time_ns(),
            "total_lines": counts["total_lines"],
            "valid_events": counts["valid_events"],
            "stream_sample_events": counts["stream_sample_events"],
            "diagnostic_events": counts["diagnostic_events"],
            "invalid_lines": counts["invalid_lines"],
        },
    }


def build_streams_json(streams: dict[str, StreamSummary], counts: dict[str, int]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "stream_count": len(streams),
        "sample_count": counts["stream_sample_events"],
        "streams": [
            stream.to_dict()
            for stream in sorted(streams.values(), key=lambda item: item.stream_id)
        ],
    }


def build_episode_readme(
    *,
    episode: dict[str, Any],
    streams_json: dict[str, Any],
    diagnostics: dict[str, Any],
    counts: dict[str, int],
) -> str:
    lines = [
        f"# Episode {episode['episode_id']}",
        "",
        "Prototype RoMi episode generated from bridge JSONL output.",
        "",
        "## Summary",
        "",
        f"- Scenario: `{episode['scenario']['name']}`",
        f"- Mode: `{episode['scenario']['mode']}`",
        f"- Clock domain: `{episode['clock']['clock_domain']}`",
        f"- Stream count: `{streams_json['stream_count']}`",
        f"- Stream samples: `{counts['stream_sample_events']}`",
        f"- Diagnostic events: `{counts['diagnostic_events']}`",
        f"- Invalid lines: `{counts['invalid_lines']}`",
        "",
        "## Files",
        "",
        "- `events.jsonl`: copied bridge events",
        "- `episode.json`: episode metadata",
        "- `streams.json`: stream summary",
        "- `diagnostics.json`: diagnostics summary",
        "",
        "## Streams",
        "",
    ]

    if not streams_json["streams"]:
        lines.append("No stream samples were recorded.")
    else:
        lines.extend(["| Stream | Samples | Source | Type |", "| --- | ---: | --- | --- |"])
        for stream in streams_json["streams"]:
            lines.append(
                "| {stream_id} | {count} | {source} | {message_type} |".format(
                    stream_id=stream["stream_id"],
                    count=stream["message_count"],
                    source=stream.get("source_topic") or stream.get("source_system") or "",
                    message_type=stream.get("source_message_type") or "",
                )
            )

    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            f"- By severity: `{diagnostics['by_severity']}`",
            f"- By category: `{diagnostics['by_category']}`",
            "",
            "This is a prototype episode layout, not a final storage format.",
            "",
        ]
    )
    return "\n".join(lines)


def ensure_output_dir(path: Path, force: bool) -> None:
    if path.exists() and any(path.iterdir()) and not force:
        raise RuntimeError(f"Output directory is not empty: {path}. Use --force to overwrite files.")
    path.mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if not args.input.exists():
        raise FileNotFoundError(f"Input JSONL does not exist: {args.input}")

    ensure_output_dir(args.output, args.force)

    events_path = args.output / "events.jsonl"
    if args.input.resolve() == events_path.resolve():
        raise RuntimeError("Input path and output events path must be different.")

    streams, diagnostics, bounds, counts = read_and_copy_events(
        input_path=args.input,
        output_events_path=events_path,
        max_diagnostics=args.max_diagnostics,
    )
    runtime_graph = load_runtime_graph(args.runtime_graph)
    episode = build_episode_metadata(
        args=args,
        streams=streams,
        bounds=bounds,
        counts=counts,
        runtime_graph=runtime_graph,
    )
    streams_json = build_streams_json(streams, counts)

    json_dump(args.output / "episode.json", episode)
    json_dump(args.output / "streams.json", streams_json)
    json_dump(args.output / "diagnostics.json", diagnostics)
    (args.output / "README.md").write_text(
        build_episode_readme(
            episode=episode,
            streams_json=streams_json,
            diagnostics=diagnostics,
            counts=counts,
        ),
        encoding="utf-8",
    )

    print(json.dumps({"episode_id": args.episode_id, "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
