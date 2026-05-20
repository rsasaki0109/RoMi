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


def default_scenario_path() -> Path:
    return Path(__file__).resolve().parent / "scenario.json"


def load_scenario(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Scenario must be a JSON object: {path}")
    return data


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def lerp(a: float, b: float, value: float) -> float:
    return a + (b - a) * value


def pair(value: Any, fallback: tuple[float, float]) -> tuple[float, float]:
    if isinstance(value, list | tuple) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return fallback


def timing(scenario: dict[str, Any]) -> dict[str, Any]:
    value = scenario.get("timing")
    return value if isinstance(value, dict) else {}


def camera_config(scenario: dict[str, Any]) -> dict[str, Any]:
    value = scenario.get("camera")
    return value if isinstance(value, dict) else {}


def workspace_config(scenario: dict[str, Any]) -> dict[str, Any]:
    value = scenario.get("workspace")
    return value if isinstance(value, dict) else {}


def robot_config(scenario: dict[str, Any]) -> dict[str, Any]:
    value = scenario.get("robot")
    return value if isinstance(value, dict) else {}


def arm_config(scenario: dict[str, Any]) -> dict[str, Any]:
    value = scenario.get("arm")
    return value if isinstance(value, dict) else {}


def stage_name(scenario: dict[str, Any], progress: float) -> str:
    for stage in timing(scenario).get("stages", []):
        if not isinstance(stage, dict):
            continue
        start = float(stage.get("start", 0.0))
        end = float(stage.get("end", 1.0))
        if start <= progress < end:
            return str(stage.get("name", "unknown"))
    return "report"


def quaternion_from_yaw(yaw: float) -> dict[str, float]:
    return {
        "x": 0.0,
        "y": 0.0,
        "z": math.sin(yaw / 2.0),
        "w": math.cos(yaw / 2.0),
    }


def robot_pose_px(scenario: dict[str, Any], progress: float) -> tuple[float, float, float]:
    robot = robot_config(scenario)
    timing_data = timing(scenario)
    start_x, start_y = pair(robot.get("start_px"), (140.0, 392.0))
    goal_x, goal_y = pair(robot.get("goal_px"), (625.0, 392.0))
    nav_end = float(timing_data.get("nav_end", 0.58))
    nav = ease(progress / nav_end if nav_end > 0 else progress)
    x = lerp(start_x, goal_x, nav)
    y = lerp(start_y, goal_y, nav) - float(robot.get("path_arc_height_px", 120.0)) * math.sin(nav * math.pi)
    yaw = lerp(float(robot.get("yaw_start_rad", -0.05)), float(robot.get("yaw_goal_rad", -0.65)), nav)
    return x, y, yaw


def px_to_world_m(scenario: dict[str, Any], x: float, y: float) -> dict[str, float]:
    world = scenario.get("world") if isinstance(scenario.get("world"), dict) else {}
    origin_x, origin_y = pair(world.get("origin_px"), (140.0, 392.0))
    scale = float(world.get("scale_px_per_m", 300.0))
    return {
        "x": (x - origin_x) / scale,
        "y": (origin_y - y) / scale,
        "z": 0.0,
    }


def arm_reach(scenario: dict[str, Any], progress: float) -> float:
    timing_data = timing(scenario)
    start = float(timing_data.get("reach_start", 0.56))
    end = float(timing_data.get("reach_end", 0.72))
    return ease((progress - start) / (end - start) if end > start else progress)


def place_reach(scenario: dict[str, Any], progress: float) -> float:
    timing_data = timing(scenario)
    start = float(timing_data.get("place_start", 0.78))
    end = float(timing_data.get("place_end", 0.92))
    return ease((progress - start) / (end - start) if end > start else progress)


def object_state(scenario: dict[str, Any], progress: float) -> str:
    timing_data = timing(scenario)
    if progress >= float(timing_data.get("placed_after", 0.88)):
        return "placed"
    if progress >= float(timing_data.get("grasp_start", 0.70)):
        return "held"
    return "on_table"


def object_position_px(scenario: dict[str, Any], progress: float) -> tuple[float, float]:
    workspace = workspace_config(scenario)
    arm = arm_config(scenario)
    table_x, table_y = pair(workspace.get("object_start_px"), (712.0, 292.0))
    bin_x, bin_y = pair(workspace.get("bin_px"), (768.0, 320.0))
    base_x, base_y, _ = robot_pose_px(scenario, progress)
    carry_x, carry_y = pair(arm.get("tool_carry_offset_px"), (72.0, -34.0))
    carried_x = base_x + carry_x
    carried_y = base_y + carry_y

    state = object_state(scenario, progress)
    if state == "on_table":
        return table_x, table_y
    if state == "held":
        reach = arm_reach(scenario, progress)
        return lerp(table_x, carried_x, reach), lerp(table_y, carried_y, reach)
    place = place_reach(scenario, progress)
    return lerp(carried_x, bin_x, place), lerp(carried_y, bin_y, place)


def stream_sample(
    *,
    stream_id: str,
    semantic_type: str,
    source_message_type: str,
    event_time_ns: int,
    frame_id: str | None,
    payload_summary: dict[str, Any],
    sample_index: int,
    scenario: dict[str, Any],
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
            "scenario_id": scenario.get("scenario_id"),
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
    scenario: dict[str, Any],
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
        "attributes": {
            "scenario_id": scenario.get("scenario_id"),
            **attributes,
        },
    }


def camera_summary(scenario: dict[str, Any], progress: float, *, depth: bool = False) -> dict[str, Any]:
    camera = camera_config(scenario)
    visual = scenario.get("visual") if isinstance(scenario.get("visual"), dict) else {}
    height = int(camera.get("height", 90))
    width = int(camera.get("width", 160))
    canvas_width = float(visual.get("canvas_width", 960))
    canvas_height = float(visual.get("canvas_height", 620))
    object_x, object_y = object_position_px(scenario, progress)
    target_x = int(max(0, min(width - 1, (object_x / canvas_width) * width)))
    target_y = int(max(0, min(height - 1, (object_y / canvas_height) * height)))
    state = object_state(scenario, progress)

    if depth:
        background_start = int(camera.get("background_depth_start_mm", 1800))
        background_end = int(camera.get("background_depth_end_mm", 900))
        return {
            "height": height,
            "width": width,
            "encoding": "16UC1",
            "is_bigendian": 0,
            "step": width * 2,
            "data_len": height * width * 2,
            "synthetic_scene": {
                "target_centroid_px": {"x": target_x, "y": target_y},
                "target_depth_mm": int(camera.get("held_depth_mm" if state == "held" else "target_depth_mm", 620)),
                "background_depth_mm": int(lerp(background_start, background_end, ease(progress))),
                "object_state": state,
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
            "target_visible": state != "placed",
            "object_state": state,
            "progress_bar": progress,
        },
    }


def camera_info_summary(scenario: dict[str, Any]) -> dict[str, Any]:
    camera = camera_config(scenario)
    return {
        "height": int(camera.get("height", 90)),
        "width": int(camera.get("width", 160)),
        "distortion_model": "plumb_bob",
        "d_len": 0,
        "k_len": 9,
        "p_len": 12,
    }


def joint_summary(scenario: dict[str, Any], progress: float) -> dict[str, Any]:
    names = ["shoulder_pan", "shoulder_lift", "elbow", "wrist", "gripper_left", "gripper_right"]
    reach = arm_reach(scenario, progress)
    holding = object_state(scenario, progress) == "held"
    positions = [
        -0.22 * reach,
        -0.52 * reach,
        0.82 * reach,
        -0.34 * reach,
        0.0 if holding else 0.04,
        0.0 if holding else 0.04,
    ]
    return {
        "joint_count": len(names),
        "joint_names_sample": names,
        "position_sample": positions,
        "position_count": len(positions),
        "velocity_count": len(positions),
        "effort_count": len(positions),
    }


def odom_summary(scenario: dict[str, Any], progress: float) -> dict[str, Any]:
    x, y, yaw = robot_pose_px(scenario, progress)
    stage = stage_name(scenario, progress)
    return {
        "child_frame_id": "base_link",
        "position": px_to_world_m(scenario, x, y),
        "orientation": quaternion_from_yaw(yaw),
        "linear": {"x": 0.35 if stage == "navigate" else 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": -0.15 if stage == "navigate" else 0.0},
        "stage": stage,
    }


def tf_summary(scenario: dict[str, Any], event_time_ns: int, progress: float) -> dict[str, Any]:
    x, y, _ = robot_pose_px(scenario, progress)
    object_x, object_y = object_position_px(scenario, progress)
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
        "synthetic_base_translation": px_to_world_m(scenario, x, y),
        "synthetic_object_position": px_to_world_m(scenario, object_x, object_y),
    }


def goal_summary(scenario: dict[str, Any]) -> dict[str, Any]:
    goal = scenario.get("goal") if isinstance(scenario.get("goal"), dict) else {}
    workspace = workspace_config(scenario)
    return {
        "position": goal.get("position_m") or {"x": 1.6, "y": 0.0, "z": 0.0},
        "orientation": goal.get("orientation") or {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        "target_object": workspace.get("target_object", "orange_cube"),
        "scenario_id": scenario.get("scenario_id"),
    }


def emit_episode(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    scenario_timing = timing(scenario)
    duration_sec = args.duration_sec or float(scenario_timing.get("duration_sec", 16.0))
    rate_hz = args.rate_hz or float(scenario_timing.get("rate_hz", 12.0))
    diagnostics_period_sec = args.diagnostics_period_sec or float(scenario_timing.get("diagnostics_period_sec", 0.5))

    writer = JsonlWriter(args.output)
    period_ns = int(1_000_000_000 / rate_hz)
    sample_count = int(duration_sec * rate_hz)
    diagnostic_every = max(1, int(rate_hz * diagnostics_period_sec))
    goal_every = max(1, int(rate_hz))

    try:
        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "native_sim_start",
                "source": "romi_native_sim",
                "scenario": {
                    "scenario_id": scenario.get("scenario_id"),
                    "name": scenario.get("name"),
                    "path": str(args.scenario),
                },
                "duration_sec": duration_sec,
                "rate_hz": rate_hz,
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
                    payload_summary=camera_summary(scenario, progress),
                    sample_index=sample_index,
                    scenario=scenario,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.camera.depth",
                    semantic_type="depth_image",
                    source_message_type="romi.robotics.ImageSummary",
                    event_time_ns=event_time_ns,
                    frame_id="camera_depth_optical_frame",
                    payload_summary=camera_summary(scenario, progress, depth=True),
                    sample_index=sample_index,
                    scenario=scenario,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.camera.info",
                    semantic_type="camera_info",
                    source_message_type="romi.robotics.CameraInfoSummary",
                    event_time_ns=event_time_ns,
                    frame_id="camera_color_optical_frame",
                    payload_summary=camera_info_summary(scenario),
                    sample_index=sample_index,
                    scenario=scenario,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.joints.state",
                    semantic_type="joint_state",
                    source_message_type="romi.robotics.JointStateSummary",
                    event_time_ns=event_time_ns,
                    frame_id="base_link",
                    payload_summary=joint_summary(scenario, progress),
                    sample_index=sample_index,
                    scenario=scenario,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.base.odom",
                    semantic_type="odometry",
                    source_message_type="romi.robotics.OdometrySummary",
                    event_time_ns=event_time_ns,
                    frame_id="odom",
                    payload_summary=odom_summary(scenario, progress),
                    sample_index=sample_index,
                    scenario=scenario,
                )
            )
            writer.write(
                stream_sample(
                    stream_id="robot.frames.tf",
                    semantic_type="transform_tree",
                    source_message_type="romi.robotics.TransformTreeSummary",
                    event_time_ns=event_time_ns,
                    frame_id="map->odom",
                    payload_summary=tf_summary(scenario, event_time_ns, progress),
                    sample_index=sample_index,
                    scenario=scenario,
                )
            )

            if index % goal_every == 0:
                writer.write(
                    stream_sample(
                        stream_id="task.goal",
                        semantic_type="task_goal",
                        source_message_type="romi.robotics.PoseGoalSummary",
                        event_time_ns=event_time_ns,
                        frame_id=str((scenario.get("goal") or {}).get("frame_id", "map")),
                        payload_summary=goal_summary(scenario),
                        sample_index=(index // goal_every) + 1,
                        scenario=scenario,
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
                            "stage": stage_name(scenario, progress),
                            "streams": [
                                "robot.camera.rgb",
                                "robot.camera.depth",
                                "robot.camera.info",
                                "robot.joints.state",
                                "robot.base.odom",
                                "robot.frames.tf",
                            ],
                        },
                        scenario=scenario,
                    )
                )

        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "native_sim_stop",
                "source": "romi_native_sim",
                "scenario_id": scenario.get("scenario_id"),
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
    parser.add_argument("--scenario", type=Path, default=default_scenario_path(), help="Shared scenario JSON.")
    parser.add_argument("--duration-sec", type=float, default=None, help="Override scenario duration in seconds.")
    parser.add_argument("--rate-hz", type=float, default=None, help="Override scenario observation rate in Hz.")
    parser.add_argument("--diagnostics-period-sec", type=float, default=None, help="Override scenario diagnostic period.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.duration_sec is not None and args.duration_sec <= 0:
        raise ValueError("--duration-sec must be greater than zero")
    if args.rate_hz is not None and args.rate_hz <= 0:
        raise ValueError("--rate-hz must be greater than zero")
    if args.diagnostics_period_sec is not None and args.diagnostics_period_sec <= 0:
        raise ValueError("--diagnostics-period-sec must be greater than zero")
    return emit_episode(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
