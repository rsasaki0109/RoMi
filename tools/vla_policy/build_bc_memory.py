#!/usr/bin/env python3
"""Build a compact behavior-cloning memory from LeRobot demonstration episodes.

Collects (observation.state -> action) pairs from a set of training episodes and
writes them to a small JSON file. The ``bc_knn`` backend in romi_vla_policy.py
uses this memory as a non-parametric imitation policy: for a given agent state it
proposes a distance-weighted average of the nearest demonstrated actions.

Keep the training episodes disjoint from the episode you later evaluate on, so
the evaluation stays a genuine held-out counterfactual comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Reuse the LeRobot import logic (parquet over HTTP, no torch/lerobot).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lerobot_import"))
import romi_lerobot_import as li  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="lerobot/pusht", help="HuggingFace dataset repo id.")
    parser.add_argument("--revision", default="main", help="Dataset git revision.")
    parser.add_argument("--episodes", default="1-20", help="Training episodes, e.g. '1-20' or '1,2,5'.")
    parser.add_argument("--output", required=True, type=Path, help="Output bc_memory.json path.")
    parser.add_argument("--stride", type=int, default=2, help="Keep every Nth frame to keep the memory compact.")
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache" / "romi-lerobot")
    parser.add_argument("--offline", action="store_true", help="Use cached files only.")
    return parser.parse_args(argv)


def parse_episodes(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(range(int(lo), int(hi) + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))


def build(args: argparse.Namespace) -> int:
    info = li.load_info(
        repo_id=args.repo_id, revision=args.revision, cache_dir=args.cache_dir, offline=args.offline
    )
    states: list[list[float]] = []
    actions: list[list[float]] = []
    used: list[int] = []
    for episode in parse_episodes(args.episodes):
        try:
            location = li.locate_episode(
                repo_id=args.repo_id, revision=args.revision, episode=episode,
                cache_dir=args.cache_dir, offline=args.offline,
            )
            frames = li.load_episode_frames(
                repo_id=args.repo_id, revision=args.revision, episode=episode,
                location=location, info=info, cache_dir=args.cache_dir, offline=args.offline,
            )
        except (ValueError, RuntimeError) as exc:
            print(f"skip episode {episode}: {exc}", file=sys.stderr)
            continue
        for index, frame in enumerate(frames):
            if index % args.stride != 0:
                continue
            state = li.to_xy(frame.get("observation.state"))
            action = li.to_xy(frame.get("action"))
            if state is None or action is None:
                continue
            states.append([round(state["x"], 3), round(state["y"], 3)])
            actions.append([round(action["x"], 3), round(action["y"], 3)])
        used.append(episode)

    if not states:
        raise ValueError("No training pairs collected.")

    memory = {
        "schema_version": "0.1.0",
        "kind": "bc_memory",
        "dataset": args.repo_id,
        "train_episodes": used,
        "stride": args.stride,
        "pairs": len(states),
        "states": states,
        "actions": actions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(memory, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output}: {len(states)} (state,action) pairs from "
        f"{len(used)} episodes of {args.repo_id}",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return build(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
