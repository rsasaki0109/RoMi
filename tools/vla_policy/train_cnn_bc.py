#!/usr/bin/env python3
"""Train a small CNN vision policy (image -> action) on LeRobot demonstrations.

This is the vision counterpart of train_bc_mlp.py: instead of the 2D agent state,
it consumes the camera frame and regresses the demonstrated action, trained by
gradient descent on GPU when available. It is a real vision behavior-cloning
policy - the "V" that a full VLA also uses - though it is not language-conditioned.

Weights are saved as a portable NPZ (state-dict arrays + normalization) that the
``vision_cnn`` backend in romi_vla_policy.py loads for deterministic CPU inference.
The CNN architecture in build_cnn() must stay identical here and in that backend.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lerobot_import"))
import romi_lerobot_import as li  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="lerobot/pusht")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--episodes", default="1-30", help="Training episodes, e.g. '1-30'.")
    parser.add_argument("--output", required=True, type=Path, help="Output weights NPZ.")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default=None, help="cuda or cpu. Defaults to cuda if available.")
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


def build_cnn():
    """Vision policy network. MUST match the vision_cnn backend exactly."""
    import torch.nn as nn

    return nn.Sequential(
        nn.Conv2d(3, 16, 5, stride=2, padding=2), nn.ReLU(),
        nn.Conv2d(16, 32, 5, stride=2, padding=2), nn.ReLU(),
        nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(),
        nn.AdaptiveAvgPool2d(4),
        nn.Flatten(),
        nn.Linear(64 * 4 * 4, 64), nn.ReLU(),
        nn.Linear(64, 2),
    )


def collect(args: argparse.Namespace):
    import numpy as np

    info = li.load_info(repo_id=args.repo_id, revision=args.revision, cache_dir=args.cache_dir, offline=args.offline)
    images: list = []
    actions: list = []
    used: list[int] = []
    for episode in parse_episodes(args.episodes):
        try:
            frames = li.decode_episode_frames(repo_id=args.repo_id, revision=args.revision, episode=episode, cache_dir=args.cache_dir, offline=args.offline)
            location = li.locate_episode(repo_id=args.repo_id, revision=args.revision, episode=episode, cache_dir=args.cache_dir, offline=args.offline)
            data = li.load_episode_frames(repo_id=args.repo_id, revision=args.revision, episode=episode, location=location, info=info, cache_dir=args.cache_dir, offline=args.offline)
        except (ValueError, RuntimeError) as exc:
            print(f"skip episode {episode}: {exc}", file=sys.stderr)
            continue
        n = min(len(frames), len(data))
        for i in range(n):
            act = li.to_xy(data[i].get("action"))
            if act is None:
                continue
            images.append(frames[i])
            actions.append([act["x"], act["y"]])
        used.append(episode)
        print(f"  episode {episode}: {n} frames", file=sys.stderr)
    if not images:
        raise ValueError("No training frames collected.")
    return np.asarray(images, dtype=np.float32), np.asarray(actions, dtype=np.float32), used


def train(args: argparse.Namespace) -> int:
    import numpy as np
    import torch

    torch.manual_seed(args.seed)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    images, actions, used = collect(args)
    x = torch.from_numpy(images).permute(0, 3, 1, 2) / 255.0  # (N,3,H,W) in [0,1]
    y = torch.from_numpy(actions)
    y_mean, y_std = y.mean(0), y.std(0) + 1e-6
    yn = (y - y_mean) / y_std

    model = build_cnn().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = torch.nn.MSELoss()

    n = x.shape[0]
    model.train()
    final_loss = float("nan")
    for epoch in range(args.epochs):
        perm = torch.randperm(n)
        epoch_loss = 0.0
        for start in range(0, n, args.batch_size):
            idx = perm[start : start + args.batch_size]
            xb = x[idx].to(device)
            yb = yn[idx].to(device)
            optimizer.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.item()) * len(idx)
        final_loss = epoch_loss / n
        if (epoch + 1) % max(1, args.epochs // 8) == 0:
            print(f"epoch {epoch + 1}/{args.epochs} loss {final_loss:.5f}", file=sys.stderr)

    state = {name: tensor.detach().cpu().numpy() for name, tensor in model.state_dict().items()}
    arrays = {f"param::{name}": value for name, value in state.items()}
    arrays["action_mean"] = y_mean.numpy()
    arrays["action_std"] = y_std.numpy()
    arrays["meta_episodes"] = np.asarray(used, dtype=np.int64)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **arrays)
    print(
        f"wrote {args.output}: trained on {n} frames from {len(used)} episodes "
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
