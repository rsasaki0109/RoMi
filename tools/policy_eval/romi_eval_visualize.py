#!/usr/bin/env python3
"""Render a counterfactual policy evaluation report into a shareable animation.

Reads a ``romi.counterfactual_policy_eval`` JSON report (the artifact produced by
romi_policy_eval.py) and draws, over the replay timeline:

- the recorded expert goal trajectory,
- the policy's proposed goal trajectory,
- the per-step divergence between them,
- the action-error curve and a running agreement rate.

Output is an animated GIF (no ffmpeg required) plus a static poster PNG. The
visualization reads only the evaluation report, so the committed artifact is
enough to reproduce the figure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import json

import matplotlib

matplotlib.use("Agg")  # headless rendering

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

BG = "#0d1117"
PANEL = "#161b22"
EXPERT = "#3fb950"
PROPOSED = "#f0883e"
DIVERGE = "#f85149"
MUTED = "#8b949e"
TEXT = "#e6edf3"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path, help="policy_eval.json report.")
    parser.add_argument("--gif-output", type=Path, default=None, help="Animated GIF path.")
    parser.add_argument("--png-output", type=Path, default=None, help="Static poster PNG path.")
    parser.add_argument("--frames", type=int, default=72, help="Number of animation frames.")
    parser.add_argument("--fps", type=int, default=12, help="Frames per second.")
    return parser.parse_args(argv)


def bounds(points: list[tuple[float, float]], pad_ratio: float = 0.08) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    span = max(hi_x - lo_x, hi_y - lo_y) or 1.0
    pad = span * pad_ratio
    cx, cy = (lo_x + hi_x) / 2, (lo_y + hi_y) / 2
    half = span / 2 + pad
    return cx - half, cx + half, cy - half, cy + half


def render_frame(
    *,
    report: dict[str, Any],
    expert: np.ndarray,
    proposed: np.ndarray,
    errors: np.ndarray,
    times: np.ndarray,
    k: int,
    extent: tuple[float, float, float, float],
    tolerance: float,
) -> np.ndarray:
    fig = plt.figure(figsize=(9.0, 4.6), dpi=82, facecolor=BG)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.0], wspace=0.22, left=0.06, right=0.97, top=0.84, bottom=0.13)

    # --- left: goal-space trajectories ---
    ax = fig.add_subplot(grid[0, 0], facecolor=PANEL)
    lo_x, hi_x, lo_y, hi_y = extent
    ax.set_xlim(lo_x, hi_x)
    ax.set_ylim(hi_y, lo_y)  # invert y: dataset pixel origin is top-left
    ax.set_aspect("equal")
    ax.tick_params(colors=MUTED, labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#30363d")
    ax.set_title("goal space (pixels)", color=MUTED, fontsize=9, loc="left")

    upto = max(1, k + 1)
    ax.plot(expert[:upto, 0], expert[:upto, 1], color=EXPERT, lw=2.0, label="expert (recorded)")
    ax.plot(proposed[:upto, 0], proposed[:upto, 1], color=PROPOSED, lw=2.0, label="policy (proposed)")
    ax.scatter([expert[k, 0]], [expert[k, 1]], color=EXPERT, s=42, zorder=5, edgecolor=BG, linewidth=0.8)
    ax.scatter([proposed[k, 0]], [proposed[k, 1]], color=PROPOSED, s=42, zorder=5, edgecolor=BG, linewidth=0.8)
    ax.plot(
        [expert[k, 0], proposed[k, 0]],
        [expert[k, 1], proposed[k, 1]],
        color=DIVERGE,
        lw=1.6,
        ls=(0, (2, 2)),
        zorder=4,
    )
    ax.legend(loc="upper right", fontsize=7, facecolor=PANEL, edgecolor="#30363d", labelcolor=TEXT)

    # --- right: action error over replay ---
    ax2 = fig.add_subplot(grid[0, 1], facecolor=PANEL)
    ax2.set_xlim(float(times[0]), float(times[-1]) or 1.0)
    ax2.set_ylim(0, float(errors.max()) * 1.1 + 1e-6)
    ax2.tick_params(colors=MUTED, labelsize=7)
    for spine in ax2.spines.values():
        spine.set_color("#30363d")
    ax2.set_title("action error vs expert (px)", color=MUTED, fontsize=9, loc="left")
    ax2.set_xlabel("replay time (s)", color=MUTED, fontsize=8)
    ax2.axhline(tolerance, color=MUTED, lw=1.0, ls=(0, (3, 3)))
    ax2.text(float(times[-1]), tolerance, f" tol {tolerance:g}px", color=MUTED, fontsize=6.5, va="bottom", ha="right")
    ax2.fill_between(times[:upto], errors[:upto], color=PROPOSED, alpha=0.18)
    ax2.plot(times[:upto], errors[:upto], color=PROPOSED, lw=1.8)
    ax2.scatter([times[k]], [errors[k]], color=DIVERGE, s=36, zorder=5)

    agreement = float((errors[:upto] <= tolerance).mean()) * 100.0
    ax2.text(
        0.03, 0.93, f"t = {times[k]:.1f}s   error = {errors[k]:.0f}px   agreement = {agreement:.0f}%",
        transform=ax2.transAxes, color=TEXT, fontsize=8.5, va="top",
    )

    # --- header / footer ---
    fig.text(
        0.06, 0.93,
        f"RoMi · policy {report.get('policy_id')} ({report.get('backend')}) "
        f"vs recorded expert · {report.get('dataset')}",
        color=TEXT, fontsize=10.0, fontweight="bold",
    )
    fig.text(
        0.06, 0.025,
        "Replay an episode, run a policy, compare proposals to expert demonstrations — "
        "policy_authority: proposed_only   ·   actuator_authority: none",
        color=MUTED, fontsize=7.8,
    )

    fig.canvas.draw()
    image = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
    plt.close(fig)
    return image


def run(args: argparse.Namespace) -> int:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    samples = report.get("samples", [])
    if len(samples) < 2:
        raise ValueError("Report needs at least 2 samples to animate.")

    expert = np.array([[s["expert_goal"]["x"], s["expert_goal"]["y"]] for s in samples], dtype=float)
    proposed = np.array([[s["proposed_goal"]["x"], s["proposed_goal"]["y"]] for s in samples], dtype=float)
    errors = np.array([s["error_px"] for s in samples], dtype=float)
    times = np.array([s["time_sec"] for s in samples], dtype=float)
    tolerance = float(report.get("tolerance_px", 20.0))

    all_points = [tuple(p) for p in expert] + [tuple(p) for p in proposed]
    extent = bounds(all_points)

    n = len(samples)
    step_indices = sorted(set(int(round(i)) for i in np.linspace(0, n - 1, min(args.frames, n))))
    frames = [
        render_frame(
            report=report, expert=expert, proposed=proposed, errors=errors, times=times,
            k=k, extent=extent, tolerance=tolerance,
        )
        for k in step_indices
    ]
    frames.extend([frames[-1]] * max(1, args.fps))  # hold the final frame

    import imageio.v2 as imageio  # local import: optional dependency

    if args.gif_output is not None:
        args.gif_output.parent.mkdir(parents=True, exist_ok=True)
        imageio.mimsave(args.gif_output, frames, duration=1.0 / args.fps, loop=0)
        print(f"wrote {args.gif_output} ({len(frames)} frames)", file=sys.stderr)
    if args.png_output is not None:
        args.png_output.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(args.png_output, frames[len(step_indices) - 1])
        print(f"wrote {args.png_output}", file=sys.stderr)
    if args.gif_output is None and args.png_output is None:
        raise SystemExit("Nothing to do: pass --gif-output and/or --png-output.")
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
