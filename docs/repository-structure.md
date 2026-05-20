# Proposed Repository Structure

This document proposes a repository structure for RoMi. It is a planning document, not a claim that all directories or modules already exist.

## Structure

```text
romi/
  README.md
  docs/
    assets/
      romi-demo-pipeline.svg
      romi-2d-nav-manip-demo.mp4
      romi-2d-nav-manip-demo.webp
      romi-2d-nav-manip-demo-poster.png
      romi-h-mascot.png
    vision.md
    requirements.md
    architecture.md
    ros2-interop.md
    mvp.md
    demo-video.md
    demo-spec.md
    demo-backlog.md
    roadmap.md
    repository-structure.md
  schemas/
    README.md
    core/
      diagnostic_event.schema.json
      episode.schema.json
      runtime_graph.schema.json
    robotics/
      stream_metadata.schema.json
    ml/
      policy_io.schema.json
  runtime/
    graph/
    lifecycle/
    clock/
    frames/
    observability/
    safety/
  transports/
    local/
    shared_memory/
    dds/
    zenoh/
  bridges/
    README.md
    ros2/
      README.md
      message-map.md
      qos-diagnostics.md
      rclpy_bridge/
        README.md
        romi_ros2_bridge.py
    mcap/
    simulators/
  tools/
    README.md
    romictl/
    episode_recorder/
      README.md
      romi_record_episode.py
    replay_source/
      README.md
      romi_replay_episode.py
    mock_policy/
      README.md
      romi_mock_policy.py
    dataset_inspector/
      README.md
      romi_inspect_dataset.py
  examples/
    navigation_manipulation_demo/
      README.md
      capture-guide.md
      scenario.json
      capture_readme_video.py
      romi_native_sim_source.py
      ros2_demo_sim_publisher.py
      run_smoke_demo.sh
      romi_2d_sim/
        index.html
        styles.css
        sim.js
      stream-map.example.json
      runtime-graph.example.json
      episode-metadata.example.json
      diagnostics.example.json
      ros2-bridge-plan.md
      ros2-qos-diagnostics.example.json
      sample_output/
        dataset-report/
          report.md
    ros2_bridge_demo/
    manipulation_replay_demo/
    policy_runtime_demo/
  tests/
    fixtures/
    replay/
    integration/
```

## Directory Intent

### `docs/`

Architecture, requirements, design notes, MVP plans, interoperability notes, and decision records.

### `schemas/`

Schema definitions and compatibility rules.

Suggested split:

- `core/`: clocks, streams, graph metadata, diagnostics, lifecycle events
- `robotics/`: images, camera info, point clouds, odometry, joint state, transforms, commands
- `ml/`: tensors, observations, proposed actions, policy outputs, embeddings, evaluation metadata

### `runtime/`

Core runtime contracts and implementation modules.

Suggested split:

- `graph/`: node and stream graph contracts
- `lifecycle/`: component states and supervision
- `clock/`: live, simulated, recorded, and replay clock models
- `frames/`: frame graph contracts and diagnostics
- `observability/`: graph, latency, QoS, and health inspection
- `safety/`: actuator authority, gates, limits, and intervention events

### `transports/`

Transport adapters. The core runtime should avoid depending on a single transport.

Possible adapters:

- `local/`: local process or IPC transport
- `shared_memory/`: high-throughput local payload movement
- `dds/`: DDS-backed integration path
- `zenoh/`: Zenoh-backed integration path

### `bridges/`

Interop adapters for existing ecosystems.

Suggested split:

- `ros2/`: topics, services, actions, tf2, QoS diagnostics
- `mcap/`: MCAP-compatible logging and reading
- `simulators/`: simulator integration contracts and adapters

### `tools/`

Developer and operator tools.

Possible initial tool:

- `romictl/`: future CLI for graph inspection, replay control, bridge status, and diagnostics

No CLI implementation should be added until a language/runtime stack is chosen.

### `examples/`

Small, inspectable examples that demonstrate runtime contracts.

Suggested examples:

- `navigation_manipulation_demo/`: README-target demo combining navigation, manipulation, replay, policy output, and diagnostics
- `ros2_bridge_demo/`: bridge ROS2 camera, joint state, odometry, and TF streams
- `manipulation_replay_demo/`: record and replay manipulation episodes
- `policy_runtime_demo/`: run a mock policy over live or replayed observations

### `tests/`

Fixtures and integration tests.

Suggested split:

- `fixtures/`: small test schemas, messages, and episode fragments
- `replay/`: replay determinism and clock behavior tests
- `integration/`: bridge and runtime integration tests

## Repository Principles

- Keep runtime, schema, transport, bridge, and tooling boundaries visible.
- Do not hide transport assumptions inside core schemas.
- Keep examples small enough to inspect.
- Prefer explicit documentation and contracts before broad implementation.
- Avoid committing to one language stack before the MVP needs it.
