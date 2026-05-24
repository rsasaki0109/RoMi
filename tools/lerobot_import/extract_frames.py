#!/usr/bin/env python3
"""Extract an episode's camera frames from a LeRobot dataset into a compact NPZ.

Decodes the dataset video (software AV1 via ffmpeg) for one episode and saves the
RGB frames plus per-frame timestamps. The NPZ is a self-contained sidecar that
the ``vision_cnn`` policy backend reads for image observations, so the committed
held-out episode can be evaluated offline without re-decoding video.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import romi_lerobot_import as li  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="lerobot/pusht")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--episode", type=int, default=0)
    parser.add_argument("--output", required=True, type=Path, help="Output .npz path.")
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache" / "romi-lerobot")
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    import numpy as np

    frames = li.decode_episode_frames(
        repo_id=args.repo_id, revision=args.revision, episode=args.episode,
        cache_dir=args.cache_dir, offline=args.offline,
    )
    fps = float(li.load_info(repo_id=args.repo_id, revision=args.revision, cache_dir=args.cache_dir, offline=args.offline).get("fps", 10.0)) or 10.0
    timestamps = np.arange(len(frames), dtype=np.float32) / fps

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        frames=frames.astype(np.uint8),
        timestamps=timestamps,
        episode=np.int64(args.episode),
        fps=np.float32(fps),
    )
    print(f"wrote {args.output}: {len(frames)} frames {frames.shape[1:]} from {args.repo_id} ep{args.episode}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
