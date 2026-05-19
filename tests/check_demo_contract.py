#!/usr/bin/env python3
"""Sanity-check the navigation + manipulation smoke demo contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_STREAMS = {
    "robot.camera.rgb",
    "robot.camera.depth",
    "robot.camera.info",
    "robot.joints.state",
    "robot.base.odom",
    "robot.frames.tf",
    "task.goal",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def first_stream(events: list[dict[str, Any]], stream_id: str) -> dict[str, Any]:
    for event in events:
        if event.get("stream_id") == stream_id:
            return event
    raise AssertionError(f"missing stream: {stream_id}")


def check_joint_contract(source_events: list[dict[str, Any]]) -> None:
    event = first_stream(source_events, "robot.joints.state")
    payload = event.get("payload_summary") or {}
    names = payload.get("joint_names_sample") or []
    positions = payload.get("position_sample") or []

    require(payload.get("joint_count") == 7, "joint_count must stay at 7 for RoMi-H")
    require(len(names) == 7, "joint_names_sample must contain 7 joints")
    require(payload.get("position_count") == 7, "position_count must be 7")
    require(len(positions) == 7, "position_sample must contain 7 positions")
    require(payload.get("velocity_count") == 7, "velocity_count must be 7")
    require(payload.get("effort_count") == 7, "effort_count must be 7")
    require(event.get("metadata", {}).get("robot_morphology") == "semi_humanoid_mobile_manipulator", "robot morphology metadata missing")
    require(event.get("metadata", {}).get("authority") == "observation_only", "observation stream authority must be observation_only")


def check_source_contract(source_events: list[dict[str, Any]]) -> None:
    stream_ids = {event.get("stream_id") for event in source_events if event.get("kind") == "stream_sample"}
    missing = REQUIRED_STREAMS - stream_ids
    require(not missing, f"missing required source streams: {sorted(missing)}")

    rgb = first_stream(source_events, "robot.camera.rgb")
    rgb_payload = rgb.get("payload_summary") or {}
    require(rgb_payload.get("data_len") == rgb_payload.get("height") * rgb_payload.get("width") * 3, "RGB data_len/shape mismatch")
    require(rgb_payload.get("synthetic_scene", {}).get("target_visible") is True, "RGB target should be visible at episode start")

    depth = first_stream(source_events, "robot.camera.depth")
    depth_payload = depth.get("payload_summary") or {}
    require(depth_payload.get("data_len") == depth_payload.get("height") * depth_payload.get("width") * 2, "depth data_len/shape mismatch")

    tf = first_stream(source_events, "robot.frames.tf")
    tf_payload = tf.get("payload_summary") or {}
    require(tf_payload.get("transform_count") == 6, "TF summary must expose 6 transforms")
    require(all("stamp_ns" in frame for frame in tf_payload.get("frames_sample", [])), "TF frames must carry stamp_ns")
    require("synthetic_base_translation" in tf_payload, "TF summary must include synthetic_base_translation")


def check_policy_contract(policy_events: list[dict[str, Any]], report: dict[str, Any]) -> None:
    policy_samples = [event for event in policy_events if event.get("kind") == "stream_sample"]
    require(policy_samples, "policy-events.jsonl must include stream samples")
    require(report.get("policy", {}).get("sample_count", 0) > 0, "dataset report must include policy samples")

    for event in policy_samples:
        require(event.get("stream_id") == "policy.proposed_action", "policy output stream must be policy.proposed_action")
        require(event.get("metadata", {}).get("authority") == "proposed_only", "policy metadata authority must be proposed_only")
        payload = event.get("payload_summary") or {}
        require(payload.get("metadata", {}).get("authority") == "proposed_only", "policy payload authority must be proposed_only")
        for action in payload.get("proposed_actions", []):
            require(action.get("authority") == "proposed_only", "each proposed action must be proposed_only")


def check_replay_contract(replay_events: list[dict[str, Any]]) -> None:
    replay_streams = [event for event in replay_events if event.get("kind") == "stream_sample"]
    require(replay_streams, "replay-events.jsonl must include stream samples")
    require(all(event.get("source_system") == "replay" for event in replay_streams[:20]), "replay samples must set source_system to replay")


def check_report_contract(report: dict[str, Any]) -> None:
    report_streams = {stream.get("stream_id") for stream in report.get("streams", [])}
    missing = REQUIRED_STREAMS - report_streams
    require(not missing, f"dataset report missing streams: {sorted(missing)}")

    window_streams = {stream.get("stream_id"): stream for stream in report.get("observation_window", {}).get("streams", [])}
    missing_window = REQUIRED_STREAMS - set(window_streams)
    require(not missing_window, f"observation window missing streams: {sorted(missing_window)}")
    require(all(stream.get("status") == "ok" for stream in window_streams.values()), "observation window streams must be ok")


def check_run(run_dir: Path) -> None:
    report = load_json(run_dir / "dataset-report" / "report.json")
    source_events = iter_jsonl(run_dir / "source-events.jsonl")
    replay_events = iter_jsonl(run_dir / "replay-events.jsonl")
    policy_events = iter_jsonl(run_dir / "policy-events.jsonl")

    check_source_contract(source_events)
    check_joint_contract(source_events)
    check_replay_contract(replay_events)
    check_policy_contract(policy_events, report)
    check_report_contract(report)

    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "streams": len(report.get("streams", [])),
                "policy_samples": report.get("policy", {}).get("sample_count", 0),
                "source_events": len(source_events),
                "replay_events": len(replay_events),
            },
            sort_keys=True,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="Smoke demo run directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    check_run(args.run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
