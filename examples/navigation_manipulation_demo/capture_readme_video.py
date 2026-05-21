#!/usr/bin/env python3
"""Capture the RoMi 2D simulator into README-ready media assets."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

websocket = None


def require_websocket() -> object:
    global websocket
    if websocket is not None:
        return websocket
    try:
        import websocket as websocket_module
    except ImportError as exc:  # pragma: no cover - optional local capture dependency.
        raise SystemExit(
            "capture_readme_video.py requires browser capture dependencies. "
            "Install them with: python -m pip install -r requirements-browser.txt"
        ) from exc
    websocket = websocket_module
    return websocket_module


class CdpClient:
    def __init__(self, websocket_url: str) -> None:
        websocket_module = require_websocket()
        self._socket = websocket_module.create_connection(websocket_url, timeout=30)
        self._next_id = 1

    def close(self) -> None:
        self._socket.close()

    def send(self, method: str, params: dict | None = None, session_id: str | None = None) -> dict:
        message_id = self._next_id
        self._next_id += 1
        message = {"id": message_id, "method": method, "params": params or {}}
        if session_id:
            message["sessionId"] = session_id
        self._socket.send(json.dumps(message))

        while True:
            response = json.loads(self._socket.recv())
            if response.get("id") != message_id:
                continue
            if "error" in response:
                raise RuntimeError(f"CDP {method} failed: {response['error']}")
            return response.get("result", {})


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    default_asset_dir = repo_root / "docs" / "assets"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fps", type=int, default=12, help="Output video frame rate.")
    parser.add_argument("--video-duration-sec", type=float, default=12.0, help="Encoded video duration.")
    parser.add_argument("--viewport", default="1280x800", help="Browser viewport, for example 1280x800.")
    parser.add_argument("--mp4", type=Path, default=default_asset_dir / "romi-2d-nav-manip-demo.mp4")
    parser.add_argument("--webp", type=Path, default=default_asset_dir / "romi-2d-nav-manip-demo.webp")
    parser.add_argument("--poster", type=Path, default=default_asset_dir / "romi-2d-nav-manip-demo-poster.png")
    parser.add_argument("--keep-frames", action="store_true", help="Keep intermediate PNG frames under artifacts/.")
    parser.add_argument("--chrome-bin", default=default_chrome_bin(), help="Chrome or Chromium executable.")
    return parser.parse_args()


def default_chrome_bin() -> str:
    path_bin = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")
    if path_bin:
        return path_bin

    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return "google-chrome"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_json(url: str, timeout_sec: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout_sec
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - polling a local process.
            last_error = exc
            time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def wait_for_http(url: str, timeout_sec: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_sec
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001 - polling a local process.
            last_error = exc
            time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def ffmpeg_bin() -> str:
    path_bin = shutil.which("ffmpeg")
    if path_bin:
        return path_bin
    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - optional local capture dependency.
        raise SystemExit(
            "capture_readme_video.py requires ffmpeg on PATH or the imageio-ffmpeg "
            "Python package for media encoding. Install local capture dependencies "
            "with: python -m pip install -r requirements-browser.txt"
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str]) -> None:
    subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", *args], check=True)


def require_browser_executable(chrome_bin: str) -> None:
    if Path(chrome_bin).is_file() or shutil.which(chrome_bin):
        return
    raise SystemExit(
        "Could not find Chrome or Chromium. Install Chrome/Chromium, or pass "
        "--chrome-bin with the executable path."
    )


def file_size(path: Path) -> str:
    size = path.stat().st_size
    for unit in ["B", "KiB", "MiB"]:
        if size < 1024 or unit == "MiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024
    return f"{path.stat().st_size} B"


def display_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def main() -> int:
    args = parse_args()
    width, height = [int(part) for part in args.viewport.lower().split("x", maxsplit=1)]
    repo_root = Path(__file__).resolve().parents[2]
    example_dir = Path(__file__).resolve().parent
    artifact_dir = example_dir / "artifacts" / "readme_capture"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    server_port = free_port()
    debug_port = free_port()
    url = f"http://127.0.0.1:{server_port}/romi_2d_sim/?capture=readme"
    frame_count = max(2, int(round(args.fps * args.video_duration_sec)))
    require_browser_executable(args.chrome_bin)

    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(server_port), "--bind", "127.0.0.1", "--directory", str(example_dir)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    chrome_profile = tempfile.TemporaryDirectory(prefix="romi-chrome-profile-")
    chrome = subprocess.Popen(
        [
            args.chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={chrome_profile.name}",
            f"--window-size={width},{height}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    frame_dir_ctx = tempfile.TemporaryDirectory(prefix="frames-", dir=artifact_dir)
    frame_dir = Path(frame_dir_ctx.name)
    cdp: CdpClient | None = None

    try:
        wait_for_http(url)
        version = wait_for_json(f"http://127.0.0.1:{debug_port}/json/version")
        cdp = CdpClient(version["webSocketDebuggerUrl"])
        target = cdp.send("Target.createTarget", {"url": "about:blank"})
        session_id = cdp.send("Target.attachToTarget", {"targetId": target["targetId"], "flatten": True})["sessionId"]

        cdp.send("Page.enable", session_id=session_id)
        cdp.send("Runtime.enable", session_id=session_id)
        cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
            session_id=session_id,
        )
        cdp.send("Page.navigate", {"url": url}, session_id=session_id)

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = cdp.send(
                "Runtime.evaluate",
                {"expression": "Boolean(window.romiCapture && window.romiCapture.ready())", "returnByValue": True},
                session_id=session_id,
            )
            if result.get("result", {}).get("value") is True:
                break
            time.sleep(0.1)
        else:
            raise TimeoutError("RoMi simulator did not become capture-ready.")

        duration_result = cdp.send(
            "Runtime.evaluate",
            {"expression": "window.romiCapture.duration()", "returnByValue": True},
            session_id=session_id,
        )
        sim_duration = float(duration_result["result"]["value"])
        poster_index = min(frame_count - 1, max(0, int(frame_count * 0.72)))

        for frame_index in range(frame_count):
            sim_time = (frame_index / (frame_count - 1)) * sim_duration
            cdp.send(
                "Runtime.evaluate",
                {"expression": f"window.romiCapture.seek({sim_time:.6f})", "returnByValue": True},
                session_id=session_id,
            )
            screenshot = cdp.send(
                "Page.captureScreenshot",
                {"format": "png", "fromSurface": True, "captureBeyondViewport": False},
                session_id=session_id,
            )
            frame_path = frame_dir / f"frame_{frame_index:04d}.png"
            frame_path.write_bytes(base64.b64decode(screenshot["data"]))
            if frame_index == poster_index:
                args.poster.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(frame_path, args.poster)

        args.mp4.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(
            [
                "-y",
                "-framerate",
                str(args.fps),
                "-i",
                str(frame_dir / "frame_%04d.png"),
                "-vf",
                "scale=1280:-2:flags=lanczos,format=yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "24",
                "-movflags",
                "+faststart",
                str(args.mp4),
            ]
        )
        run_ffmpeg(
            [
                "-y",
                "-framerate",
                str(args.fps),
                "-i",
                str(frame_dir / "frame_%04d.png"),
                "-vf",
                "fps=8,scale=960:-2:flags=lanczos",
                "-loop",
                "0",
                "-c:v",
                "libwebp_anim",
                "-lossless",
                "0",
                "-quality",
                "68",
                "-compression_level",
                "6",
                str(args.webp),
            ]
        )

        print(f"captured {frame_count} frames from {url}")
        print(f"mp4    {display_path(args.mp4, repo_root)} {file_size(args.mp4)}")
        print(f"webp   {display_path(args.webp, repo_root)} {file_size(args.webp)}")
        print(f"poster {display_path(args.poster, repo_root)} {file_size(args.poster)}")
        return 0
    finally:
        if cdp is not None:
            cdp.close()
        chrome.terminate()
        server.terminate()
        chrome.wait(timeout=5)
        server.wait(timeout=5)
        chrome_profile.cleanup()
        if args.keep_frames:
            print(f"frames {frame_dir}")
        else:
            frame_dir_ctx.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
