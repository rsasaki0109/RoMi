#!/usr/bin/env python3
"""Minimal ROS2-to-RoMi JSONL bridge prototype.

This prototype is intentionally narrow. It maps selected ROS2 topics into RoMi
stream envelopes for the README navigation + manipulation demo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "0.1.0"
ROBOTICS_SCHEMA_ID = "romi.robotics.stream_metadata/0.1.0"
DIAGNOSTIC_SCHEMA_ID = "romi.core.diagnostic_event/0.1.0"


@dataclass(frozen=True)
class StreamConfig:
    stream_id: str
    semantic_type: str
    source_topic: str | None
    source_message_type: str
    clock_domain: str
    frame_id: str | None = None
    expected_rate_hz: float | None = None
    required: bool = False


@dataclass
class StreamState:
    config: StreamConfig
    count: int = 0
    last_event_time_ns: int | None = None
    last_receive_time_ns: int | None = None
    last_frame_id: str | None = None
    last_error: str | None = None
    gap_count: int = 0
    subscribers: list[Any] = field(default_factory=list)


class JsonlWriter:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.output_path.open("a", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        self._file.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
        self._file.write("\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def default_stream_map() -> Path:
    return repo_root_from_script() / "examples/navigation_manipulation_demo/stream-map.example.json"


def default_output() -> Path:
    return repo_root_from_script() / "examples/navigation_manipulation_demo/artifacts/ros2-bridge-events.jsonl"


def load_stream_configs(path: Path) -> list[StreamConfig]:
    data = json.loads(path.read_text(encoding="utf-8"))
    configs: list[StreamConfig] = []
    for item in data.get("streams", []):
        source_topic = item.get("source_topic")
        source_message_type = item.get("source_message_type")
        if not source_message_type:
            continue
        configs.append(
            StreamConfig(
                stream_id=item["stream_id"],
                semantic_type=item["semantic_type"],
                source_topic=source_topic,
                source_message_type=source_message_type,
                clock_domain=item.get("clock_domain", "unknown"),
                frame_id=item.get("frame_id"),
                expected_rate_hz=item.get("expected_rate_hz"),
                required=bool(item.get("required", False)),
            )
        )
    return configs


def import_ros2() -> dict[str, Any]:
    try:
        import rclpy
        from geometry_msgs.msg import PoseStamped, Twist
        from nav_msgs.msg import Odometry, Path as NavPath
        from rclpy.executors import ExternalShutdownException
        from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
        from sensor_msgs.msg import CameraInfo, Image, JointState, PointCloud2
        from tf2_msgs.msg import TFMessage
    except ImportError as exc:
        raise RuntimeError(
            "ROS2 Python modules are not available. Source a ROS2 environment "
            "before running this bridge prototype."
        ) from exc

    return {
        "rclpy": rclpy,
        "ExternalShutdownException": ExternalShutdownException,
        "QoSProfile": QoSProfile,
        "ReliabilityPolicy": ReliabilityPolicy,
        "DurabilityPolicy": DurabilityPolicy,
        "HistoryPolicy": HistoryPolicy,
        "message_types": {
            "sensor_msgs/msg/Image": Image,
            "sensor_msgs/msg/CameraInfo": CameraInfo,
            "sensor_msgs/msg/PointCloud2": PointCloud2,
            "sensor_msgs/msg/JointState": JointState,
            "nav_msgs/msg/Odometry": Odometry,
            "nav_msgs/msg/Path": NavPath,
            "geometry_msgs/msg/PoseStamped": PoseStamped,
            "geometry_msgs/msg/Twist": Twist,
            "tf2_msgs/msg/TFMessage": TFMessage,
        },
    }


def stamp_to_ns(stamp: Any) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def header_stamp_ns(msg: Any) -> int | None:
    header = getattr(msg, "header", None)
    stamp = getattr(header, "stamp", None)
    if stamp is None:
        return None
    return stamp_to_ns(stamp)


def header_frame_id(msg: Any) -> str | None:
    header = getattr(msg, "header", None)
    frame_id = getattr(header, "frame_id", None)
    if frame_id == "":
        return None
    return frame_id


def vector3_to_dict(value: Any) -> dict[str, float]:
    return {
        "x": float(getattr(value, "x", 0.0)),
        "y": float(getattr(value, "y", 0.0)),
        "z": float(getattr(value, "z", 0.0)),
    }


def quaternion_to_dict(value: Any) -> dict[str, float]:
    return {
        "x": float(getattr(value, "x", 0.0)),
        "y": float(getattr(value, "y", 0.0)),
        "z": float(getattr(value, "z", 0.0)),
        "w": float(getattr(value, "w", 1.0)),
    }


def summarize_message(msg: Any, message_type: str) -> dict[str, Any]:
    if message_type == "sensor_msgs/msg/Image":
        data = getattr(msg, "data", b"")
        return {
            "height": int(getattr(msg, "height", 0)),
            "width": int(getattr(msg, "width", 0)),
            "encoding": getattr(msg, "encoding", ""),
            "is_bigendian": int(getattr(msg, "is_bigendian", 0)),
            "step": int(getattr(msg, "step", 0)),
            "data_len": len(data),
        }

    if message_type == "sensor_msgs/msg/CameraInfo":
        return {
            "height": int(getattr(msg, "height", 0)),
            "width": int(getattr(msg, "width", 0)),
            "distortion_model": getattr(msg, "distortion_model", ""),
            "d_len": len(getattr(msg, "d", [])),
            "k_len": len(getattr(msg, "k", [])),
            "p_len": len(getattr(msg, "p", [])),
        }

    if message_type == "sensor_msgs/msg/PointCloud2":
        fields = [
            getattr(field, "name", "")
            for field in list(getattr(msg, "fields", []))[:16]
        ]
        data = getattr(msg, "data", b"")
        return {
            "height": int(getattr(msg, "height", 0)),
            "width": int(getattr(msg, "width", 0)),
            "fields": fields,
            "point_step": int(getattr(msg, "point_step", 0)),
            "row_step": int(getattr(msg, "row_step", 0)),
            "is_dense": bool(getattr(msg, "is_dense", False)),
            "data_len": len(data),
        }

    if message_type == "sensor_msgs/msg/JointState":
        names = list(getattr(msg, "name", []))
        return {
            "joint_count": len(names),
            "joint_names_sample": names[:12],
            "position_sample": [float(value) for value in list(getattr(msg, "position", []))[:12]],
            "position_count": len(getattr(msg, "position", [])),
            "velocity_count": len(getattr(msg, "velocity", [])),
            "effort_count": len(getattr(msg, "effort", [])),
        }

    if message_type == "nav_msgs/msg/Odometry":
        pose = getattr(getattr(msg, "pose", None), "pose", None)
        twist = getattr(getattr(msg, "twist", None), "twist", None)
        return {
            "child_frame_id": getattr(msg, "child_frame_id", ""),
            "position": vector3_to_dict(getattr(pose, "position", None)),
            "orientation": quaternion_to_dict(getattr(pose, "orientation", None)),
            "linear": vector3_to_dict(getattr(twist, "linear", None)),
            "angular": vector3_to_dict(getattr(twist, "angular", None)),
        }

    if message_type == "tf2_msgs/msg/TFMessage":
        transforms = list(getattr(msg, "transforms", []))
        frames = []
        for transform in transforms[:16]:
            frames.append(
                {
                    "parent_frame_id": getattr(transform.header, "frame_id", ""),
                    "child_frame_id": getattr(transform, "child_frame_id", ""),
                    "stamp_ns": stamp_to_ns(transform.header.stamp),
                }
            )
        return {
            "transform_count": len(transforms),
            "frames_sample": frames,
        }

    if message_type == "geometry_msgs/msg/PoseStamped":
        pose = getattr(msg, "pose", None)
        return {
            "position": vector3_to_dict(getattr(pose, "position", None)),
            "orientation": quaternion_to_dict(getattr(pose, "orientation", None)),
        }

    if message_type == "nav_msgs/msg/Path":
        poses = list(getattr(msg, "poses", []))
        return {
            "pose_count": len(poses),
            "first_pose_frame_id": header_frame_id(poses[0]) if poses else None,
        }

    if message_type == "geometry_msgs/msg/Twist":
        return {
            "linear": vector3_to_dict(getattr(msg, "linear", None)),
            "angular": vector3_to_dict(getattr(msg, "angular", None)),
        }

    return {"summary": "unsupported_message_summary"}


def tf_event_time_ns(msg: Any) -> int | None:
    transforms = list(getattr(msg, "transforms", []))
    if not transforms:
        return None
    return stamp_to_ns(transforms[0].header.stamp)


def tf_frame_id(msg: Any) -> str | None:
    transforms = list(getattr(msg, "transforms", []))
    if not transforms:
        return None
    parent = getattr(transforms[0].header, "frame_id", "")
    child = getattr(transforms[0], "child_frame_id", "")
    if parent and child:
        return f"{parent}->{child}"
    return parent or child or None


def qos_profile_for_config(config: StreamConfig, ros2: dict[str, Any]) -> Any:
    QoSProfile = ros2["QoSProfile"]
    ReliabilityPolicy = ros2["ReliabilityPolicy"]
    DurabilityPolicy = ros2["DurabilityPolicy"]
    HistoryPolicy = ros2["HistoryPolicy"]

    depth = 10
    if config.source_topic == "/tf_static":
        return QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=depth,
        )

    if config.semantic_type in {"rgb_image", "depth_image", "point_cloud"}:
        return QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=depth,
        )

    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
    )


def qos_metadata(config: StreamConfig) -> dict[str, Any]:
    if config.source_topic == "/tf_static":
        return {
            "reliability": "reliable",
            "durability": "transient_local",
            "history": "keep_last",
            "depth": 10,
        }
    if config.semantic_type in {"rgb_image", "depth_image", "point_cloud"}:
        return {
            "reliability": "best_effort",
            "durability": "volatile",
            "history": "keep_last",
            "depth": 10,
        }
    return {
        "reliability": "reliable",
        "durability": "volatile",
        "history": "keep_last",
        "depth": 10,
    }


def make_diagnostic(
    *,
    event_id: str,
    receive_time_ns: int,
    clock_domain: str,
    severity: str,
    message: str,
    attributes: dict[str, Any],
    category: str = "qos",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": DIAGNOSTIC_SCHEMA_ID,
        "kind": "diagnostic_event",
        "event_id": event_id,
        "time": {
            "event_time_ns": receive_time_ns,
            "clock_domain": clock_domain,
        },
        "severity": severity,
        "source": "ros2_bridge",
        "category": category,
        "message": message,
        "attributes": attributes,
    }


class RomiRos2Bridge:
    def __init__(
        self,
        *,
        node: Any,
        ros2: dict[str, Any],
        configs: list[StreamConfig],
        writer: JsonlWriter,
        diagnostics_period_sec: float,
    ) -> None:
        self.node = node
        self.ros2 = ros2
        self.writer = writer
        self.states = {config.stream_id: StreamState(config=config) for config in configs}
        self.message_types = ros2["message_types"]
        self.start_monotonic = time.monotonic()

        self.writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "bridge_start",
                "bridge": "rclpy_bridge",
                "node_name": node.get_name(),
                "stream_count": len(configs),
                "supported_message_types": sorted(self.message_types.keys()),
                "wall_time_ns": time.time_ns(),
            }
        )

        self._create_subscriptions()
        self.timer = node.create_timer(diagnostics_period_sec, self._emit_periodic_diagnostics)

    def _now_ns(self) -> int:
        return int(self.node.get_clock().now().nanoseconds)

    def _create_subscriptions(self) -> None:
        for state in self.states.values():
            config = state.config
            if not config.source_topic:
                continue

            message_cls = self.message_types.get(config.source_message_type)
            if message_cls is None:
                self._write_diagnostic(
                    state,
                    severity="warning",
                    message="Skipping unsupported ROS2 message type.",
                    attributes={
                        "stream_id": config.stream_id,
                        "source_topic": config.source_topic,
                        "source_message_type": config.source_message_type,
                    },
                )
                continue

            callback = self._callback_for(state)
            qos_profile = qos_profile_for_config(config, self.ros2)
            subscriber = self.node.create_subscription(
                message_cls,
                config.source_topic,
                callback,
                qos_profile,
            )
            state.subscribers.append(subscriber)
            self._write_diagnostic(
                state,
                severity="info",
                message="Subscribed to ROS2 topic.",
                attributes={
                    "stream_id": config.stream_id,
                    "source_topic": config.source_topic,
                    "source_message_type": config.source_message_type,
                    "qos": qos_metadata(config),
                },
            )

    def _callback_for(self, state: StreamState) -> Callable[[Any], None]:
        def callback(msg: Any) -> None:
            self._handle_message(state, msg)

        return callback

    def _handle_message(self, state: StreamState, msg: Any) -> None:
        config = state.config
        receive_time_ns = self._now_ns()
        if config.source_message_type == "tf2_msgs/msg/TFMessage":
            event_time_ns = tf_event_time_ns(msg) or receive_time_ns
            frame_id = tf_frame_id(msg) or config.frame_id
        else:
            event_time_ns = header_stamp_ns(msg) or receive_time_ns
            frame_id = header_frame_id(msg) or config.frame_id

        state.count += 1
        if state.last_event_time_ns is not None and config.expected_rate_hz:
            expected_period_ns = int(1_000_000_000 / config.expected_rate_hz)
            gap_ns = event_time_ns - state.last_event_time_ns
            if gap_ns > expected_period_ns * 3:
                state.gap_count += 1
                self._write_diagnostic(
                    state,
                    severity="warning",
                    message="Observed sample gap on ROS2 stream.",
                    attributes={
                        "stream_id": config.stream_id,
                        "source_topic": config.source_topic,
                        "expected_rate_hz": config.expected_rate_hz,
                        "observed_gap_ms": gap_ns / 1_000_000.0,
                    },
                )

        state.last_event_time_ns = event_time_ns
        state.last_receive_time_ns = receive_time_ns
        state.last_frame_id = frame_id

        envelope = {
            "schema_version": SCHEMA_VERSION,
            "schema_id": ROBOTICS_SCHEMA_ID,
            "kind": "stream_sample",
            "stream_id": config.stream_id,
            "semantic_type": config.semantic_type,
            "source_system": "ros2",
            "source_topic": config.source_topic,
            "source_message_type": config.source_message_type,
            "event_time_ns": event_time_ns,
            "bridge_receive_time_ns": receive_time_ns,
            "bridge_latency_ms": max(0.0, (receive_time_ns - event_time_ns) / 1_000_000.0),
            "clock_domain": config.clock_domain,
            "frame_id": frame_id,
            "qos": qos_metadata(config),
            "payload_summary": summarize_message(msg, config.source_message_type),
            "metadata": {
                "bridge": "rclpy_bridge",
                "sample_index": state.count,
            },
        }
        self.writer.write(envelope)

    def _write_diagnostic(
        self,
        state: StreamState,
        *,
        severity: str,
        message: str,
        attributes: dict[str, Any],
        category: str = "qos",
    ) -> None:
        config = state.config
        receive_time_ns = self._now_ns()
        event_id = f"ros2_bridge_{config.stream_id.replace('.', '_')}_{state.count}"
        self.writer.write(
            make_diagnostic(
                event_id=event_id,
                receive_time_ns=receive_time_ns,
                clock_domain=config.clock_domain,
                severity=severity,
                category=category,
                message=message,
                attributes=attributes,
            )
        )

    def _emit_periodic_diagnostics(self) -> None:
        now_ns = self._now_ns()
        for state in self.states.values():
            config = state.config
            if not config.required:
                continue

            if not config.source_topic:
                continue

            if state.count == 0:
                severity = "warning"
                message = "Required stream has not produced samples."
                attributes = {
                    "stream_id": config.stream_id,
                    "source_topic": config.source_topic,
                    "source_message_type": config.source_message_type,
                    "elapsed_sec": round(time.monotonic() - self.start_monotonic, 3),
                }
            else:
                severity = "info"
                age_ms = (
                    (now_ns - state.last_receive_time_ns) / 1_000_000.0
                    if state.last_receive_time_ns is not None
                    else None
                )
                message = "Required stream status."
                attributes = {
                    "stream_id": config.stream_id,
                    "source_topic": config.source_topic,
                    "source_message_type": config.source_message_type,
                    "sample_count": state.count,
                    "age_ms": age_ms,
                    "gap_count": state.gap_count,
                    "last_frame_id": state.last_frame_id,
                }

            self.writer.write(
                make_diagnostic(
                    event_id=f"ros2_bridge_status_{config.stream_id.replace('.', '_')}_{int(time.time())}",
                    receive_time_ns=now_ns,
                    clock_domain=config.clock_domain,
                    severity=severity,
                    category="stream",
                    message=message,
                    attributes=attributes,
                )
            )

    def close(self) -> None:
        self.writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "bridge_stop",
                "bridge": "rclpy_bridge",
                "wall_time_ns": time.time_ns(),
                "streams": {
                    stream_id: {
                        "sample_count": state.count,
                        "gap_count": state.gap_count,
                        "last_frame_id": state.last_frame_id,
                    }
                    for stream_id, state in self.states.items()
                },
            }
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RoMi ROS2 rclpy bridge prototype")
    parser.add_argument(
        "--stream-map",
        type=Path,
        default=default_stream_map(),
        help="Path to stream-map JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output(),
        help="Path to JSONL bridge output.",
    )
    parser.add_argument(
        "--diagnostics-period-sec",
        type=float,
        default=1.0,
        help="Periodic diagnostics interval.",
    )
    parser.add_argument(
        "--duration-sec",
        type=float,
        default=None,
        help="Optional run duration before graceful shutdown.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    configs = load_stream_configs(args.stream_map)
    ros2 = import_ros2()
    rclpy = ros2["rclpy"]
    ExternalShutdownException = ros2["ExternalShutdownException"]

    rclpy.init()
    node = rclpy.create_node("romi_ros2_bridge")
    writer = JsonlWriter(args.output)
    bridge = RomiRos2Bridge(
        node=node,
        ros2=ros2,
        configs=configs,
        writer=writer,
        diagnostics_period_sec=args.diagnostics_period_sec,
    )
    if args.duration_sec is not None:
        node.create_timer(args.duration_sec, rclpy.shutdown)

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        bridge.close()
        writer.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
