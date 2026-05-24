# Navigation + Manipulation Demo

Status: prototype pipeline / smoke-demo ready.

This example is the target for RoMi's first README demo video. It shows a semi-humanoid robot navigating to a manipulation area, observing a target, running a mock policy, recording an episode, replaying that episode, comparing policy behavior, and exposing runtime diagnostics.

This directory contains a prototype pipeline for the first README demo. No simulator, transport, or ML framework is selected as a permanent architectural choice.

Current prototype files:

- `stream-map.example.json`: planned source topic to RoMi stream mapping
- `scenario.json`: shared navigation + manipulation scenario for the browser simulator and native source
- `contract.example.json`: machine-readable demo contract used by CI checks
- `runtime-graph.example.json`: planned graph shape
- `episode-metadata.example.json`: planned episode metadata
- `diagnostics.example.json`: planned diagnostics report shape
- `ros2-bridge-plan.md`: planned ROS2 bridge path for the demo
- `ros2-qos-diagnostics.example.json`: committed ROS2 bridge diagnostics sample covering topics, QoS, TF, timing, and bridge limits
- `romi_native_sim_source.py`: ROS2-free RoMi-native navigation + manipulation source
- `generate_sample_artifacts.py`: deterministic helper for committed sample artifacts
- `ros2_demo_sim_publisher.py`: scripted ROS2 navigation + manipulation source for the smoke demo
- `run_smoke_demo.sh`: one-shot smoke run for source, record, replay, policy, and dataset report
- `romi_2d_sim/`: browser-based RoMi 2D navigation + manipulation simulator
- `capture_readme_video.py`: headless Chrome capture script for README MP4, WebP, and poster assets
- `sample_output/dataset-report/report.md`: committed example of the generated dataset report
- `sample_output/dataset-report/report.json`: committed structured dataset report
- `sample_output/report_manifest.json`: committed manifest connecting report artifacts to schemas
- `sample_output/policy_compare.md`: committed Markdown policy comparison artifact from RoMi Studio
- `sample_output/policy_compare.json`: committed JSON policy comparison artifact from RoMi Studio
- `sample_output/evaluation_timeline.md`: committed Markdown replay evaluation timeline artifact from RoMi Studio
- `sample_output/evaluation_timeline.json`: committed JSON replay evaluation timeline artifact from RoMi Studio
- `sample_output/safety_authority.md`: committed Markdown safety authority artifact from RoMi Studio
- `sample_output/safety_authority.json`: committed JSON safety authority artifact from RoMi Studio
- `capture-guide.md`: README video capture guide

## Demo Goal

Demonstrate RoMi's intended contract layer across:

- RoMi-native, ROS2, or simulator data
- Navigation and manipulation observations
- Runtime graph inspection
- Episode recording
- Replay
- Mock policy inference
- Counterfactual policy comparison
- Replay-wide policy evaluation timeline
- Safety authority boundary report
- Dataset-style inspection
- Diagnostics
- A simple visual simulator that is not tied to ROS2

The demo should be useful even if the first robot behavior is scripted and the first policy is a stub.

## Visual Simulator

Open the RoMi 2D browser simulator locally:

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory examples/navigation_manipulation_demo
# in another terminal:
xdg-open http://127.0.0.1:8000/romi_2d_sim/
```

The simulator shows a semi-humanoid mobile manipulator navigating to a work area, reaching for an object, placing it in a bin, and exposing RoMi-shaped stream counters, runtime graph state, policy proposals, and event envelopes. Its RoMi Studio mini inspector adds switchable live, replay, policy, compare, timeline, safety, and dataset report views plus policy observation-window freshness, exportable counterfactual policy comparison artifacts, replay-wide evaluation timeline artifacts, actuator authority boundaries, replay seek controls, runtime graph inspection, and event-envelope inspection. It runs without ROS2 or a build step.

The visual direction follows the [RoMi-H mascot concept](../../docs/assets/romi-h-mascot.png): a semi-humanoid mobile manipulator, not a ROS2-only simulator mascot.

The browser simulator and `romi_native_sim_source.py` both read `scenario.json`, so the motion shown on screen and the RoMi JSONL artifact stream are generated from the same scenario definition.

The browser export and native smoke source intentionally use the same RoMi stream names and closely aligned payload summaries for RGB, depth, camera info, joint state, odometry, TF, task goal, diagnostics, and non-authoritative policy proposals. The Studio compare view can export `policy_compare.md` or `policy_compare.json` from the replay state. The Studio timeline view can export `evaluation_timeline.md` or `evaluation_timeline.json` across sampled replay times. The committed safety authority artifacts keep policy proposals separate from actuator authority.

The ROS2 bridge path keeps `/tf` and `/tf_static` mapped into the same `robot.frames.tf` RoMi stream while preserving the original `source_topic` and QoS metadata. The committed [ROS2 bridge diagnostics sample](ros2-qos-diagnostics.example.json) shows the expected topic, QoS, frame, latency, and limitation fields without requiring ROS2 to run in CI.

The machine-readable contract lives in [contract.example.json](contract.example.json).

Generate the README media assets:

```bash
python -m pip install -r requirements-browser.txt
examples/navigation_manipulation_demo/capture_readme_video.py
```

The capture script and browser/native contract test use headless Chrome through
the Chrome DevTools Protocol. They auto-detect common Chrome, Chromium, and Edge
install paths; pass `--chrome-bin` if your browser lives elsewhere.

Regenerate the committed sample artifacts:

```bash
python examples/navigation_manipulation_demo/generate_sample_artifacts.py
```

Run the ROS2 bridge smoke path from a sourced ROS2 environment:

```bash
source /opt/ros/<distro>/setup.bash
python3 -m pip install numpy

