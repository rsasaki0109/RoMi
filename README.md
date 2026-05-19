# RoMi

[![CI](https://github.com/rsasaki0109/RoMi/actions/workflows/ci.yml/badge.svg)](https://github.com/rsasaki0109/RoMi/actions/workflows/ci.yml)

**Physical AI-friendly robotics middleware for replayable, inspectable, simulation-native robot runtimes.**

RoMi stands for **Robotics Middleware**. It is an early pre-MVP project exploring a bridge-first contract layer between live robots, simulators, recorded episodes, datasets, ML policies, and deployment runtimes.

<p align="center">
  <a href="docs/assets/romi-2d-nav-manip-demo.mp4">
    <img src="docs/assets/romi-2d-nav-manip-demo.webp" alt="RoMi 2D semi-humanoid navigation and manipulation simulator demo" width="900">
  </a>
</p>

<p align="center">
  <sub>Actual RoMi 2D simulator capture: ROS2-free navigation/manipulation with a RoMi Studio mini inspector for live, replay, policy, and dataset state.</sub>
</p>

## Demo

Current visual target: **RoMi 2D semi-humanoid navigation + manipulation simulator**.

Open the ROS2-free browser demo locally:

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory examples/navigation_manipulation_demo
# in another terminal:
xdg-open http://127.0.0.1:8000/romi_2d_sim/
```

The visual simulator shows a semi-humanoid mobile manipulator navigating to a work area, reaching for an object, placing it in a bin, and exposing RoMi-shaped stream counts, runtime stages, policy proposals, and event envelopes. The RoMi Studio mini inspector can switch between live stream freshness, replay graph state, proposed policy actions, and dataset report views, with seek controls and event-envelope inspection for replay debugging.

The browser simulator and the smoke pipeline both read [scenario.json](examples/navigation_manipulation_demo/scenario.json), so the visual motion and generated RoMi artifacts share the same scenario.

This demo currently proves:

- The navigation + manipulation scenario can run without ROS2.
- The browser simulator and native smoke source share the same scenario contract.
- The pipeline records an episode, replays it, runs a mock policy, and generates a dataset report.
- Policy output is `proposed_only`; it is not actuator authority.

Current smoke demo:

```text
RoMi-native simulation: camera / depth / joints / odom / TF / goal
  -> episode recorder
  -> replay source
  -> mock policy
  -> dataset inspection report
```

Optional ROS2 interop mode:

```text
ROS2 camera / depth / joints / odom / TF / goal
  -> RoMi ROS2 bridge
  -> episode recorder
  -> replay source
  -> mock policy
  -> dataset inspection report
```

Run the default ROS2-free demo from the repository root:

```bash
examples/navigation_manipulation_demo/run_smoke_demo.sh
```

The script generates a RoMi-native navigation + manipulation simulation, records a prototype episode, replays it, emits non-authoritative `policy.proposed_action` samples, and generates `dataset-report/report.md`.

Example generated report: [sample dataset report](examples/navigation_manipulation_demo/sample_output/dataset-report/report.md).

To exercise the ROS2 bridge instead:

```bash
ROMI_DEMO_SOURCE=ros2 examples/navigation_manipulation_demo/run_smoke_demo.sh
```

## What RoMi Is

RoMi is a Physical AI-friendly robotics middleware direction focused on:

- Replay-first robot runtimes
- Inspectable runtime graphs
- Simulation-native development
- Dataset-aware logging and replay
- Policy-runtime integration
- ROS2 interoperability without becoming ROS2-only
- Transport-agnostic contracts

RoMi is not a claim that ROS or ROS2 should be discarded. The first goal is interop and better runtime contracts, not ecosystem replacement.

## Current Prototype

The current repository contains a small end-to-end prototype path:

- [ROS2 bridge prototype](bridges/ros2/rclpy_bridge)
- [Episode recorder](tools/episode_recorder)
- [Replay source](tools/replay_source)
- [Mock policy](tools/mock_policy)
- [Dataset inspector](tools/dataset_inspector)
- [Navigation + manipulation demo](examples/navigation_manipulation_demo)
- [RoMi Studio mini browser simulator](examples/navigation_manipulation_demo/romi_2d_sim)
- [Capture guide](examples/navigation_manipulation_demo/capture-guide.md)

This is a prototype contract demo, not a production robot runtime.

## Docs

- [Vision](docs/vision.md)
- [Requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [ROS2 interop](docs/ros2-interop.md)
- [MVP proposal](docs/mvp.md)
- [Demo contract](docs/demo-contract.md)
- [Demo spec](docs/demo-spec.md)
- [Demo backlog](docs/demo-backlog.md)
- [Roadmap](docs/roadmap.md)
- [Repository structure](docs/repository-structure.md)

## Status

Development status: **early concept / pre-MVP**.

RoMi is not:

- Production-ready
- A full ROS replacement
- DDS-only, ROS2-only, Python-only, C++-only, or Rust-only
- A simulator, ML framework, dataset format, or robot SDK by itself

## Contributing

Good early contributions clarify schemas, replay behavior, ROS2 bridge boundaries, observability, dataset workflows, and policy-runtime contracts.
