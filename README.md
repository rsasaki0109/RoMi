# RoMi

**Physical AI-friendly robotics middleware**

RoMi stands for **Robotics Middleware**. It is an early concept for a next-generation robotics middleware focused on replayable, inspectable, simulation-native robot runtimes.

RoMi is intended to bridge classical robotics middleware and modern Physical AI workflows. The design direction is a middleware contract layer that can connect live robots, simulators, recorded logs, datasets, ML policies, and deployment runtimes without forcing every system into one language, one transport, one simulator, or one robotics framework.

> Development status: early concept / pre-MVP.

RoMi is not production-ready, and it does not yet provide a runtime implementation. This repository currently defines the project vision, requirements, architecture direction, and MVP scope.

## Target Demo Video: Navigation + Manipulation

The first public README demo should be a short navigation + manipulation episode that shows RoMi's intended contract layer across live or simulated execution, recording, replay, policy evaluation, and runtime inspection.

Planned demo flow:

```text
ROS2 robot or simulator
        |
        | camera / depth / joint state / odometry / TF / goals
        v
RoMi bridge -> episode recorder -> replay source
        |              |              |
        v              v              v
runtime graph     dataset view     mock policy node
        |
        v
graph / latency / frame / QoS / policy diagnostics
```

The demo should show a robot navigating to a manipulation area, observing an object or target, running a mock policy over synchronized observations, emitting proposed non-authoritative actions, recording the episode, replaying it, and exposing diagnostics. The video is planned; the target storyboard is in [docs/demo-video.md](docs/demo-video.md), the implementation contract is in [docs/demo-spec.md](docs/demo-spec.md), and the example scaffold is in [examples/navigation_manipulation_demo](examples/navigation_manipulation_demo).

Demo build path:

- [Demo video plan](docs/demo-video.md)
- [Demo implementation spec](docs/demo-spec.md)
- [Demo backlog](docs/demo-backlog.md)
- [Demo-focused roadmap](docs/roadmap.md)
- [Navigation + manipulation example scaffold](examples/navigation_manipulation_demo)
- [Demo capture guide](examples/navigation_manipulation_demo/capture-guide.md)
- [ROS2 bridge boundary](bridges/ros2)
- [Episode recorder prototype](tools/episode_recorder)
- [Replay source prototype](tools/replay_source)
- [Mock policy prototype](tools/mock_policy)
- [Dataset inspector prototype](tools/dataset_inspector)
- [Draft schemas](schemas)

## Current Demo Pipeline

The current prototype can run a smoke-level navigation + manipulation contract demo:

```text
ROS2 /goal_pose
  -> RoMi ROS2 bridge JSONL
  -> episode recorder
  -> replay source
  -> mock policy
  -> dataset inspection report
```

Run from the repository root inside a sourced ROS2 environment:

```bash
examples/navigation_manipulation_demo/run_smoke_demo.sh
```

The script publishes one ROS2 `geometry_msgs/msg/PoseStamped` goal, records a prototype episode, replays it, emits a non-authoritative `policy.proposed_action`, and generates `dataset-report/report.md` for inspection or video capture.

This is a prototype contract demo, not a full robot runtime. A richer simulator or mobile manipulator scene can replace the single `/goal_pose` publisher while keeping the RoMi-side pipeline shape.

## Why RoMi Exists

Classical robotics middleware has proven the value of distributed robot components, typed communication, coordinate frames, time synchronization, logging, replay, visualization, hardware abstraction, and ecosystem interoperability.

Modern Physical AI workflows add pressure in areas that were not always first-class middleware concerns:

- Dataset-first development and evaluation
- Replay-based debugging and benchmarking
- Tensor-native perception and policy data
- Vision-language-action and imitation learning policies
- GPU-centered inference runtimes
- Notebook experimentation over recorded episodes
- Simulation-driven development and validation
- Runtime observability for deployed policies
- Clear actuator authority and safety boundaries

RoMi exists to explore a middleware layer that treats live execution, simulation, replay, dataset loading, and policy deployment as closely related runtime modes.

## Problems RoMi Targets

RoMi is focused on problems that sit between robot runtime systems and robot learning systems:

- Making live and replayed robot data behave symmetrically
- Preserving time, frame, and world semantics across logs, simulators, and live robots
- Exposing inspectable runtime graphs for debugging and evaluation
- Supporting transport-agnostic data movement across processes, hosts, accelerators, and logs
- Making structured schemas and tensor data practical for robot learning workflows
- Providing bridge-first interoperability with ROS2, DDS, MCAP, simulators, and vendor SDKs
- Defining deployment-oriented contracts for policies, sensors, actuators, and supervisors

## What RoMi Is Not

RoMi is not:

