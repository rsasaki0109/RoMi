#!/usr/bin/env python3
"""Render the README animation from RoMi demo run artifacts."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


WIDTH = 960
HEIGHT = 540
FPS = 12
DURATION_SEC = 7.0
FRAME_COUNT = int(FPS * DURATION_SEC)

WORLD_BOX = (42, 132, 598, 450)
PANEL_BOX = (635, 132, 918, 450)


@dataclass(frozen=True)
class PoseSample:
    time_ns: int
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class JointSample:
    time_ns: int
    positions: tuple[float, ...]


@dataclass(frozen=True)
class DemoData:
    run_dir: Path
    episode_id: str
    source_label: str
    pipeline_label: str
    live_status: str
    episode_events: list[dict[str, Any]]
    replay_events: list[dict[str, Any]]
    policy_events: list[dict[str, Any]]
    report: dict[str, Any]
    stream_counts: dict[str, int]
    odom: list[PoseSample]
    joints: list[JointSample]
    goal: tuple[float, float, float] | None
    diagnostics_count: int
    observation_stream_count: int


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def default_gif_path() -> Path:
    return repo_root_from_script() / "docs/assets/romi-nav-manip-demo.gif"


def default_smoke_root() -> Path:
    return Path(__file__).resolve().parent / "artifacts/smoke"


def latest_run_dir() -> Path:
    smoke_root = default_smoke_root()
    candidates = [path for path in smoke_root.glob("*") if path.is_dir()]
    if not candidates:
        raise FileNotFoundError(
            "No demo run artifacts found. Run "
            "examples/navigation_manipulation_demo/run_smoke_demo.sh first."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
        ),
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


FONT_11 = font(11)
FONT_12 = font(12)
FONT_13 = font(13)
FONT_14 = font(14)
FONT_16 = font(16)
FONT_18_BOLD = font(18, bold=True)
FONT_22_BOLD = font(22, bold=True)
FONT_28_BOLD = font(28, bold=True)


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def ease(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def draw_round(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: str,
    outline: str | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_obj: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> str:
    if draw.textlength(text, font=font_obj) <= max_width:
        return text
    suffix = "..."
    available = max_width - int(draw.textlength(suffix, font=font_obj))
    if available <= 0:
        return suffix
    result = ""
    for char in text:
        if draw.textlength(result + char, font=font_obj) > available:
            break
        result += char
    return result + suffix


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            if isinstance(event, dict):
                events.append(event)
    return events


def event_time_ns(event: dict[str, Any]) -> int:
    value = event.get("event_time_ns")
    if isinstance(value, int):
        return value
    replay = event.get("replay")
    if isinstance(replay, dict) and isinstance(replay.get("original_event_time_ns"), int):
        return replay["original_event_time_ns"]
    payload = event.get("payload_summary")
    if isinstance(payload, dict):
        time_value = payload.get("time")
        if isinstance(time_value, dict) and isinstance(time_value.get("event_time_ns"), int):
            return time_value["event_time_ns"]
    return 0


def stream_samples(
    events: list[dict[str, Any]],
    stream_id: str | None = None,
) -> list[dict[str, Any]]:
    samples = [event for event in events if event.get("kind") == "stream_sample"]
    if stream_id is not None:
        samples = [event for event in samples if event.get("stream_id") == stream_id]
    return sorted(samples, key=event_time_ns)


def payload_summary(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload_summary")
    return payload if isinstance(payload, dict) else {}


def vector_from_payload(payload: dict[str, Any], key: str) -> tuple[float, float, float] | None:
    vector = payload.get(key)
    if not isinstance(vector, dict):
        return None
    try:
        return (
            float(vector.get("x", 0.0)),
            float(vector.get("y", 0.0)),
            float(vector.get("z", 0.0)),
        )
    except (TypeError, ValueError):
        return None


def yaw_from_quaternion(payload: dict[str, Any]) -> float:
    orientation = payload.get("orientation")
    if not isinstance(orientation, dict):
        return 0.0
    try:
        x = float(orientation.get("x", 0.0))
        y = float(orientation.get("y", 0.0))
        z = float(orientation.get("z", 0.0))
        w = float(orientation.get("w", 1.0))
    except (TypeError, ValueError):
        return 0.0
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def extract_odom(events: list[dict[str, Any]]) -> list[PoseSample]:
    poses: list[PoseSample] = []
    for event in stream_samples(events, "robot.base.odom"):
        payload = payload_summary(event)
        position = vector_from_payload(payload, "position")
        if position is None:
            continue
        poses.append(
            PoseSample(
                time_ns=event_time_ns(event),
                x=position[0],
                y=position[1],
                yaw=yaw_from_quaternion(payload),
            )
        )
    return poses


def extract_joints(events: list[dict[str, Any]]) -> list[JointSample]:
    joints: list[JointSample] = []
    for event in stream_samples(events, "robot.joints.state"):
        sample = payload_summary(event).get("position_sample")
        if not isinstance(sample, list):
            continue
        positions = []
        for value in sample[:8]:
            try:
                positions.append(float(value))
            except (TypeError, ValueError):
                positions.append(0.0)
        joints.append(JointSample(time_ns=event_time_ns(event), positions=tuple(positions)))
    return joints


def extract_goal(events: list[dict[str, Any]]) -> tuple[float, float, float] | None:
    goals = stream_samples(events, "task.goal")
    if not goals:
        return None
    return vector_from_payload(payload_summary(goals[-1]), "position")


def stream_count_map(report: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for stream in report.get("streams", []):
        if not isinstance(stream, dict):
            continue
        stream_id = stream.get("stream_id")
        if isinstance(stream_id, str):
            counts[stream_id] = int(stream.get("message_count") or 0)
    if counts:
        return counts

    for event in stream_samples(events):
        stream_id = event.get("stream_id")
        if isinstance(stream_id, str):
            counts[stream_id] = counts.get(stream_id, 0) + 1
    return counts


def load_demo_data(run_dir: Path) -> DemoData:
    episode_dir = run_dir / "episode"
    episode_events = load_jsonl(episode_dir / "events.jsonl")
    replay_events = load_jsonl(run_dir / "replay-events.jsonl")
    policy_events = load_jsonl(run_dir / "policy-events.jsonl")
    report = load_json(run_dir / "dataset-report/report.json")
    episode = load_json(episode_dir / "episode.json")

    if not episode_events:
        bridge_events = load_jsonl(run_dir / "ros2-bridge-events.jsonl")
        episode_events = bridge_events
    if not episode_events:
        source_events = load_jsonl(run_dir / "source-events.jsonl")
        episode_events = source_events

    if not episode_events:
        raise FileNotFoundError(f"No RoMi episode or bridge events found under {run_dir}")

    episode_id = (
        report.get("episode", {}).get("episode_id")
        or episode.get("episode_id")
        or run_dir.name
    )
    if not isinstance(episode_id, str):
        episode_id = run_dir.name

    diagnostics = report.get("diagnostics")
    diagnostics_count = 0
    if isinstance(diagnostics, dict):
        diagnostics_count = int(diagnostics.get("event_count") or 0)

    observation_window = report.get("observation_window")
    observation_stream_count = 0
    if isinstance(observation_window, dict):
        streams = observation_window.get("streams")
        if isinstance(streams, list):
            observation_stream_count = len(streams)

    source_systems = {
        str(event.get("source_system"))
        for event in stream_samples(episode_events)
        if event.get("source_system") is not None
    }
    if "romi_native_sim" in source_systems:
        source_label = "RoMi-native simulation"
        pipeline_label = "native simulation -> episode -> replay -> policy -> dataset"
        live_status = "NATIVE SIM SOURCE"
    elif "ros2" in source_systems:
        source_label = "ROS2 bridge"
        pipeline_label = "ROS2 bridge -> episode -> replay -> policy -> dataset"
        live_status = "LIVE ROS2 BRIDGE"
    else:
        source_label = "RoMi source"
        pipeline_label = "source -> episode -> replay -> policy -> dataset"
        live_status = "LIVE SOURCE"

    return DemoData(
        run_dir=run_dir,
        episode_id=episode_id,
        source_label=source_label,
        pipeline_label=pipeline_label,
        live_status=live_status,
        episode_events=episode_events,
        replay_events=replay_events,
        policy_events=policy_events,
        report=report,
        stream_counts=stream_count_map(report, episode_events),
        odom=extract_odom(episode_events),
        joints=extract_joints(episode_events),
        goal=extract_goal(episode_events),
        diagnostics_count=diagnostics_count,
        observation_stream_count=observation_stream_count,
    )


def sample_index(count: int, progress: float) -> int:
    if count <= 1:
        return 0
    return min(count - 1, int(round((count - 1) * clamp(progress))))


def current_pose(data: DemoData, progress: float) -> PoseSample:
    if data.odom:
        return data.odom[sample_index(len(data.odom), progress)]
    goal_x = data.goal[0] if data.goal else 1.0
    goal_y = data.goal[1] if data.goal else 0.0
    return PoseSample(0, goal_x * ease(progress), goal_y * ease(progress), 0.0)


def current_joints(data: DemoData, progress: float) -> tuple[float, ...]:
    if data.joints:
        return data.joints[sample_index(len(data.joints), progress)].positions
    reach = ease(progress)
    return (-0.25 * reach, -0.55 * reach, 0.85 * reach, -0.35 * reach)


def world_bounds(data: DemoData) -> tuple[float, float, float, float]:
    xs = [pose.x for pose in data.odom]
    ys = [pose.y for pose in data.odom]
    if data.goal is not None:
        xs.append(data.goal[0])
        ys.append(data.goal[1])
    if not xs:
        xs = [0.0, 1.6]
        ys = [-0.3, 0.5]

    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    if max_x - min_x < 0.5:
        center = (min_x + max_x) / 2.0
        min_x = center - 0.25
        max_x = center + 0.25
    if max_y - min_y < 0.5:
        center = (min_y + max_y) / 2.0
        min_y = center - 0.25
        max_y = center + 0.25

    pad_x = (max_x - min_x) * 0.18
    pad_y = (max_y - min_y) * 0.30
    return min_x - pad_x, max_x + pad_x, min_y - pad_y, max_y + pad_y


def world_mapper(data: DemoData) -> tuple[Any, Any]:
    x0, y0, x1, y1 = WORLD_BOX
    min_x, max_x, min_y, max_y = world_bounds(data)
    draw_w = x1 - x0 - 92
    draw_h = y1 - y0 - 86

    def sx(x: float) -> float:
        return x0 + 48 + ((x - min_x) / (max_x - min_x)) * draw_w

    def sy(y: float) -> float:
        return y1 - 46 - ((y - min_y) / (max_y - min_y)) * draw_h

    return sx, sy


def stream_count(data: DemoData, stream_id: str) -> int:
    return int(data.stream_counts.get(stream_id, 0))


def policy_count(data: DemoData) -> int:
    policy = data.report.get("policy")
    if isinstance(policy, dict):
        return int(policy.get("sample_count") or 0)
    return len(stream_samples(data.policy_events, "policy.proposed_action"))


def draw_world(draw: ImageDraw.ImageDraw, data: DemoData, progress: float) -> None:
    x0, y0, x1, y1 = WORLD_BOX
    draw_round(draw, WORLD_BOX, 18, "#121A20", "#2B3B46", 2)
    draw.text(
        (x0 + 20, y0 + 16),
        f"{data.source_label} observations recorded as RoMi streams",
        fill="#E8F5FA",
        font=FONT_16,
    )

    for x in range(x0 + 32, x1, 32):
        draw.line((x, y0 + 46, x, y1 - 18), fill="#1E2A32", width=1)
    for y in range(y0 + 64, y1, 32):
        draw.line((x0 + 16, y, x1 - 16, y), fill="#1E2A32", width=1)

    sx, sy = world_mapper(data)
    if data.goal is not None:
        gx, gy, _ = data.goal
        goal_x = sx(gx)
        goal_y = sy(gy)
        draw_round(
            draw,
            (int(goal_x - 76), int(goal_y - 50), int(goal_x + 86), int(goal_y + 62)),
            12,
            "#253024",
            "#73A33B",
            2,
        )
        draw.text((goal_x - 56, goal_y - 38), "task.goal", fill="#BCE784", font=FONT_12)
        draw_round(draw, (int(goal_x - 28), int(goal_y - 10), int(goal_x + 38), int(goal_y + 35)), 9, "#44523F", "#9AD66B", 2)
        draw.ellipse((goal_x - 7, goal_y - 31, goal_x + 17, goal_y - 7), fill="#FFB86B", outline="#FFE0B8", width=2)

    path = [(sx(pose.x), sy(pose.y)) for pose in data.odom]
    if len(path) >= 2:
        active_count = max(2, sample_index(len(path), progress) + 1)
        draw.line(path, fill="#425666", width=5)
        draw.line(path[:active_count], fill="#67E8F9", width=5)
        for px, py in path[:: max(1, len(path) // 8)]:
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill="#9FB5C2")

    pose = current_pose(data, progress)
    robot_x = sx(pose.x)
    robot_y = sy(pose.y)
    draw_robot(draw, data, progress, robot_x, robot_y, pose.yaw)

    draw.text((x0 + 20, y1 - 30), "odom / tf / joints / camera streams", fill="#7F929E", font=FONT_12)
    draw.text((x1 - 146, y1 - 30), f"{len(data.odom)} odom samples", fill="#A7B6C2", font=FONT_12)


def draw_robot(
    draw: ImageDraw.ImageDraw,
    data: DemoData,
    progress: float,
    x: float,
    y: float,
    yaw: float,
) -> None:
    base_w, base_h = 58, 42
    draw_round(
        draw,
        (int(x - base_w / 2), int(y - base_h / 2), int(x + base_w / 2), int(y + base_h / 2)),
        12,
        "#22313A",
        "#67E8F9",
        3,
    )
    draw.text((x - 20, y - 7), "base", fill="#E8F5FA", font=FONT_12)

    arrow_len = 35
    ax = x + math.cos(yaw) * arrow_len
    ay = y - math.sin(yaw) * arrow_len
    draw.line((x, y, ax, ay), fill="#BFF7FF", width=3)
    draw.ellipse((ax - 4, ay - 4, ax + 4, ay + 4), fill="#BFF7FF")

    joints = current_joints(data, progress)
    pan = joints[0] if len(joints) > 0 else 0.0
    lift = joints[1] if len(joints) > 1 else 0.0
    elbow_value = joints[2] if len(joints) > 2 else 0.0
    wrist_value = joints[3] if len(joints) > 3 else 0.0

    shoulder = (x + 20, y - 8)
    angle1 = -0.55 + pan * 0.5 + lift * 0.35
    angle2 = angle1 + 0.75 + elbow_value * 0.45
    angle3 = angle2 - 0.35 + wrist_value * 0.25
    elbow = (shoulder[0] + math.cos(angle1) * 52, shoulder[1] + math.sin(angle1) * 52)
    wrist = (elbow[0] + math.cos(angle2) * 48, elbow[1] + math.sin(angle2) * 48)
    tool = (wrist[0] + math.cos(angle3) * 24, wrist[1] + math.sin(angle3) * 24)

    draw.line((shoulder, elbow, wrist, tool), fill="#F8C471", width=7, joint="curve")
    for point, radius, color in [
        (shoulder, 7, "#F8C471"),
        (elbow, 6, "#F8C471"),
        (wrist, 6, "#FFE0A6"),
        (tool, 5, "#FFFFFF"),
    ]:
        px, py = point
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)

    if policy_count(data) > 0 and progress > 0.70:
        draw.text((x + 44, y - 74), "policy.proposed_action", fill="#FFDD99", font=FONT_13)
        draw.arc((tool[0] - 18, tool[1] - 18, tool[0] + 18, tool[1] + 18), start=210, end=330, fill="#FFFFFF", width=3)


def draw_panel(draw: ImageDraw.ImageDraw, data: DemoData, progress: float) -> None:
    x0, y0, x1, y1 = PANEL_BOX
    draw_round(draw, PANEL_BOX, 18, "#121A20", "#2B3B46", 2)
    draw.text((x0 + 20, y0 + 18), "Artifact-backed run", fill="#F3F7FA", font=FONT_18_BOLD)
    draw.text(
        (x0 + 20, y0 + 43),
        fit_text(draw, data.episode_id, FONT_12, x1 - x0 - 40),
        fill="#A7B6C2",
        font=FONT_12,
    )

    sample_count = len(stream_samples(data.episode_events))
    replay_count = len(stream_samples(data.replay_events))
    stats = [
        ("streams", len(data.stream_counts)),
        ("episode", sample_count),
        ("replay", replay_count),
        ("policy", policy_count(data)),
    ]
    for index, (label, value) in enumerate(stats):
        col = index % 2
        row = index // 2
        sx0 = x0 + 20 + col * 132
        sy0 = y0 + 70 + row * 43
        draw.text((sx0, sy0), str(value), fill="#E8F5FA", font=FONT_22_BOLD)
        draw.text((sx0, sy0 + 25), label, fill="#7F929E", font=FONT_11)

    stream_rows = [
        ("rgb", "robot.camera.rgb", "#67E8F9"),
        ("depth", "robot.camera.depth", "#7DD3FC"),
        ("joints", "robot.joints.state", "#F8C471"),
        ("odom", "robot.base.odom", "#9AD66B"),
        ("tf", "robot.frames.tf", "#BCA5FF"),
        ("goal", "task.goal", "#FFB86B"),
    ]
    max_count = max([stream_count(data, stream_id) for _, stream_id, _ in stream_rows] + [1])
    draw.text(
        (x0 + 20, y0 + 164),
        f"diagnostics {data.diagnostics_count} / window streams {data.observation_stream_count}",
        fill="#A7B6C2",
        font=FONT_11,
    )

    list_y = y0 + 192
    draw.text((x0 + 20, list_y - 20), "Recorded stream counts", fill="#A7B6C2", font=FONT_12)
    for index, (label, stream_id, color) in enumerate(stream_rows):
        count = stream_count(data, stream_id)
        y = list_y + index * 20
        draw.text((x0 + 20, y), label, fill="#E8F5FA" if count else "#64727B", font=FONT_12)
        draw_round(draw, (x0 + 76, y + 4, x0 + 222, y + 13), 5, "#1E2A32")
        if count:
            width = int(146 * count / max_count)
            draw_round(draw, (x0 + 76, y + 4, x0 + 76 + width, y + 13), 5, color)
        draw.text((x0 + 234, y), str(count), fill="#A7B6C2", font=FONT_11)


def draw_timeline(draw: ImageDraw.ImageDraw, progress: float) -> None:
    tx0, ty = 42, 484
    draw_round(draw, (tx0, ty, 918, ty + 26), 13, "#10161B", "#2B3B46", 1)
    fill_x = int(tx0 + 876 * progress)
    draw_round(draw, (tx0, ty, fill_x, ty + 26), 13, "#233D46")
    for label, pos in [
        ("source", 0.10),
        ("record", 0.30),
        ("replay", 0.50),
        ("policy", 0.68),
        ("report", 0.82),
    ]:
        x = int(tx0 + 876 * pos)
        draw.line((x, ty - 5, x, ty + 31), fill="#586A75", width=1)
        draw.text((x - 18, ty + 34), label, fill="#7F929E", font=FONT_12)


def draw_frame(data: DemoData, frame_index: int) -> Image.Image:
    progress = frame_index / max(1, FRAME_COUNT - 1)
    image = Image.new("RGB", (WIDTH, HEIGHT), "#0E1317")
    draw = ImageDraw.Draw(image)

    draw_round(draw, (18, 18, WIDTH - 18, HEIGHT - 18), 24, "#141B21", "#2B3B46", 2)
    draw.text((42, 48), "RoMi navigation + manipulation replay", fill="#F3F7FA", font=FONT_28_BOLD)
    draw.text(
        (42, 84),
        f"Rendered from RoMi artifacts: {data.pipeline_label}",
        fill="#A7B6C2",
        font=FONT_16,
    )

    if progress < 0.36:
        status = data.live_status
    elif progress < 0.64:
        status = "REPLAY"
    else:
        status = "POLICY + DATASET"
    draw_round(draw, (714, 48, 918, 82), 17, "#172B35", "#22D3EE", 2)
    draw.text((734, 55), status, fill="#BFF7FF", font=FONT_16)

    draw_world(draw, data, progress)
    draw_panel(draw, data, progress)
    draw_timeline(draw, progress)

    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the RoMi README animation from demo artifacts")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Smoke demo run directory. Defaults to the newest artifacts/smoke run.",
    )
    parser.add_argument("--gif", type=Path, default=default_gif_path(), help="Output GIF path.")
    parser.add_argument("--mp4", type=Path, default=None, help="Output MP4 path.")
    parser.add_argument("--skip-gif", action="store_true", help="Do not render GIF.")
    parser.add_argument("--skip-mp4", action="store_true", help="Do not render MP4.")
    return parser.parse_args()


def write_gif(frames: list[Image.Image], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / FPS),
        loop=0,
        optimize=True,
    )
    print(f"gif: {path}")


def write_mp4(frames: list[Image.Image], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        FPS,
        (WIDTH, HEIGHT),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open MP4 writer for {path}")
    for frame in frames:
        writer.write(cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
    writer.release()
    print(f"mp4: {path}")


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir if args.run_dir is not None else latest_run_dir()
    data = load_demo_data(run_dir)
    frames = [draw_frame(data, index) for index in range(FRAME_COUNT)]

    if not args.skip_gif:
        write_gif(frames, args.gif)

    if not args.skip_mp4:
        mp4_path = args.mp4 or (run_dir / "romi-nav-manip-demo.mp4")
        write_mp4(frames, mp4_path)

    print(f"source_run: {run_dir}")
    print(f"episode: {data.episode_id}")
    print(f"streams: {len(data.stream_counts)}")
    print(f"policy_samples: {policy_count(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
