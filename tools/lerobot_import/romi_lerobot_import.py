#!/usr/bin/env python3
"""Import a LeRobot dataset episode into a RoMi episode JSONL.

This adapter reads a LeRobot v3 dataset directly over HTTP (parquet only, no
torch or lerobot package required) and maps one episode into RoMi stream-sample
event envelopes.

The mapping keeps RoMi's existing action space: the agent pose becomes a
``robot.base.odom`` odometry stream, the recorded teleoperation/expert action
becomes an ``expert.action`` command stream tagged ``recorded_demonstration``,
and the dataset task becomes a ``task.goal`` stream. A downstream policy can
then propose ``navigate_to_goal`` actions and be compared counterfactually
against the recorded expert actions before any actuator is touched.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.1.0"
STREAM_SCHEMA_ID = "romi.core.stream_sample/0.1.0"
LIFECYCLE_SCHEMA_ID = "romi.core.lifecycle_event/0.1.0"

HF_BASE = "https://huggingface.co/datasets"


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

    def close(self) -> None:
        if self.path is not None:
            self.file.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a LeRobot dataset episode into a RoMi episode JSONL.",
    )
    parser.add_argument(
        "--repo-id",
        default="lerobot/pusht",
        help="HuggingFace dataset repo id. Defaults to lerobot/pusht.",
    )
    parser.add_argument(
        "--episode",
        type=int,
        default=0,
        help="Episode index to import. Defaults to 0.",
    )
    parser.add_argument(
        "--revision",
        default="main",
        help="Dataset git revision. Defaults to main.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output episode JSONL path. Defaults to stdout.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "romi-lerobot",
        help="Local cache directory for downloaded parquet/json files.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional cap on the number of frames emitted.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only cached files; never download.",
    )
    return parser.parse_args(argv)


def cache_fetch(
    *, repo_id: str, revision: str, rel_path: str, cache_dir: Path, offline: bool
) -> Path:
    """Return a local path to a dataset file, downloading it if needed."""
    local = cache_dir / repo_id / revision / rel_path
    if local.exists():
        return local
    if offline:
        raise FileNotFoundError(
            f"Offline mode but file not cached: {local}\n"
            f"Re-run without --offline to download {rel_path}."
        )
    url = f"{HF_BASE}/{repo_id}/resolve/{revision}/{rel_path}"
    local.parent.mkdir(parents=True, exist_ok=True)
    tmp = local.with_suffix(local.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            tmp.write_bytes(response.read())
    except Exception as exc:  # noqa: BLE001 - surface a clear message
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc
    tmp.replace(local)
    return local


def load_info(
    *, repo_id: str, revision: str, cache_dir: Path, offline: bool
) -> dict[str, Any]:
    path = cache_fetch(
        repo_id=repo_id,
        revision=revision,
        rel_path="meta/info.json",
        cache_dir=cache_dir,
        offline=offline,
    )
    return json.loads(path.read_text(encoding="utf-8"))


def locate_episode(
    *, repo_id: str, revision: str, episode: int, cache_dir: Path, offline: bool
) -> dict[str, Any]:
    """Find which data file holds an episode using the episodes metadata."""
    import pyarrow.parquet as pq  # local import: optional dependency

    rel = "meta/episodes/chunk-000/file-000.parquet"
    path = cache_fetch(
        repo_id=repo_id,
        revision=revision,
        rel_path=rel,
        cache_dir=cache_dir,
        offline=offline,
    )
    table = pq.read_table(
        path,
        columns=[
            "episode_index",
            "data/chunk_index",
            "data/file_index",
            "length",
            "tasks",
        ],
    )
    rows = table.to_pylist()
    for row in rows:
        if int(row["episode_index"]) == episode:
            tasks = row.get("tasks")
            task_text = None
            if isinstance(tasks, (list, tuple)) and tasks:
                task_text = str(tasks[0])
            elif isinstance(tasks, str):
                task_text = tasks
            return {
                "chunk_index": int(row["data/chunk_index"]),
                "file_index": int(row["data/file_index"]),
                "length": int(row["length"]),
                "task": task_text,
            }
    raise ValueError(
        f"Episode {episode} not found in {repo_id} (episodes: "
        f"{rows[0]['episode_index']}..{rows[-1]['episode_index']})."
    )


def load_episode_frames(
    *,
    repo_id: str,
    revision: str,
    episode: int,
    location: dict[str, Any],
    info: dict[str, Any],
    cache_dir: Path,
    offline: bool,
) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq  # local import: optional dependency

    data_template = info.get(
        "data_path", "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
    )
    rel = data_template.format(
        chunk_index=location["chunk_index"], file_index=location["file_index"]
    )
    path = cache_fetch(
        repo_id=repo_id,
        revision=revision,
        rel_path=rel,
        cache_dir=cache_dir,
        offline=offline,
    )
    table = pq.read_table(path)
    frames = [
        row for row in table.to_pylist() if int(row["episode_index"]) == episode
    ]
    frames.sort(key=lambda row: int(row["frame_index"]))
    return frames


def decode_episode_frames(
    *,
    repo_id: str,
    revision: str,
    episode: int,
    cache_dir: Path,
    offline: bool,
    video_key: str = "observation.image",
):
    """Decode an episode's camera frames from the dataset video via ffmpeg.

    Returns an ``(N, H, W, 3)`` uint8 numpy array of RGB frames for the episode,
    using software AV1 decoding (libdav1d) so it works without GPU video accel.
    Requires ffmpeg on PATH and numpy.
    """
    import shutil
    import subprocess

    import numpy as np
    import pyarrow.parquet as pq

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to decode dataset video frames.")

    info = load_info(repo_id=repo_id, revision=revision, cache_dir=cache_dir, offline=offline)
    shape = info["features"][video_key]["shape"]  # [H, W, C]
    height, width = int(shape[0]), int(shape[1])

    meta = cache_fetch(
        repo_id=repo_id, revision=revision,
        rel_path="meta/episodes/chunk-000/file-000.parquet",
        cache_dir=cache_dir, offline=offline,
    )
    cols = [
        "episode_index", "length",
        f"videos/{video_key}/chunk_index", f"videos/{video_key}/file_index",
        f"videos/{video_key}/from_timestamp", f"videos/{video_key}/to_timestamp",
    ]
    rows = pq.read_table(meta, columns=cols).to_pylist()
    row = next((r for r in rows if int(r["episode_index"]) == episode), None)
    if row is None:
        raise ValueError(f"Episode {episode} not found for video decode.")

    chunk = int(row[f"videos/{video_key}/chunk_index"])
    file_index = int(row[f"videos/{video_key}/file_index"])
    start = float(row[f"videos/{video_key}/from_timestamp"])
    end = float(row[f"videos/{video_key}/to_timestamp"])
    length = int(row["length"])

    video_template = info.get("video_path", "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4")
    rel = video_template.format(video_key=video_key, chunk_index=chunk, file_index=file_index)
    video = cache_fetch(repo_id=repo_id, revision=revision, rel_path=rel, cache_dir=cache_dir, offline=offline)

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-c:v", "libdav1d",
        "-i", str(video), "-ss", f"{start}", "-t", f"{max(end - start, 0.0) + 0.5}",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed: {result.stderr.decode()[:300]}")
    buffer = np.frombuffer(result.stdout, dtype=np.uint8)
    frame_bytes = height * width * 3
    frames = buffer[: (buffer.size // frame_bytes) * frame_bytes].reshape(-1, height, width, 3)
    return frames[:length]


def to_xy(value: Any) -> dict[str, float] | None:
    try:
        seq = list(value)
    except TypeError:
        return None
    if len(seq) < 2:
        return None
    return {"x": float(seq[0]), "y": float(seq[1])}


def odometry_sample(
    *, position: dict[str, float], event_time_ns: int, frame_id: str, sample_index: int
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": STREAM_SCHEMA_ID,
        "kind": "stream_sample",
        "stream_id": "robot.base.odom",
        "semantic_type": "odometry",
        "source_system": "dataset",
        "source_topic": None,
        "source_message_type": "lerobot/observation.state",
        "event_time_ns": event_time_ns,
        "clock_domain": "episode_time",
        "frame_id": frame_id,
        "payload_summary": {
            "position": {"x": position["x"], "y": position["y"], "z": 0.0},
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
            "child_frame_id": "base_link",
        },
        "metadata": {
            "authority": "observation_only",
            "sample_index": sample_index,
            "source": "lerobot_import",
        },
    }


def expert_action_sample(
    *,
    goal: dict[str, float],
    raw_action: list[float],
    event_time_ns: int,
    frame_id: str,
    sample_index: int,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": STREAM_SCHEMA_ID,
        "kind": "stream_sample",
        "stream_id": "expert.action",
        "semantic_type": "command",
        "source_system": "dataset",
        "source_topic": None,
        "source_message_type": "lerobot/action",
        "event_time_ns": event_time_ns,
        "clock_domain": "episode_time",
        "frame_id": frame_id,
        "payload_summary": {
            "target": "base",
            "action_type": "navigate_to_goal",
            "values": {
                "goal_position": {"x": goal["x"], "y": goal["y"]},
                "raw_action": raw_action,
            },
            "authority": "recorded_demonstration",
        },
        "metadata": {
            "authority": "recorded_demonstration",
            "sample_index": sample_index,
            "source": "lerobot_import",
        },
    }


def task_goal_sample(
    *, task: str | None, frame_id: str, repo_id: str, episode: int
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": STREAM_SCHEMA_ID,
        "kind": "stream_sample",
        "stream_id": "task.goal",
        "semantic_type": "task_goal",
        "source_system": "dataset",
        "source_topic": None,
        "source_message_type": "lerobot/task",
        "event_time_ns": 0,
        "clock_domain": "episode_time",
        "frame_id": frame_id,
        "payload_summary": {
            "task_text": task or "unspecified",
            "dataset": repo_id,
            "episode_index": episode,
        },
        "metadata": {
            "authority": "observation_only",
            "sample_index": 0,
            "source": "lerobot_import",
        },
    }


def run_import(args: argparse.Namespace) -> int:
    info = load_info(
        repo_id=args.repo_id,
        revision=args.revision,
        cache_dir=args.cache_dir,
        offline=args.offline,
    )
    location = locate_episode(
        repo_id=args.repo_id,
        revision=args.revision,
        episode=args.episode,
        cache_dir=args.cache_dir,
        offline=args.offline,
    )
    frames = load_episode_frames(
        repo_id=args.repo_id,
        revision=args.revision,
        episode=args.episode,
        location=location,
        info=info,
        cache_dir=args.cache_dir,
        offline=args.offline,
    )
    if args.max_frames is not None:
        frames = frames[: args.max_frames]
    if not frames:
        raise ValueError(f"Episode {args.episode} produced no frames.")

    fps = float(info.get("fps", 10.0)) or 10.0
    frame_id = f"{args.repo_id.split('/')[-1]}_pixel"
    episode_id = f"lerobot_{args.repo_id.split('/')[-1]}_ep{args.episode:06d}"
    writer = JsonlWriter(args.output)

    try:
        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "schema_id": LIFECYCLE_SCHEMA_ID,
                "kind": "episode_start",
                "episode_id": episode_id,
                "dataset": args.repo_id,
                "episode_index": args.episode,
                "fps": fps,
                "frame_count": len(frames),
                "task": location.get("task"),
                "action_space": "navigate_to_goal_2d_pixel",
                "clock_domain": "episode_time",
                "wall_time_ns": time.time_ns(),
            }
        )
        writer.write(
            task_goal_sample(
                task=location.get("task"),
                frame_id=frame_id,
                repo_id=args.repo_id,
                episode=args.episode,
            )
        )

        for index, frame in enumerate(frames):
            timestamp = float(frame.get("timestamp", index / fps))
            event_time_ns = int(round(timestamp * 1_000_000_000))
            state_xy = to_xy(frame.get("observation.state"))
            action_seq = list(frame.get("action", []))
            action_xy = to_xy(action_seq)
            if state_xy is not None:
                writer.write(
                    odometry_sample(
                        position=state_xy,
                        event_time_ns=event_time_ns,
                        frame_id=frame_id,
                        sample_index=index + 1,
                    )
                )
            if action_xy is not None:
                writer.write(
                    expert_action_sample(
                        goal=action_xy,
                        raw_action=[float(v) for v in action_seq],
                        event_time_ns=event_time_ns,
                        frame_id=frame_id,
                        sample_index=index + 1,
                    )
                )

        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "schema_id": LIFECYCLE_SCHEMA_ID,
                "kind": "episode_stop",
                "episode_id": episode_id,
                "dataset": args.repo_id,
                "episode_index": args.episode,
                "frame_count": len(frames),
                "wall_time_ns": time.time_ns(),
            }
        )
    finally:
        writer.close()

    print(
        f"Imported {len(frames)} frames from {args.repo_id} episode "
        f"{args.episode} -> {args.output or 'stdout'}",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run_import(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