ROMI_DEMO_SOURCE=ros2 \
ROMI_DEMO_RUN_ID=ros2-local \
ROMI_DEMO_BRIDGE_DURATION_SEC=8 \
examples/navigation_manipulation_demo/run_smoke_demo.sh

python3 tests/check_demo_contract.py examples/navigation_manipulation_demo/artifacts/smoke/ros2-local
```

The ROS2 path starts `bridges/ros2/rclpy_bridge/romi_ros2_bridge.py`, publishes
a scripted ROS2 demo source, records the resulting RoMi stream samples, replays
them, runs the mock policy, and writes `dataset-report/report.md`. See
[`bridges/ros2/rclpy_bridge/README.md`](../../bridges/ros2/rclpy_bridge/README.md)
for expected output files and troubleshooting.

## Planned Flow

```text
RoMi-native sim source or external simulator bridge
        |
        | RGB / depth / joint state / odometry / TF / task goal
        v
RoMi stream events
        |
        +---> optional ROS2 bridge diagnostics
        +---> runtime graph diagnostics
        +---> episode recorder
        +---> observation synchronizer
                    |
                    v
              mock policy node
                    |
                    v
          proposed non-authoritative actions

recorded episode
        |
        v
replay source -> same graph shape -> mock policy -> policy compare + diagnostics
```

## Minimum Source Signals

The first implementation maps native simulation output or robot/simulator topics into these RoMi stream names:

| RoMi stream | Meaning |
| --- | --- |
| `robot.camera.rgb` | RGB camera observation |
| `robot.camera.depth` | Depth image or point cloud observation |
| `robot.camera.info` | Camera calibration metadata |
| `robot.joints.state` | Arm or full robot joint state |
| `robot.base.odom` | Base odometry |
| `robot.frames.tf` | Dynamic and static transforms |
| `task.goal` | Navigation or manipulation target |
| `policy.observation` | Synchronized policy input |
| `policy.proposed_action` | Non-authoritative action proposal |
| `runtime.diagnostics` | Graph, timing, frame, QoS, and policy diagnostics |

The current smoke path contract is summarized in [../../docs/demo-contract.md](../../docs/demo-contract.md).

## Mock Policy

The mock policy exists to test the runtime contract.

It should:

- Consume synchronized observations.
- Include both navigation and manipulation context.
- Emit proposed base, end-effector, or gripper actions.
- Report input freshness.
- Report inference latency.
- Avoid direct actuator authority.
- Run against live source or bridged streams and replayed streams.

It does not need to be a learned model.

## ROS2 Bridge Prototype

The recommended first bridge path is the `rclpy` prototype:

```bash
python3 ../../bridges/ros2/rclpy_bridge/romi_ros2_bridge.py \
  --stream-map stream-map.example.json \
  --output artifacts/ros2-bridge-events.jsonl \
  --duration-sec 30
