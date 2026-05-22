#!/usr/bin/env python3
"""Validate the committed ROS2 bridge diagnostics example."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from bridges.ros2.rclpy_bridge.romi_ros2_bridge import load_stream_configs, qos_metadata  # noqa: E402
from check_sample_artifact_schemas import validate_schema  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_bridge_configs(repo_root: Path) -> None:
    configs = load_stream_configs(repo_root / "examples" / "navigation_manipulation_demo" / "stream-map.example.json")
    source_topics = {config.source_topic for config in configs if config.source_topic}
    required_topics = {
        "/camera/color/image_raw",
        "/camera/depth/image_raw",
        "/camera/color/camera_info",
        "/joint_states",
        "/odom",
        "/tf",
        "/tf_static",
        "/goal_pose",
    }
    require(required_topics.issubset(source_topics), f"stream map missing ROS2 topics: {sorted(required_topics - source_topics)}")

    tf_configs = [config for config in configs if config.stream_id == "robot.frames.tf"]
    require(len(tf_configs) == 2, "stream map should map /tf and /tf_static into robot.frames.tf")

    static_tf = next(config for config in tf_configs if config.source_topic == "/tf_static")
    require(static_tf.static_transform is True, "/tf_static config should be marked static_transform")
    static_qos = qos_metadata(static_tf)
    require(static_qos["durability"] == "transient_local", "/tf_static should use transient local QoS")
    require(static_qos["reliability"] == "reliable", "/tf_static should use reliable QoS")

    policy_configs = [config for config in configs if config.stream_id == "policy.proposed_action"]
    require(len(policy_configs) == 1, "stream map should include one policy proposal stream")
    require(policy_configs[0].source_topic is None, "policy proposal stream should not be a ROS2 command topic")

    sample_schema = load_json(repo_root / "schemas" / "core" / "stream_sample.schema.json")
    bridge_sample = {
        "schema_version": "0.1.0",
        "schema_id": "romi.robotics.stream_metadata/0.1.0",
        "kind": "stream_sample",
        "stream_id": static_tf.stream_id,
        "semantic_type": static_tf.semantic_type,
        "source_system": "ros2",
        "source_topic": static_tf.source_topic,
        "source_message_type": static_tf.source_message_type,
        "event_time_ns": 12000000000,
        "bridge_receive_time_ns": 12001000000,
        "bridge_latency_ms": 1.0,
        "clock_domain": static_tf.clock_domain,
        "frame_id": "base_link->camera_color_optical_frame",
        "qos": static_qos,
        "payload_summary": {
            "transform_count": 1,
            "frames_sample": [
                {
                    "parent_frame_id": "base_link",
                    "child_frame_id": "camera_color_optical_frame",
                    "stamp_ns": 12000000000,
                }
            ],
        },
        "metadata": {
            "bridge": "rclpy_bridge",
            "sample_index": 1,
            "static_transform": True,
        },
    }
    validate_schema(bridge_sample, sample_schema, "$.ros2_tf_static_sample")

    lifecycle_schema = load_json(repo_root / "schemas" / "core" / "lifecycle_event.schema.json")
    validate_schema(
        {
            "schema_version": "0.1.0",
            "kind": "bridge_start",
            "bridge": "rclpy_bridge",
            "node_name": "romi_ros2_bridge",
            "stream_count": len(configs),
            "supported_message_types": ["tf2_msgs/msg/TFMessage"],
            "wall_time_ns": 12000000000,
        },
        lifecycle_schema,
        "$.ros2_bridge_start",
    )
    validate_schema(
        {
            "schema_version": "0.1.0",
            "kind": "bridge_stop",
            "bridge": "rclpy_bridge",
            "wall_time_ns": 12050000000,
            "streams": [
                {
                    "stream_id": static_tf.stream_id,
                    "source_topic": static_tf.source_topic,
                    "source_message_type": static_tf.source_message_type,
                    "sample_count": 1,
                    "gap_count": 0,
                    "last_frame_id": "base_link->camera_color_optical_frame",
                    "qos": static_qos,
                    "static_transform": True,
                }
            ],
        },
        lifecycle_schema,
        "$.ros2_bridge_stop",
    )


def check_demo_publisher(repo_root: Path) -> None:
    publisher_path = repo_root / "examples" / "navigation_manipulation_demo" / "ros2_demo_sim_publisher.py"
    source = publisher_path.read_text(encoding="utf-8")
    require('"/tf_static"' in source, "ROS2 demo publisher should publish /tf_static")
    require("TRANSIENT_LOCAL" in source, "ROS2 demo publisher should use transient-local QoS for /tf_static")
    require("publish_static_tf" in source, "ROS2 demo publisher should keep static TF publishing explicit")


def check_report(repo_root: Path) -> None:
    report_path = repo_root / "examples" / "navigation_manipulation_demo" / "ros2-qos-diagnostics.example.json"
    report = load_json(report_path)
    report_schema = load_json(repo_root / "schemas" / "observability" / "ros2_bridge_diagnostics.schema.json")
    diagnostic_schema = load_json(repo_root / "schemas" / "core" / "diagnostic_event.schema.json")

    validate_schema(report, report_schema)
    for event in report["events"]:
        validate_schema(event, diagnostic_schema)

    stream_topics = {stream["source_topic"] for stream in report["streams"]}
    require("/tf" in stream_topics and "/tf_static" in stream_topics, "diagnostics report should include /tf and /tf_static")

    tf_static = next(stream for stream in report["streams"] if stream["source_topic"] == "/tf_static")
    require(tf_static["stream_id"] == "robot.frames.tf", "/tf_static should share the RoMi frame stream")
    require(tf_static["qos"]["durability"] == "transient_local", "diagnostics report should preserve /tf_static durability")
    require(tf_static["timing"]["expected_rate_hz"] == 0.0, "/tf_static should not pretend to be periodic")

    warning_streams = [stream for stream in report["streams"] if stream["status"] == "warning"]
    require(warning_streams, "diagnostics report should include at least one warning example")
    require(any(event["severity"] == "warning" for event in report["events"]), "diagnostics events should include a warning")

    require(report["summary"]["policy_authority"] == "proposed_only", "policy authority boundary mismatch")
    require(report["summary"]["actuator_authority"] == "none", "actuator authority boundary mismatch")
    require(any("not a ROS2 replacement" in item for item in report["limitations"]), "bridge limitations should avoid replacement messaging")


def check_runbook_docs(repo_root: Path) -> None:
    readme = (repo_root / "bridges" / "ros2" / "rclpy_bridge" / "README.md").read_text(encoding="utf-8")
    require("ROMI_DEMO_SOURCE=ros2" in readme, "ROS2 bridge README should include the scripted smoke command")
    require("tests/check_demo_contract.py" in readme, "ROS2 bridge README should include the validation command")
    require("source-events.jsonl" in readme, "ROS2 bridge README should list expected output files")
    require("/tf_static" in readme, "ROS2 bridge README should document /tf_static troubleshooting")
    require("numpy" in readme, "ROS2 bridge README should mention demo publisher numpy dependency")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    check_bridge_configs(repo_root)
    check_demo_publisher(repo_root)
    check_report(repo_root)
    check_runbook_docs(repo_root)
    print(
        json.dumps(
            {
                "validated_artifact": "examples/navigation_manipulation_demo/ros2-qos-diagnostics.example.json",
                "validated_topics": 8,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
