# RoMi Roadmap

This roadmap is focused on reaching the first README demo video. It is not a full product roadmap.

## Current Status

RoMi is in early concept / pre-MVP status.

The repository currently contains project positioning, requirements, architecture direction, ROS2 interop notes, MVP direction, demo video planning, and GitHub templates. It does not yet contain a runtime implementation.

## Milestone 0: Repository Foundation

Status: in progress.

Goal:

- Make the project understandable to senior robotics engineers.
- Establish that RoMi is Physical AI-friendly, replay-first, simulation-native, ROS2-interoperable, and transport-agnostic.
- Avoid positioning RoMi as a full ROS replacement.

Done:

- README foundation
- Vision document
- Requirements document
- Architecture draft
- ROS2 interop document
- MVP proposal
- Demo video plan
- Issue and PR templates

Remaining:

- License selection
- Contributing guide
- Architecture decision records

## Milestone 1: Demo Contract

Goal:

- Define the exact navigation + manipulation demo contract.
- Create an example scaffold without committing to final runtime technologies.
- Make the stream names, graph shape, episode metadata, replay expectations, and diagnostics explicit.

Deliverables:

- `docs/demo-spec.md`
- `examples/navigation_manipulation_demo/README.md`
- `docs/demo-backlog.md`
- Initial schema sketches for demo streams
- Initial episode metadata sketch
- Demo issue backlog

Exit criteria:

- A contributor can understand what the README demo should show.
- Implementation issues can be created from the spec.
- The demo can be implemented with a simulator first.

## Milestone 2: Static Demo Artifacts

Goal:

- Create artifacts that make the demo visible before a full runtime exists.

Possible deliverables:

- Static runtime graph JSON
- Example episode metadata JSON
- Example diagnostics JSON
- Example stream mapping table
- Generated markdown or HTML report for graph, frames, latency, and policy diagnostics

Exit criteria:

- README can show concrete RoMi artifacts.
- The data contracts are reviewable before bridge or replay code exists.

## Milestone 3: Minimal Live Bridge

Goal:

- Connect selected ROS2 or simulator streams to RoMi demo stream names.

Current status:

- Bridge boundary scaffolded in `bridges/ros2/`.
- Demo-specific bridge plan scaffolded in `examples/navigation_manipulation_demo/ros2-bridge-plan.md`.
- Initial `rclpy` JSONL bridge prototype scaffolded in `bridges/ros2/rclpy_bridge/`.

Minimum streams:

- RGB image
- Depth or point cloud
- Camera info
- Joint state
- Odometry
- TF and static TF
- Task goal or marker

Exit criteria:

- Stream metadata and diagnostics are visible.
- QoS metadata is captured where available.
- The bridge remains an adapter, not the core runtime model.

## Milestone 4: Episode Record And Replay

Goal:

- Record one navigation + manipulation episode and replay it through the same logical graph.

Current status:

- Prototype episode recorder scaffolded in `tools/episode_recorder/`.
- Prototype replay source scaffolded in `tools/replay_source/`.
- Prototype mock policy scaffolded in `tools/mock_policy/`.
- Prototype dataset inspector scaffolded in `tools/dataset_inspector/`.

Deliverables:

- Episode writer direction compatible with MCAP-oriented design
- Replay source
- Replay clock metadata
- Stream gap and frame diagnostics

Exit criteria:

- A recorded episode can drive the mock policy.
- Live and replay inputs share the same stream contracts.

## Milestone 5: Mock Policy And Diagnostics

Goal:

- Show policy-runtime awareness without requiring a trained model.

Deliverables:

- Mock policy node
- Proposed action stream
- Input freshness diagnostics
- Inference latency diagnostics
- Authority boundary note or event

Exit criteria:

- The policy runs on live and replayed observations.
- Proposed actions are clearly separate from actuator authority.
- Diagnostics are readable in a video.

## Milestone 6: README Demo Video

Goal:

- Capture and embed the first README video.

Current status:

- Smoke demo script scaffolded in `examples/navigation_manipulation_demo/run_smoke_demo.sh`.
- Capture guide scaffolded in `examples/navigation_manipulation_demo/capture-guide.md`.
- Actual video has not been captured or embedded.

Deliverables:

- 60 to 90 second demo video
- README embed using GitHub video asset URL
- Short caption explaining live, replay, dataset, policy, and diagnostics

Exit criteria:

- A new visitor can understand RoMi's direction from the README in under two minutes.
- The video does not imply production readiness.
- The demo remains bridge-first and ROS2-interoperable.

## Near-Term Non-Goals

- Full runtime replacement for ROS2
- Production deployment story
- Final transport decision
- Final language decision
- Full simulator support matrix
- Real learned policy benchmark
