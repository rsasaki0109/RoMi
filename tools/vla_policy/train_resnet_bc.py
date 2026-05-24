#!/usr/bin/env python3
"""Train a vision policy on top of a pretrained ResNet-18 backbone.

Uses a real pretrained foundation vision model (torchvision ResNet-18, ImageNet
weights) as a frozen feature extractor, and trains a small action head on
demonstration frames by gradient descent on GPU. This is the pretrained vision
encoder a VLA also relies on; only the tiny action head is learned and saved, so
the committed weights stay small (the backbone is downloaded at inference).

The backbone identity is recorded in the weights so the vision_resnet backend in
romi_vla_policy.py reconstructs the exact same frozen encoder.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lerobot_import"))
import romi_lerobot_import as li  # noqa: E402

BACKBONE = "resnet18"
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="lerobot/pusht")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--episodes", default="1-30")
    parser.add_argument("--output", required=True, type=Path, help="Output head weights NPZ.")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default=None)
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


def build_backbone(device):
    import torch.nn as nn
    import torchvision

    weights = torchvision.models.ResNet18_Weights.IMAGENET1K_V1
    model = torchvision.models.resnet18(weights=weights)
    model.fc = nn.Identity()  # 512-d features
    model.eval().to(device)
    for param in model.parameters():
        param.requires_grad_(False)
    return model


def build_head():
    import torch.nn as nn

    return nn.Sequential(nn.Linear(512, 128), nn.ReLU(), nn.Linear(128, 2))


def collect(args):
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


def encode_features(backbone, images, device, torch):
    """Run frozen backbone over images to 512-d features (batched, no grad)."""
    mean = torch.tensor(IMAGENET_MEAN, device=device).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD, device=device).view(1, 3, 1, 1)
    feats = []
    with torch.no_grad():
        for start in range(0, images.shape[0], 256):
            batch = images[start : start + 256].to(device)
            batch = (batch - mean) / std
            feats.append(backbone(batch).cpu())
    return torch.cat(feats, dim=0)


def train(args) -> int:
    import numpy as np
    import torch

    torch.manual_seed(args.seed)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    images_np, actions_np, used = collect(args)
    images = torch.from_numpy(images_np).permute(0, 3, 1, 2) / 255.0
    actions = torch.from_numpy(actions_np)
    y_mean, y_std = actions.mean(0), actions.std(0) + 1e-6
    yn = (actions - y_mean) / y_std

    backbone = build_backbone(device)
    features = encode_features(backbone, images, device, torch).to(device)
    targets = yn.to(device)

    head = build_head().to(device)
    optimizer = torch.optim.Adam(head.parameters(), lr=args.lr)
    loss_fn = torch.nn.MSELoss()

    head.train()
    final_loss = float("nan")
    for epoch in range(args.epochs):
        optimizer.zero_grad()
        loss = loss_fn(head(features), targets)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.item())
        if (epoch + 1) % max(1, args.epochs // 6) == 0:
            print(f"epoch {epoch + 1}/{args.epochs} loss {final_loss:.5f}", file=sys.stderr)

    state = {f"param::{name}": value.detach().cpu().numpy() for name, value in head.state_dict().items()}
    state["action_mean"] = y_mean.numpy()
    state["action_std"] = y_std.numpy()
    state["meta_episodes"] = np.asarray(used, dtype=np.int64)
    state["backbone"] = np.asarray(BACKBONE)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **state)
    print(
        f"wrote {args.output}: trained head on {features.shape[0]} frames from {len(used)} episodes "
        f"({device}, frozen {BACKBONE} backbone), final loss {final_loss:.5f}",
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
