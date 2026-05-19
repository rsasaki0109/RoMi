#!/usr/bin/env python3
"""Render a lightweight animated simulation asset for the RoMi README.

This is a visual communication asset for the current prototype pipeline. It is
not a physics simulator and is not part of the RoMi runtime.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


WIDTH = 960
HEIGHT = 540
FPS = 12
DURATION_SEC = 7.0
FRAME_COUNT = int(FPS * DURATION_SEC)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def default_gif_path() -> Path:
    return repo_root_from_script() / "docs/assets/romi-nav-manip-demo.gif"


def default_mp4_path() -> Path:
    return (
        repo_root_from_script()
        / "examples/navigation_manipulation_demo/artifacts/simulation/romi-nav-manip-demo.mp4"
    )


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


FONT_12 = font(12)
FONT_14 = font(14)
FONT_16 = font(16)
FONT_18_BOLD = font(18, bold=True)
FONT_22_BOLD = font(22, bold=True)
FONT_28_BOLD = font(28, bold=True)


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def lerp(a: float, b: float, value: float) -> float:
    return a + (b - a) * value


def draw_round(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_grid(draw: ImageDraw.ImageDraw) -> None:
    x0, y0, x1, y1 = 42, 128, 598, 450
    draw_round(draw, (x0, y0, x1, y1), 18, "#121A20", "#2B3B46", 2)
    for x in range(x0 + 32, x1, 32):
        draw.line((x, y0 + 10, x, y1 - 10), fill="#1E2A32", width=1)
    for y in range(y0 + 32, y1, 32):
        draw.line((x0 + 10, y, x1 - 10, y), fill="#1E2A32", width=1)

    # Work area and table.
    draw_round(draw, (405, 215, 555, 336), 14, "#253024", "#73A33B", 2)
    draw.text((424, 230), "manipulation area", fill="#BCE784", font=FONT_12)
    draw_round(draw, (455, 262, 525, 314), 10, "#44523F", "#9AD66B", 2)
    draw.text((463, 281), "target", fill="#ECFFD9", font=FONT_12)

    # Object.
    draw.ellipse((485, 238, 509, 262), fill="#FFB86B", outline="#FFE0B8", width=2)


def path_point(progress: float) -> tuple[float, float, float]:
    p = ease(progress)
    x = lerp(105, 430, p)
    y = 344 - 58 * math.sin(p * math.pi)
    angle = lerp(-0.1, -0.7, p)
    return x, y, angle


def draw_robot(draw: ImageDraw.ImageDraw, t: float) -> None:
    nav_progress = ease((t - 0.08) / 0.48)
    x, y, angle = path_point(nav_progress)

    # Path and replay trace.
    points = [path_point(i / 36.0)[:2] for i in range(37)]
    draw.line(points, fill="#425666", width=5)
    draw.line(points[: max(2, int(37 * nav_progress))], fill="#67E8F9", width=5)
    for px, py in points[::6]:
        draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill="#9FB5C2")

    # Robot base.
    base_w, base_h = 58, 42
    draw_round(draw, (int(x - base_w / 2), int(y - base_h / 2), int(x + base_w / 2), int(y + base_h / 2)), 12, "#22313A", "#67E8F9", 3)
    draw.ellipse((x - 20, y - 30, x - 6, y - 16), fill="#0F1418", outline="#B7D8E8", width=2)
    draw.ellipse((x + 6, y - 30, x + 20, y - 16), fill="#0F1418", outline="#B7D8E8", width=2)
    draw.text((x - 21, y - 7), "base", fill="#E8F5FA", font=FONT_12)

    # Arm.
    arm_progress = ease((t - 0.55) / 0.25)
    shoulder = (x + 20, y - 7)
    elbow = (lerp(shoulder[0] + 36, 462, arm_progress), lerp(shoulder[1] - 24, 254, arm_progress))
    wrist = (lerp(elbow[0] + 34, 492, arm_progress), lerp(elbow[1] - 10, 249, arm_progress))
    draw.line((shoulder, elbow, wrist), fill="#F8C471", width=7, joint="curve")
    draw.ellipse((shoulder[0] - 7, shoulder[1] - 7, shoulder[0] + 7, shoulder[1] + 7), fill="#F8C471")
    draw.ellipse((elbow[0] - 6, elbow[1] - 6, elbow[0] + 6, elbow[1] + 6), fill="#F8C471")
    draw.ellipse((wrist[0] - 6, wrist[1] - 6, wrist[0] + 6, wrist[1] + 6), fill="#FFE0A6")

    if t > 0.73:
        draw.arc((475, 227, 519, 271), start=210, end=330, fill="#FFFFFF", width=3)
        draw.text((418, 190), "policy.proposed_action", fill="#FFDD99", font=FONT_14)


def draw_panel(draw: ImageDraw.ImageDraw, t: float) -> None:
    x0, y0, x1, y1 = 635, 128, 918, 450
    draw_round(draw, (x0, y0, x1, y1), 18, "#121A20", "#2B3B46", 2)
    draw.text((x0 + 22, y0 + 22), "Inspectable runtime", fill="#F3F7FA", font=FONT_18_BOLD)

    nodes = [
        ("ROS2 bridge", 0.12, "#67E8F9"),
        ("episode recorder", 0.30, "#9AD66B"),
        ("replay source", 0.48, "#BCA5FF"),
        ("mock policy", 0.64, "#FFB86B"),
        ("dataset report", 0.78, "#F7A8C4"),
    ]
    for i, (label, threshold, color) in enumerate(nodes):
        y = y0 + 68 + i * 43
        active = t >= threshold
        fill = color if active else "#25313A"
        draw_round(draw, (x0 + 22, y, x0 + 52, y + 24), 8, fill, "#5A6A74", 1)
        draw.text((x0 + 64, y + 3), label, fill="#E8F5FA" if active else "#7F929E", font=FONT_14)
        if i < len(nodes) - 1:
            draw.line((x0 + 37, y + 26, x0 + 37, y + 40), fill="#455866", width=2)

    # Diagnostics meters.
    meter_y = y1 - 94
    draw.text((x0 + 22, meter_y), "latency / freshness", fill="#A7B6C2", font=FONT_12)
    latency = 0.25 + 0.16 * math.sin(t * math.tau * 2)
    freshness = ease((t - 0.28) / 0.45)
    draw_round(draw, (x0 + 22, meter_y + 22, x0 + 250, meter_y + 34), 6, "#1E2A32")
    draw_round(draw, (x0 + 22, meter_y + 22, int(x0 + 22 + 228 * latency), meter_y + 34), 6, "#67E8F9")
    draw_round(draw, (x0 + 22, meter_y + 48, x0 + 250, meter_y + 60), 6, "#1E2A32")
    draw_round(draw, (x0 + 22, meter_y + 48, int(x0 + 22 + 228 * freshness), meter_y + 60), 6, "#9AD66B")


def draw_frame(frame_index: int) -> Image.Image:
    t = frame_index / max(1, FRAME_COUNT - 1)
    image = Image.new("RGB", (WIDTH, HEIGHT), "#0E1317")
    draw = ImageDraw.Draw(image)

    draw_round(draw, (18, 18, WIDTH - 18, HEIGHT - 18), 24, "#141B21", "#2B3B46", 2)
    draw.text((42, 50), "RoMi navigation + manipulation demo", fill="#F3F7FA", font=FONT_28_BOLD)
    draw.text((42, 84), "ROS2 bridge -> record -> replay -> mock policy -> dataset report", fill="#A7B6C2", font=FONT_16)

    status = "LIVE" if t < 0.42 else "REPLAY" if t < 0.68 else "POLICY + DATASET"
    draw_round(draw, (742, 48, 918, 82), 17, "#172B35", "#22D3EE", 2)
    draw.text((764, 55), status, fill="#BFF7FF", font=FONT_16)

    draw_grid(draw)
    draw_robot(draw, t)
    draw_panel(draw, t)

    # Timeline.
    tx0, ty = 42, 484
    draw_round(draw, (tx0, ty, 918, ty + 26), 13, "#10161B", "#2B3B46", 1)
    fill_x = int(tx0 + 876 * t)
    draw_round(draw, (tx0, ty, fill_x, ty + 26), 13, "#233D46")
    for label, pos in [("bridge", 0.12), ("record", 0.30), ("replay", 0.48), ("policy", 0.64), ("report", 0.78)]:
        x = int(tx0 + 876 * pos)
        draw.line((x, ty - 5, x, ty + 31), fill="#586A75", width=1)
        draw.text((x - 18, ty + 34), label, fill="#7F929E", font=FONT_12)

    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the RoMi README simulation animation")
    parser.add_argument("--gif", type=Path, default=default_gif_path(), help="Output GIF path.")
    parser.add_argument("--mp4", type=Path, default=default_mp4_path(), help="Output MP4 path.")
    parser.add_argument("--skip-gif", action="store_true", help="Do not render GIF.")
    parser.add_argument("--skip-mp4", action="store_true", help="Do not render MP4.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frames = [draw_frame(i) for i in range(FRAME_COUNT)]

    if not args.skip_gif:
        args.gif.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            args.gif,
            save_all=True,
            append_images=frames[1:],
            duration=int(1000 / FPS),
            loop=0,
            optimize=True,
        )
        print(f"gif: {args.gif}")

    if not args.skip_mp4:
        args.mp4.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(args.mp4),
            cv2.VideoWriter_fourcc(*"mp4v"),
            FPS,
            (WIDTH, HEIGHT),
        )
        for frame in frames:
            writer.write(cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
        writer.release()
        print(f"mp4: {args.mp4}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