- A claim that ROS or ROS2 should be discarded
- A planned drop-in replacement for the full ROS ecosystem
- A DDS-only, ROS2-only, Python-only, C++-only, or Rust-only project
- A simulator, ML framework, dataset format, or robot SDK by itself
- A production runtime today

The initial goal is bridge-first interoperability and clearer runtime contracts, not replacement-first ecosystem disruption.

## Core Design Principles

- **Replay-first:** Runtime behavior should be inspectable from recorded episodes, not only from live processes.
- **Online/offline symmetry:** Live robot execution, simulation, replay, and dataset iteration should share the same conceptual graph where practical.
- **Transport-agnostic:** The data plane should not assume one transport. Local IPC, shared memory, DDS, Zenoh, vendor SDKs, and log readers should be possible adapters.
- **Schema-native:** Robot data should have explicit structure, versioning, metadata, and validation paths.
- **Tensor-aware:** Images, point clouds, proprioception, actions, embeddings, and policy inputs should be practical to move between runtime and ML tooling.
- **Simulation-native:** Simulators should be first-class runtime peers, not special cases outside the middleware model.
- **ROS2-interoperable:** RoMi should bridge to ROS2 topics, services, actions, tf2, rosbag2, MCAP, Nav2, Autoware, and DDS-based deployments where appropriate.
- **Inspectable runtime:** Graph state, timing, frame transforms, latency, QoS, drops, and policy decisions should be observable.
- **Deployment-oriented:** Runtime contracts should make authority, lifecycle, supervision, and safety boundaries explicit.

## Early Architecture Sketch

RoMi is currently framed as a set of cooperating planes:

```text
                    tools / notebooks / diagnostics
                               |
                        observability plane
                               |
 control plane ---- runtime graph / lifecycle / supervision
       |                       |
 semantic plane ---- schemas / time / frames / world model
       |                       |
 data plane -------- transports / shared memory / DDS / log readers
       |                       |
 log and dataset plane ------- episodes / MCAP direction / dataset views
       |                       |
 interop plane ----- ROS2 / simulators / vendor SDKs / policy runtimes
       |
 safety plane ------ actuator authority / limits / policy gates
```

This is a design sketch, not an implemented architecture.

## MVP Direction

The proposed MVP should demonstrate a small but complete runtime contract:

- Bridge camera, depth, joint state, odometry, TF-like data, and task signals from a ROS2 robot or simulator
- Record an episode in an MCAP-compatible direction
- Replay the same episode through the same graph shape
- Run a mock navigation + manipulation policy inference node
- Expose graph, latency, stream, and frame diagnostics
- Provide notebook-friendly loading of recorded data

The MVP should optimize for clarity of contracts before breadth of features.

## Relationship With ROS and ROS2

RoMi is not anti-ROS. ROS and ROS2 remain important robotics ecosystems, especially for modular autonomous systems, driver integration, visualization, navigation, manipulation stacks, and distributed component development.

RoMi should interoperate with ROS2 instead of requiring users to abandon it. The intended path is bridge-first:

- ROS2 topic bridge
- tf2 bridge
- rosbag2 / MCAP bridge
- Service and action bridge
- QoS diagnostics
- Migration paths for Nav2, Autoware, simulator stacks, and robot-specific SDKs

RoMi aims to define a better contract layer around replay, simulation, datasets, policies, and deployable robot runtimes while preserving access to the ROS2 ecosystem.

## Repository Status

This repository currently contains:

- Project vision and positioning
- Initial requirements for next-generation robotics middleware
- High-level architecture draft
- ROS2 interoperability notes
- MVP proposal
- Navigation + manipulation demo specification
- Demo-focused roadmap
- Demo implementation backlog
- ROS2 bridge boundary and message map
- Episode recorder prototype
- Replay source prototype
- Mock policy prototype
- Dataset inspector prototype
- Demo smoke script and capture guide
- Draft schema sketches and static demo artifacts
- Proposed repository structure
- Basic GitHub issue and PR templates

No heavy runtime code has been introduced yet.

## GitHub Metadata

Suggested repository description:

> Physical AI-friendly robotics middleware for replayable, inspectable, simulation-native robot runtimes.

Suggested topics:

`robotics`, `middleware`, `physical-ai`, `robot-runtime`, `ros2`, `simulation`, `replay`, `autonomy`, `distributed-systems`, `robot-learning`, `vla`, `mcap`

## Contributing

RoMi is pre-MVP and needs careful technical discussion before implementation. Contributions are welcome in the form of architecture notes, requirements, interoperability analysis, MVP experiments, and narrowly scoped prototypes.

Good early contributions should make runtime contracts clearer, improve replay or observability semantics, or reduce ambiguity around ROS2, simulator, dataset, and policy integration.
