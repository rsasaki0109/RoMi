#!/usr/bin/env python3
"""Train a small neural behavior-cloning policy on LeRobot demonstrations.

Trains a gradient-descent MLP that maps the agent state to the demonstrated
action, using GPU when available. The learned weights are saved as a portable
JSON file (no pickle) that the ``neural_bc`` backend in romi_vla_policy.py loads
for deterministic CPU inference.

This is the learned-action core that modern policies (including VLAs) share. The
observation here is the 2D agent state, not pixels, so this is a behavior-cloning
policy rather than a vision-language model - but it is a real GPU-trained neural
network, and it plugs into the same eval harness as every other policy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lerobot_import"))
import romi_lerobot_import as li  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="lerobot/pusht")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--episodes", default="1-50", help="Training episodes, e.g. '1-50'.")
    parser.add_argument("--output", required=True, type=Path, help="Output weights JSON.")
    parser.add_argument("--hidden", type=int, default=64, help="Hidden layer width.")
    parser.add_argument("--epochs", type=int, default=400)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default=None, help="cuda or cpu. Defaults to cuda if available.")
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache" / "romi-lerobot")
    parser.add_argument("--offline", action="store_true")
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


def collect_pairs(args: argparse.Namespace) -> tuple[list[list[float]], list[list[float]], list[int]]:
    info = li.load_info(repo_id=args.repo_id, revision=args.revision, cache_dir=args.cache_dir, offline=args.offline)
    states: list[list[float]] = []
    actions: list[list[float]] = []
    used: list[int] = []
    for episode in parse_episodes(args.episodes):
        try:
            location = li.locate_episode(repo_id=args.repo_id, revision=args.revision, episode=episode, cache_dir=args.cache_dir, offline=args.offline)
            frames = li.load_episode_frames(repo_id=args.repo_id, revision=args.revision, episode=episode, location=location, info=info, cache_dir=args.cache_dir, offline=args.offline)
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
            states.append([state["x"], state["y"]])
            actions.append([action["x"], action["y"]])
        used.append(episode)
    if not states:
        raise ValueError("No training pairs collected.")
    return states, actions, used


def build_mlp(in_dim: int, hidden: int, out_dim: int):
    import torch.nn as nn

    return nn.Sequential(
        nn.Linear(in_dim, hidden), nn.ReLU(),
        nn.Linear(hidden, hidden), nn.ReLU(),
        nn.Linear(hidden, out_dim),
    )


def train(args: argparse.Namespace) -> int:
    import torch

    torch.manual_seed(args.seed)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    states, actions, used = collect_pairs(args)
    x = torch.tensor(states, dtype=torch.float32)
    y = torch.tensor(actions, dtype=torch.float32)
    x_mean, x_std = x.mean(0), x.std(0) + 1e-6
    y_mean, y_std = y.mean(0), y.std(0) + 1e-6
    xn = ((x - x_mean) / x_std).to(device)
    yn = ((y - y_mean) / y_std).to(device)

    model = build_mlp(2, args.hidden, 2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = torch.nn.MSELoss()

    model.train()
    final_loss = float("nan")
    for epoch in range(args.epochs):
        optimizer.zero_grad()
        loss = loss_fn(model(xn), yn)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.item())
        if (epoch + 1) % max(1, args.epochs // 5) == 0:
            print(f"epoch {epoch + 1}/{args.epochs} loss {final_loss:.5f}", file=sys.stderr)

    state_dict = {name: tensor.detach().cpu().tolist() for name, tensor in model.state_dict().items()}
    weights = {
        "schema_version": "0.1.0",
        "kind": "bc_mlp_weights",
        "dataset": args.repo_id,
        "arch": {"in_dim": 2, "hidden": args.hidden, "out_dim": 2, "activation": "relu"},
        "norm": {
            "state_mean": x_mean.tolist(), "state_std": x_std.tolist(),
            "action_mean": y_mean.tolist(), "action_std": y_std.tolist(),
        },
        "train": {"episodes": used, "pairs": len(states), "epochs": args.epochs, "seed": args.seed, "final_loss": round(final_loss, 6)},
        "state_dict": state_dict,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(weights, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output}: trained on {len(states)} pairs from {len(used)} episodes "
        f"({device}), final loss {final_loss:.5f}",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return train(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
