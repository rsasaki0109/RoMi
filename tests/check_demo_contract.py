#!/usr/bin/env python3
"""Sanity-check the navigation + manipulation smoke demo contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def default_contract_path() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "navigation_manipulation_demo" / "contract.example.json"


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


def required_stream_ids(contract: dict[str, Any]) -> set[str]:
    return {stream["stream_id"] for stream in contract["required_streams"]}


def stream_contract(contract: dict[str, Any], stream_id: str) -> dict[str, Any]:
    for stream in contract["required_streams"]:
        if stream["stream_id"] == stream_id:
            return stream
    raise AssertionError(f"missing stream contract: {stream_id}")


def check_joint_contract(source_events: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    joint_contract = contract["robot"]["joint_state"]
    event = first_stream(source_events, joint_contract["stream_id"])
    payload = event.get("payload_summary") or {}
    names = payload.get("joint_names_sample") or []
    positions = payload.get("position_sample") or []

    require(payload.get("joint_count") == joint_contract["joint_count"], "joint_count must match contract")
    require(names == joint_contract["joint_names"], "joint_names_sample must match contract")
    require(payload.get("position_count") == joint_contract["position_count"], "position_count must match contract")
    require(len(positions) == joint_contract["position_count"], "position_sample length must match contract")
    require(payload.get("velocity_count") == joint_contract["velocity_count"], "velocity_count must match contract")
    require(payload.get("effort_count") == joint_contract["effort_count"], "effort_count must match contract")
    require(event.get("metadata", {}).get("robot_morphology") == contract["robot"]["morphology"], "robot morphology metadata missing")
    require(event.get("metadata", {}).get("authority") == contract["source_invariants"]["observation_authority"], "observation stream authority mismatch")


def check_source_contract(source_events: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    stream_ids = {event.get("stream_id") for event in source_events if event.get("kind") == "stream_sample"}
    missing = required_stream_ids(contract) - stream_ids
    require(not missing, f"missing required source streams: {sorted(missing)}")
    expected_clock = contract["source_invariants"]["clock_domain"]
    for stream_id in required_stream_ids(contract):
        event = first_stream(source_events, stream_id)
        stream = stream_contract(contract, stream_id)
        require(event.get("semantic_type") == stream["semantic_type"], f"{stream_id} semantic_type mismatch")
        require(event.get("frame_id") == stream["frame_id"], f"{stream_id} frame_id mismatch")
        require(event.get("source_message_type") == stream["source_message_type"], f"{stream_id} source_message_type mismatch")
        require(event.get("clock_domain") == expected_clock, f"{stream_id} clock_domain mismatch")
        require(event.get("metadata", {}).get("scenario_id") == contract["scenario_id"], f"{stream_id} scenario_id mismatch")

    rgb = first_stream(source_events, "robot.camera.rgb")
    rgb_contract = stream_contract(contract, "robot.camera.rgb")["payload_invariants"]
    rgb_payload = rgb.get("payload_summary") or {}
    require(rgb_payload.get("encoding") == rgb_contract["encoding"], "RGB encoding mismatch")
    require(rgb_payload.get("data_len") == rgb_payload.get("height") * rgb_payload.get("width") * rgb_contract["channels"], "RGB data_len/shape mismatch")
    require(rgb_payload.get("synthetic_scene", {}).get("target_visible") is True, "RGB target should be visible at episode start")

    depth = first_stream(source_events, "robot.camera.depth")
    depth_contract = stream_contract(contract, "robot.camera.depth")["payload_invariants"]
    depth_payload = depth.get("payload_summary") or {}
    require(depth_payload.get("encoding") == depth_contract["encoding"], "depth encoding mismatch")
    require(depth_payload.get("data_len") == depth_payload.get("height") * depth_payload.get("width") * depth_contract["channels"], "depth data_len/shape mismatch")

    tf = first_stream(source_events, "robot.frames.tf")
    tf_contract = stream_contract(contract, "robot.frames.tf")["payload_invariants"]
    tf_payload = tf.get("payload_summary") or {}
    require(tf_payload.get("transform_count") == tf_contract["transform_count"], "TF summary transform_count mismatch")
    require(all("stamp_ns" in frame for frame in tf_payload.get("frames_sample", [])), "TF frames must carry stamp_ns")
    for field in tf_contract["required_fields"]:
        require(field in tf_payload, f"TF summary must include {field}")


def check_policy_contract(policy_events: list[dict[str, Any]], report: dict[str, Any], contract: dict[str, Any]) -> None:
    policy_contract = contract["policy"]
    policy_samples = [event for event in policy_events if event.get("kind") == "stream_sample"]
    require(policy_samples, "policy-events.jsonl must include stream samples")
    require(report.get("policy", {}).get("sample_count", 0) > 0, "dataset report must include policy samples")

    for event in policy_samples:
        require(event.get("stream_id") == policy_contract["stream_id"], "policy output stream mismatch")
        require(event.get("metadata", {}).get("authority") == policy_contract["authority"], "policy metadata authority mismatch")
        payload = event.get("payload_summary") or {}
        require(payload.get("metadata", {}).get("authority") == policy_contract["authority"], "policy payload authority mismatch")
        for action in payload.get("proposed_actions", []):
            require(action.get("authority") == policy_contract["authority"], "each proposed action authority mismatch")


def check_replay_contract(replay_events: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    replay_streams = [event for event in replay_events if event.get("kind") == "stream_sample"]
    require(replay_streams, "replay-events.jsonl must include stream samples")
    expected_source = contract["replay_invariants"]["source_system"]
    require(all(event.get("source_system") == expected_source for event in replay_streams[:20]), f"replay samples must set source_system to {expected_source}")


def check_report_contract(report: dict[str, Any], contract: dict[str, Any]) -> None:
    for section in contract["dataset_report"]["required_sections"]:
        require(section in report, f"dataset report missing section: {section}")

    report_streams = {stream.get("stream_id") for stream in report.get("streams", [])}
    missing = required_stream_ids(contract) - report_streams
    require(not missing, f"dataset report missing streams: {sorted(missing)}")

    window_streams = {stream.get("stream_id"): stream for stream in report.get("observation_window", {}).get("streams", [])}
    missing_window = required_stream_ids(contract) - set(window_streams)
    require(not missing_window, f"observation window missing streams: {sorted(missing_window)}")
    expected_status = contract["dataset_report"]["observation_window_status"]
    require(all(stream.get("status") == expected_status for stream in window_streams.values()), f"observation window streams must be {expected_status}")


def check_run(run_dir: Path, contract: dict[str, Any]) -> None:
    report = load_json(run_dir / "dataset-report" / "report.json")
    source_events = iter_jsonl(run_dir / "source-events.jsonl")
    replay_events = iter_jsonl(run_dir / "replay-events.jsonl")
    policy_events = iter_jsonl(run_dir / "policy-events.jsonl")

    check_source_contract(source_events, contract)
    check_joint_contract(source_events, contract)
    check_replay_contract(replay_events, contract)
    check_policy_contract(policy_events, report, contract)
    check_report_contract(report, contract)

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
    parser.add_argument("--contract", type=Path, default=default_contract_path(), help="Demo contract JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    check_run(args.run_dir, load_json(args.contract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
