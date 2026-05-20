# Demo Capture Guide

This guide describes how to capture the first README-oriented navigation + manipulation demo using the current prototype pipeline.

The current visual demo is a RoMi 2D browser simulator. It shows a ROS2-free mobile manipulation scene while exposing RoMi-shaped stream counts, runtime stages, policy proposals, and recent events. The browser simulator and smoke pipeline both read `scenario.json`, so the visual motion and generated RoMi artifacts share the same scenario.

## Capture Goal

Show that RoMi can connect:

```text
RoMi-native simulation camera / depth / joints / odom / TF / goal
  -> episode -> replay -> mock policy -> dataset report
```

The video should communicate:

- RoMi can run the demo contract without ROS2.
- ROS2 interop remains bridge-first.
- Recorded data can be replayed.
- Policy output is non-authoritative.
- Runtime data remains inspectable.
- Dataset views preserve stream, time, frame, diagnostics, and policy metadata.

## Prerequisites

- Python 3.
- A modern browser for the visual simulator.

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

## Browser Simulator

Open the visual demo locally:

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory examples/navigation_manipulation_demo
# in another terminal:
xdg-open http://127.0.0.1:8000/romi_2d_sim/
```

The simulator runs in the browser and does not need ROS2 or a build step. Use the `Export JSONL` control to export RoMi-shaped stream events from the browser session.

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
0:35 - 0:50  Show stream counters and policy proposals
0:50 - 1:10  Run smoke script and show generated episode/report
1:10 - 1:30  Close on ROS2-free / replay-first / inspectable summary
```

## What To Highlight

During capture, show these concrete details:

- Camera, depth, joint, odometry, TF, and `task.goal` samples arrive as RoMi-shaped streams without requiring ROS2.
- The browser simulator shows navigation, manipulation, runtime graph stages, and recent events.
- The browser simulator and smoke pipeline share `scenario.json`.
- The same downstream pipeline can be exercised through `ROMI_DEMO_SOURCE=ros2`.
- `episode.json` records the episode metadata.
- `replay-events.jsonl` re-emits the stream with `source_system: replay`.
- `policy-events.jsonl` emits `policy.proposed_action`.
- Proposed actions have `authority: proposed_only`.
- `dataset-report/report.md` shows stream counts, diagnostics, policy output, and observation window.

## What Not To Claim

Do not claim:

- Production readiness.
- Full ROS2 replacement.
- Full simulator support.
- Real learned policy quality.
- Hardware-safe actuator control.

This is a README demo pipeline for the RoMi contract layer.