```

Run it from this directory inside a sourced ROS2 environment. The prototype writes stream envelopes and diagnostics as JSON Lines. It does not serialize large image or point cloud payloads into JSON.

## One-Shot Smoke Demo

From the repository root:

```bash
examples/navigation_manipulation_demo/run_smoke_demo.sh
```

By default the script does not require ROS2. It generates camera, depth, joint state, odometry, TF, and goal streams with the RoMi-native source, then runs episode recording, replay, mock policy, and dataset inspection. See [capture-guide.md](capture-guide.md) for capture steps.

For a GitHub-viewable example of the generated dataset view, open [sample_output/dataset-report/report.md](sample_output/dataset-report/report.md).

To refresh the committed dataset, policy compare, and evaluation timeline samples, run:

```bash
python examples/navigation_manipulation_demo/generate_sample_artifacts.py
```

To run the same contract through the ROS2 bridge:

```bash
ROMI_DEMO_SOURCE=ros2 examples/navigation_manipulation_demo/run_smoke_demo.sh
```

When `ROS_DOMAIN_ID` is unset, the script uses an isolated demo domain to keep
the smoke output separate from other local ROS graphs.

## Episode Recording Prototype

After collecting source JSONL output, create a prototype episode directory:

```bash
python3 ../../tools/episode_recorder/romi_record_episode.py \
  --input artifacts/source-events.jsonl \
  --output artifacts/episodes/nav_manip_demo_001 \
  --episode-id nav_manip_demo_001 \
  --scenario-name navigation_to_table_and_mock_pick \
  --mode simulation \
  --world-id demo_world \
  --robot-id mobile_manipulator_demo \
  --runtime-graph runtime-graph.example.json
```

The output is a JSONL-based prototype episode layout. It is not the final storage format.

## Replay Source Prototype

Replay the recorded episode back into RoMi stream samples:

```bash
python3 ../../tools/replay_source/romi_replay_episode.py \
  --episode artifacts/episodes/nav_manip_demo_001 \
  --output artifacts/replay-events.jsonl \
  --no-sleep
```

The replay output preserves stream IDs and recorded event time, sets `source_system` to `replay`, and adds replay metadata.

## Mock Policy Prototype

Run the mock policy over live source, bridge, or replay output:

```bash
python3 ../../tools/mock_policy/romi_mock_policy.py \
  --input artifacts/replay-events.jsonl \
  --output artifacts/policy-events.jsonl
```

The mock policy emits `policy.proposed_action` only. It does not command actuators.

## Dataset Inspection Prototype

Generate a report for README video capture:

```bash
python3 ../../tools/dataset_inspector/romi_inspect_dataset.py \
  --episode artifacts/episodes/nav_manip_demo_001 \
  --policy-events artifacts/policy-events.jsonl \
  --output-dir artifacts/dataset-report
```

The report includes episode metadata, stream counts, diagnostics, policy actions, and a synchronized observation window.

## Episode Output

The recorded episode should eventually include:

- Episode metadata
- Stream metadata
- Schema versions
- Frame graph metadata
- Source or bridge metadata
- QoS metadata where available
- Runtime graph metadata
- Mock policy metadata
- Diagnostics events

MCAP compatibility is a design direction for the logging path.

## Diagnostics To Capture

The README video should visibly show:

- Graph nodes and streams
- Stream rates
- Latency
- Drops or gaps
- Frame graph status
- QoS metadata or warnings
- Replay clock state
- Policy input freshness
- Policy inference latency
- Proposed action stream

## First Implementation Tasks

1. Add static stream mapping and graph metadata.
2. Add schema sketches for required streams.
3. Add example episode metadata.
4. Add a small diagnostics report.
5. Add a minimal bridge path for selected ROS2 topics.
6. Add a prototype episode recorder.
7. Add a minimal replay source.
8. Add a mock policy node.
9. Add a dataset inspection report or notebook.
10. Capture and embed the README video.

## References

- [Demo spec](../../docs/demo-spec.md)
- [Demo video plan](../../docs/demo-video.md)
- [Demo capture guide](capture-guide.md)
- [MVP proposal](../../docs/mvp.md)
- [Demo backlog](../../docs/demo-backlog.md)
- [Roadmap](../../docs/roadmap.md)
- [ROS2 bridge boundary](../../bridges/ros2)
- [rclpy bridge prototype](../../bridges/ros2/rclpy_bridge)
- [Episode recorder prototype](../../tools/episode_recorder)
- [Replay source prototype](../../tools/replay_source)
- [Mock policy prototype](../../tools/mock_policy)
- [Dataset inspector prototype](../../tools/dataset_inspector)
- [Draft schemas](../../schemas)
