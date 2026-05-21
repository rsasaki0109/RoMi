# Demo Capture Guide

This guide describes how to capture the first README-oriented navigation + manipulation demo using the current prototype pipeline.

The current visual demo is a RoMi 2D browser simulator. It shows a ROS2-free semi-humanoid mobile manipulation scene while exposing RoMi-shaped stream counts, runtime stages, policy proposals, and recent events. The browser simulator and smoke pipeline both read `scenario.json`, so the visual motion and generated RoMi artifacts share the same scenario.

## Capture Goal

Show that RoMi can connect:

```text
RoMi-native simulation camera / depth / joints / odom / TF / goal
  -> episode -> replay -> mock policy
  -> policy compare -> replay timeline -> safety report -> dataset report
```

The video should communicate:

- RoMi can run the demo contract without ROS2.
- ROS2 interop remains bridge-first.
- Recorded data can be replayed.
- Policy output is non-authoritative.
- Runtime data remains inspectable.
- Dataset views preserve stream, time, frame, diagnostics, and policy metadata.
- Timeline and safety reports make policy behavior reviewable without emitting commands.
- ROS2 bridge diagnostics preserve topic, QoS, TF, timing, and limitation metadata.

## Prerequisites

- Python 3.
- A modern browser for the visual simulator.
- Chrome or Chromium for browser-backed contract checks and media capture.

Install local browser/capture Python dependencies from the repository root:

```bash
python -m pip install -r requirements-browser.txt
```

This installs:

- `websocket-client` for Chrome DevTools Protocol access.
- `imageio-ffmpeg` as an ffmpeg fallback for media encoding.

If Chrome or Chromium is not on `PATH`, pass the executable explicitly:

```bash
python examples/navigation_manipulation_demo/capture_readme_video.py --chrome-bin /path/to/chrome
python tests/check_browser_native_contract.py --chrome-bin /path/to/chrome
```

The default smoke script starts a RoMi-native source that emits synthetic camera, depth, camera info, joint state, odometry, TF, and goal stream samples. A richer simulator can be connected later if available, but it is not required for this contract capture.

Optional ROS2 bridge mode requires a sourced ROS2 environment, `rclpy`, and the `ros2` CLI:

```bash
ROMI_DEMO_SOURCE=ros2 examples/navigation_manipulation_demo/run_smoke_demo.sh
```

## One-Shot Smoke Run

From the repository root:

```bash
examples/navigation_manipulation_demo/run_smoke_demo.sh
```

The script prints the generated run directory, usually under:

```text
examples/navigation_manipulation_demo/artifacts/smoke/<run-id>/
```

Important output files:

- `source-events.jsonl`
- `episode/episode.json`
- `episode/streams.json`
- `episode/diagnostics.json`
- `replay-events.jsonl`
- `policy-events.jsonl`
- `dataset-report/report.md`
- `dataset-report/report.json`

Committed README-adjacent review artifacts:

- `sample_output/policy_compare.md`
- `sample_output/policy_compare.json`
- `sample_output/evaluation_timeline.md`
- `sample_output/evaluation_timeline.json`
- `sample_output/safety_authority.md`
- `sample_output/safety_authority.json`
- `ros2-qos-diagnostics.example.json`

For GitHub review without running the demo, see the committed reference report:

```text
examples/navigation_manipulation_demo/sample_output/dataset-report/report.md
```

## Browser Simulator

Open the visual demo locally:

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory examples/navigation_manipulation_demo
# in another terminal:
xdg-open http://127.0.0.1:8000/romi_2d_sim/
```

The simulator runs in the browser and does not need ROS2 or a build step. Use the `Export JSONL` control to export RoMi-shaped stream events from the browser session.

## README Media Capture

Generate the README video assets from the actual browser simulator:

```bash
examples/navigation_manipulation_demo/capture_readme_video.py
```

Generated assets:

- `docs/assets/romi-2d-nav-manip-demo.mp4`
- `docs/assets/romi-2d-nav-manip-demo.webp`
- `docs/assets/romi-2d-nav-manip-demo-poster.png`

The capture script uses headless Chrome against `romi_2d_sim/?capture=readme`, seeks through the shared scenario deterministically, and records the sim UI. It can use system `ffmpeg` or the Python `imageio-ffmpeg` package for encoding. It is a visualization capture path, not a runtime dependency.

## Suggested Recording Layout

Use three terminal panes or windows:

1. Open `romi_2d_sim/index.html`.
2. Run the smoke script in a terminal.
3. Open `dataset-report/report.md` or `episode/streams.json`.

Optional fourth pane:

- Show filtered policy output:

```bash
python3 -m json.tool examples/navigation_manipulation_demo/artifacts/smoke/<run-id>/dataset-report/report.json
```

## Suggested Shot List

Keep the video short, around 60 to 90 seconds.

```text
0:00 - 0:15  Start the browser simulator and show navigation
0:15 - 0:35  Show manipulation reach, grasp, and place
0:35 - 0:50  Show stream counters, runtime graph, and policy proposals
0:50 - 1:10  Show compare, timeline, safety, and dataset Studio modes
1:10 - 1:25  Show committed artifacts and ROS2 bridge diagnostics
1:25 - 1:30  Close on ROS2-free / replay-first / bridge-first summary
```

## What To Highlight

During capture, show these concrete details:

- Camera, depth, joint, odometry, TF, and `task.goal` samples arrive as RoMi-shaped streams without requiring ROS2.
- The browser simulator shows navigation, manipulation, runtime graph stages, and recent events.
- RoMi Studio shows live, replay, policy, compare, timeline, safety, and dataset modes.
- The browser simulator and smoke pipeline share `scenario.json`.
- The same downstream pipeline can be exercised through `ROMI_DEMO_SOURCE=ros2`.
- The ROS2 bridge diagnostics sample keeps `/tf`, `/tf_static`, QoS, timing, and limitations visible.
- `episode.json` records the episode metadata.
- `replay-events.jsonl` re-emits the stream with `source_system: replay`.
- `policy-events.jsonl` emits `policy.proposed_action`.
- Proposed actions have `authority: proposed_only`.
- `dataset-report/report.md` shows stream counts, diagnostics, policy output, and observation window.
- `safety_authority.json` keeps actuator authority as `none`.

## What Not To Claim

Do not claim:

- Production readiness.
- Full ROS2 replacement.
- Full simulator support.
- Real learned policy quality.
- Hardware-safe actuator control.

This is a README demo pipeline for the RoMi contract layer.
