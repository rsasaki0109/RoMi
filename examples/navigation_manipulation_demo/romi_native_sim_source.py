#!/usr/bin/env python3
"""Emit a RoMi-native navigation + manipulation simulation episode."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"
ROBOTICS_SCHEMA_ID = "romi.robotics.stream_metadata/0.1.0"
DIAGNOSTIC_SCHEMA_ID = "romi.core.diagnostic_event/0.1.0"


class JsonlWriter:
    def __init__(self, output: Path | None) -> None:
        self.output = output
        if output is None:
            self.file = sys.stdout
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            self.file = output.open("w", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        self.file.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
        self.file.write("\n")
        self.file.flush()

    def close(self) -> None:
        if self.output is not None:
            self.file.close()


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def lerp(a: float, b: float, value: float) -> float:
    return a + (b - a) * value


def quaternion_from_yaw(yaw: float) -> dict[str, float]:
    return {
        "x": 0.0,
        "y": 0.0,
        "z": math.sin(yaw / 2.0),
        "w": math.cos(yaw / 2.0),
    }


def pose(progress: float) -> tuple[float, float, float]:
    p = ease(progress)
    x = lerp(0.0, 1.6, p)
    y = 0.45 * math.sin(p * math.pi)
    yaw = lerp(0.0, -0.72, p)
    return x, y, yaw


def stream_sample(
    *,
    stream_id: str,
    semantic_type: str,
    source_message_type: str,
    event_time_ns: int,
    frame_id: str | None,
    payload_summary: dict[str, Any],
    sample_index: int,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": ROBOTICS_SCHEMA_ID,
        "kind": "stream_sample",
        "stream_id": stream_id,
        "semantic_type": semantic_type,
        "source_system": "romi_native_sim",
        "source_topic": None,
        "source_message_type": source_message_type,
        "event_time_ns": event_time_ns,
        "source_emit_wall_time_ns": time.time_ns(),
        "clock_domain": "sim_time",
        "frame_id": frame_id,
        "payload_summary": payload_summary,
        "metadata": {
            "source": "romi_native_sim_source",
            "sample_index": sample_index,
            "authority": "observation_only",
        },
    }


def diagnostic_event(
    *,
    event_time_ns: int,
    sequence_index: int,
    severity: str,
    message: str,
    attributes: dict[str, Any],
    category: str = "native_sim",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": DIAGNOSTIC_SCHEMA_ID,
        "kind": "diagnostic_event",
        "event_id": f"native_sim_{category}_{sequence_index}",
        "time": {
            "event_time_ns": event_time_ns,
            "clock_domain": "sim_time",
        },
        "severity": severity,
        "source": "romi_native_sim",
        "category": category,
        "message": message,
        "attributes": attributes,
    }


def camera_summary(progress: float, *, depth: bool = False) -> dict[str, Any]:
    height = 90
    width = 160
    target_x = int(112 - 46 * ease(progress))
    target_y = int(48 + 8 * math.sin(progress * math.pi))
    if depth:
        return {
            "height": height,
            "width": width,
            "encoding": "16UC1",
            "is_bigendian": 0,
            "step": width * 2,
            "data_len": height * width * 2,
            "synthetic_scene": {
                "target_centroid_px": {"x": target_x, "y": target_y},
                "target_depth_mm": 620,
                "background_depth_mm": int(1800 - 900 * ease(progress)),
            },
        }
    return {
        "height": height,
        "width": width,
        "encoding": "rgb8",
        "is_bigendian": 0,
        "step": width * 3,
        "data_len": height * width * 3,
        "synthetic_scene": {
            "target_centroid_px": {"x": target_x, "y": target_y},
            "progress_bar": progress,
        },
    }


def camera_info_summary() -> dict[str, Any]:
    return {
        "height": 90,
        "width": 160,
        "distortion_model": "plumb_bob",
        "d_len": 0,
        "k_len": 9,
        "p_len": 12,
    }


def joint_summary(progress: float) -> dict[str, Any]:
    names = ["shoulder_pan", "shoulder_lift", "elbow", "wrist", "gripper_left", "gripper_right"]
    reach = ease(max(0.0, (progress - 0.55) / 0.35))
    positions = [
        -0.25 * reach,
        -0.55 * reach,
        0.85 * reach,
        -0.35 * reach,
        0.04 * (1.0 - reach),
        0.04 * (1.0 - reach),
    ]
    return {
        "joint_count": len(names),
        "joint_names_sample": names,
        "position_sample": positions,
        "position_count": len(positions),
        "velocity_count": len(positions),
        "effort_count": len(positions),
    }


def odom_summary(progress: float) -> dict[str, Any]:
    x, y, yaw = pose(progress)
    return {
        "child_frame_id": "base_link",
        "position": {"x": x, "y": y, "z": 0.0},
        "orientation": quaternion_from_yaw(yaw),
        "linear": {"x": 0.35 * (1.0 - progress), "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": -0.2},
    }


def tf_summary(event_time_ns: int, progress: float) -> dict[str, Any]:
    x, y, _ = pose(progress)
    frames = [
        ("map", "odom"),
        ("odom", "base_link"),
        ("base_link", "camera_color_optical_frame"),
        ("base_link", "camera_depth_optical_frame"),
        ("base_link", "arm_base_link"),
        ("arm_base_link", "tool0"),
    ]
    return {
        "transform_count": len(frames),
        "frames_sample": [
            {
                "parent_frame_id": parent,
                "child_frame_id": child,
                "stamp_ns": event_time_ns,
            }
            for parent, child in frames
        ],
        "synthetic_base_translation": {"x": x, "y": y, "z": 0.0},
    }


def goal_summary() -> dict[str, Any]:
    return {
        "position": {"x": 1.6, "y": 0.0, "z": 0.0},
        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
    }


def emit_episode(args: argparse.Namespace) -> int:
    writer = JsonlWriter(args.output)
    period_ns = int(1_000_000_000 / args.rate_hz)
    sample_count = int(args.duration_sec * args.rate_hz)
    diagnostic_every = max(1, int(args.rate_hz * args.diagnostics_period_sec))

    try:
        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "native_sim_start",
                "source": "romi_native_sim",
                "duration_sec": args.duration_sec,
                "rate_hz": args.rate_hz,
                "stream_count": 7,
                "wall_time_ns": time.time_ns(),
            }
        )

        for index in range(sample_count):
            progress = index / max(1, sample_count - 1)
            event_time_ns = index * period_ns
            sample_index = index + 1

            writer.write(
                stream_sample(
                    stream_id="robot.camera.rgb",
                    semantic_type="rgb_image",
                    source_message_type="romi.robotics.ImageSummary",
                    event_time_ns=event_time_ns,
                    frame_id="camera_color_optical_frame",
                    payload_summary=camera_summary(progress),
                    sample_index=sample_index,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.camera.depth",
                    semantic_type="depth_image",
                    source_message_type="romi.robotics.ImageSummary",
                    event_time_ns=event_time_ns,
                    frame_id="camera_depth_optical_frame",
                    payload_summary=camera_summary(progress, depth=True),
                    sample_index=sample_index,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.camera.info",
                    semantic_type="camera_info",
                    source_message_type="romi.robotics.CameraInfoSummary",
                    event_time_ns=event_time_ns,
                    frame_id="camera_color_optical_frame",
                    payload_summary=camera_info_summary(),
                    sample_index=sample_index,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.joints.state",
                    semantic_type="joint_state",
                    source_message_type="romi.robotics.JointStateSummary",
                    event_time_ns=event_time_ns,
                    frame_id="base_link",
                    payload_summary=joint_summary(progress),
                    sample_index=sample_index,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.base.odom",
                    semantic_type="odometry",
                    source_message_type="romi.robotics.OdometrySummary",
                    event_time_ns=event_time_ns,
                    frame_id="odom",
                    payload_summary=odom_summary(progress),
                    sample_index=sample_index,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.frames.tf",
                    semantic_type="transform_tree",
                    source_message_type="romi.robotics.TransformTreeSummary",
                    event_time_ns=event_time_ns,
                    frame_id="map->odom",
                    payload_summary=tf_summary(event_time_ns, progress),
                    sample_index=sample_index,
                )
            )

            if index % max(1, int(args.rate_hz)) == 0:
                writer.write(
                    stream_sample(
                        stream_id="task.goal",
                        semantic_type="task_goal",
                        source_message_type="romi.robotics.PoseGoalSummary",
                        event_time_ns=event_time_ns,
                        frame_id="map",
                        payload_summary=goal_summary(),
                        sample_index=(index // max(1, int(args.rate_hz))) + 1,
                    )
                )

            if index % diagnostic_every == 0:
                writer.write(
                    diagnostic_event(
                        event_time_ns=event_time_ns,
                        sequence_index=index // diagnostic_every,
                        severity="info",
                        message="Native simulation source emitted synchronized observation step.",
                        attributes={
                            "sample_index": sample_index,
                            "progress": progress,
                            "streams": [
                                "robot.camera.rgb",
                                "robot.camera.depth",
                                "robot.camera.info",
                                "robot.joints.state",
                                "robot.base.odom",
                                "robot.frames.tf",
                            ],
                        },
                    )
                )

        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "native_sim_stop",
                "source": "romi_native_sim",
                "sample_count": sample_count,
                "wall_time_ns": time.time_ns(),
            }
        )
    finally:
        writer.close()

    if args.output is not None:
        print(json.dumps({"output": str(args.output), "samples": sample_count}, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit a RoMi-native navigation + manipulation simulation")
    parser.add_argument("--output", type=Path, default=None, help="Output RoMi JSONL path. Defaults to stdout.")
    parser.add_argument("--duration-sec", type=float, default=5.5, help="Simulation duration in seconds.")
    parser.add_argument("--rate-hz", type=float, default=12.0, help="Observation rate in Hz.")
    parser.add_argument("--diagnostics-period-sec", type=float, default=0.5, help="Diagnostic event period.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.duration_sec <= 0:
        raise ValueError("--duration-sec must be greater than zero")
    if args.rate_hz <= 0:
        raise ValueError("--rate-hz must be greater than zero")
    if args.diagnostics_period_sec <= 0:
        raise ValueError("--diagnostics-period-sec must be greater than zero")
    return emit_episode(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
