# Demo Capture Guide

This guide describes how to capture the first README-oriented navigation + manipulation demo using the current prototype pipeline.

The current demo is a smoke-level contract demo. It proves the RoMi path from ROS2 input to bridge, episode recording, replay, mock policy output, and dataset inspection. A richer simulator scene can later replace the single `/goal_pose` publisher without changing the RoMi-side pipeline.

## Capture Goal

Show that RoMi can connect:

```text
ROS2 input -> bridge -> episode -> replay -> mock policy -> dataset report
```

The video should communicate:

- ROS2 interop is bridge-first.
- Recorded data can be replayed.
- Policy output is non-authoritative.
- Runtime data remains inspectable.
- Dataset views preserve stream, time, frame, diagnostics, and policy metadata.

## Prerequisites

- ROS2 environment sourced.
- Python 3.
- `rclpy` available.
- `ros2` CLI available.

The smoke script publishes a single `geometry_msgs/msg/PoseStamped` message on `/goal_pose`. A simulator can be running at the same time if available, but it is not required for the smoke capture.

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

- `ros2-bridge-events.jsonl`
- `episode/episode.json`
- `episode/streams.json`
- `episode/diagnostics.json`
- `replay-events.jsonl`
- `policy-events.jsonl`
- `dataset-report/report.md`
- `dataset-report/report.json`

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
0:10 - 0:25  Run smoke script and show ROS2 bridge status
0:25 - 0:40  Show generated episode directory and stream summary
0:40 - 0:55  Show replay and mock policy output
0:55 - 1:15  Show dataset report with diagnostics and observation window
1:15 - 1:30  Close on bridge-first / replay-first / inspectable summary
```

## What To Highlight

During capture, show these concrete details:

- `task.goal` arrives from ROS2 as a RoMi stream.
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
