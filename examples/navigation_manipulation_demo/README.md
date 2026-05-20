# Navigation + Manipulation Demo

Status: prototype pipeline / smoke-demo ready.

This example is the target for RoMi's first README demo video. It should show a robot navigating to a manipulation area, observing a target, running a mock policy, recording an episode, replaying that episode, and exposing runtime diagnostics.

This directory contains a prototype pipeline for the first README demo. No simulator, transport, or ML framework is selected as a permanent architectural choice.

Current static artifacts:

- `stream-map.example.json`: planned source topic to RoMi stream mapping
- `runtime-graph.example.json`: planned graph shape
- `episode-metadata.example.json`: planned episode metadata
- `diagnostics.example.json`: planned diagnostics report shape
- `ros2-bridge-plan.md`: planned ROS2 bridge path for the demo
- `ros2-qos-diagnostics.example.json`: planned QoS diagnostics shape
- `run_smoke_demo.sh`: one-shot smoke run for bridge, record, replay, policy, and dataset report
- `capture-guide.md`: README video capture guide

## Demo Goal

Demonstrate RoMi's intended contract layer across:

- ROS2 or simulator data
- Navigation and manipulation observations
- Runtime graph inspection
- Episode recording
- Replay
- Mock policy inference
- Dataset-style inspection
- Diagnostics

The demo should be useful even if the first robot behavior is scripted and the first policy is a stub.

## Planned Flow

```text
ROS2 robot or simulator
        |
        | RGB / depth / joint state / odometry / TF / task goal
        v
RoMi bridge
        |
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
replay source -> same graph shape -> mock policy -> diagnostics
```

## Minimum Source Signals

The first implementation should map robot or simulator topics into these RoMi stream names:

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

## Mock Policy

The mock policy exists to test the runtime contract.

It should:

- Consume synchronized observations.
- Include both navigation and manipulation context.
- Emit proposed base, end-effector, or gripper actions.
- Report input freshness.
- Report inference latency.
- Avoid direct actuator authority.
- Run against live bridged streams and replayed streams.

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

The script publishes one `/goal_pose` message, runs bridge, episode recording, replay, mock policy, and dataset inspection, then prints the generated `report.md` path. See [capture-guide.md](capture-guide.md) for video capture steps.

## Episode Recording Prototype

After collecting bridge JSONL output, create a prototype episode directory:

```bash
python3 ../../tools/episode_recorder/romi_record_episode.py \
  --input artifacts/ros2-bridge-events.jsonl \
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

Run the mock policy over live bridge output or replay output:

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
- ROS2 bridge metadata
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
