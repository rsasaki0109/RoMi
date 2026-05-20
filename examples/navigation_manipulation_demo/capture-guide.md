# Demo Capture Guide

This guide describes how to capture the first README-oriented navigation + manipulation demo using the current prototype pipeline.

The current demo is a smoke-level contract demo. It proves the RoMi path from a ROS2-free native simulation source to episode recording, replay, mock policy output, dataset inspection, and README animation rendering from the generated artifacts. A richer simulator scene or ROS2 bridge can later replace the native source without changing the RoMi-side pipeline.

## Capture Goal

Show that RoMi can connect:

```text
RoMi-native simulation camera / depth / joints / odom / TF / goal
  -> episode -> replay -> mock policy -> dataset report -> README GIF
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

## Rendered README Animation

The README animation is generated from the RoMi smoke run artifacts:

```bash
python3 examples/navigation_manipulation_demo/render_sim_video.py
```

Outputs:

- `docs/assets/romi-nav-manip-demo.gif`
- `examples/navigation_manipulation_demo/artifacts/smoke/<run-id>/romi-nav-manip-demo.mp4`

The GIF can be committed for README display. The MP4 is ignored by git and can be uploaded as a GitHub asset when a true video URL is needed.

## Suggested Recording Layout

Use three terminal panes or windows:

1. Run the smoke script.
2. Open `dataset-report/report.md`.
3. Show `episode/README.md` or `episode/streams.json`.

Optional fourth pane:

- Show filtered policy output:

```bash
python3 -m json.tool examples/navigation_manipulation_demo/artifacts/smoke/<run-id>/dataset-report/report.json
```

## Suggested Shot List

Keep the video short, around 60 to 90 seconds.

```text
0:00 - 0:10  README title and planned graph
0:10 - 0:25  Run smoke script and show native source status
0:25 - 0:40  Show generated episode directory and stream summary
0:40 - 0:55  Show replay and mock policy output
0:55 - 1:15  Show dataset report with diagnostics and observation window
1:15 - 1:30  Close on ROS2-free / replay-first / inspectable summary
```

## What To Highlight

During capture, show these concrete details:

- Camera, depth, joint, odometry, TF, and `task.goal` samples arrive as RoMi streams without requiring ROS2.
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
