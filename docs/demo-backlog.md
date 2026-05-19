# Demo Backlog

This backlog turns the navigation + manipulation demo spec into implementation-sized work items. It is written so each item can become a GitHub issue.

## 1. Define Static Demo Stream Map

Labels: `documentation`, `schema`, `demo`

Status: scaffolded in `examples/navigation_manipulation_demo/stream-map.example.json`.

Problem:

The README demo needs stable stream names before bridge, replay, or policy code exists.

Scope:

- Define source topic to RoMi stream mapping.
- Include navigation, manipulation, frame, policy, and diagnostics streams.
- Document required metadata for each stream.

Acceptance criteria:

- Stream names match `docs/demo-spec.md`.
- Each stream has purpose, source direction, expected rate if known, and required metadata.
- The mapping does not assume one simulator or transport.

## 2. Draft Demo Schema Sketches

Labels: `schema`, `demo`

Status: scaffolded in `schemas/`.

Problem:

The demo needs structured data contracts for observations, actions, diagnostics, and episode metadata.

Scope:

- Sketch schemas for image metadata, depth or point cloud metadata, joint state, odometry, transform, task goal, policy observation, proposed action, and diagnostics event.
- Include schema version fields.
- Include time and frame references where relevant.

Acceptance criteria:

- Schemas are reviewable before implementation.
- Tensor-like payload metadata includes shape, dtype, layout, encoding, and frame or camera context where relevant.
- Proposed action schema is separate from actuator command authority.

## 3. Create Example Episode Metadata

Labels: `replay`, `dataset`, `demo`

Status: scaffolded in `examples/navigation_manipulation_demo/episode-metadata.example.json`.

Problem:

The demo needs a concrete episode shape to guide recording, replay, and dataset inspection.

Scope:

- Add sample episode metadata.
- Include stream list, schema versions, clock mode, bridge metadata, frame graph metadata, and policy metadata.
- Keep MCAP compatibility as a design direction.

Acceptance criteria:

- Metadata can describe one navigation + manipulation run.
- Live and replay modes can refer to the same stream IDs.
- Runtime graph metadata is present.

## 4. Add Static Diagnostics Report

Labels: `observability`, `demo`

Status: scaffolded in `examples/navigation_manipulation_demo/diagnostics.example.json`.

Problem:

The README video needs something visible before a full runtime UI exists.

Scope:

- Create a static or generated diagnostics report format.
- Include graph, stream rates, latency, drops, frame status, replay clock state, QoS metadata, and policy freshness.
- Make the output suitable for video capture.

Acceptance criteria:

- A reviewer can inspect the graph and runtime state from the report.
- Diagnostics clearly separate bridge, replay, policy, and recorder status.
- No production readiness is implied.

## 5. Implement Minimal ROS2 Bridge Path

Labels: `bridge`, `ros2`, `demo`

Status: initial `rclpy` JSONL prototype scaffolded in `bridges/ros2/rclpy_bridge/`.

Problem:

The demo needs a bridge-first path from ROS2 or simulator topics into RoMi stream names.

Scope:

- Support selected common ROS2 messages from the demo spec.
- Preserve timestamps, frame IDs, and QoS metadata where available.
- Emit bridge diagnostics.

Acceptance criteria:

- Required source streams can be observed through RoMi stream names.
- QoS metadata is visible.
- The bridge remains an adapter, not the core runtime model.

## 6. Add Episode Recorder

Labels: `replay`, `mcap`, `demo`

Status: prototype scaffolded in `tools/episode_recorder/`.

Problem:

The demo must record a structured episode.

Scope:

- Record selected streams and metadata.
- Preserve event time, bridge receive time, and schema metadata.
- Keep the file format path compatible with MCAP-oriented design.

Acceptance criteria:

- One demo episode can be recorded.
- The episode includes stream, schema, time, frame, graph, bridge, and policy metadata.
- Missing streams or schema mismatches are reported.

## 7. Add Replay Source

Labels: `replay`, `runtime`, `demo`

Status: prototype scaffolded in `tools/replay_source/`.

Problem:

The demo must replay recorded data through the same logical graph as live input.

Scope:

- Read the recorded episode.
- Re-emit streams by recorded event time.
- Expose replay clock state.
- Surface gaps and frame issues.

Acceptance criteria:

- Mock policy can run against replayed observations.
- Live and replay paths share stream names and schema assumptions.
- Replay mode is visible in diagnostics.

## 8. Add Mock Policy Node

Labels: `runtime`, `policy`, `demo`

Status: prototype scaffolded in `tools/mock_policy/`.

Problem:

The demo needs to show policy-runtime awareness without requiring a real learned model.

Scope:

- Consume synchronized observations.
- Emit proposed base, end-effector, or gripper actions.
- Report input freshness and inference latency.
- Avoid direct actuator authority.

Acceptance criteria:

- The policy runs in live and replay modes.
- Proposed actions are visible in diagnostics.
- The authority boundary is explicit.

## 9. Add Dataset Inspection View

Labels: `dataset`, `tooling`, `demo`

Status: prototype scaffolded in `tools/dataset_inspector/`.

Problem:

The demo must show that recorded episodes can become inspectable dataset artifacts.

Scope:

- Provide a notebook, script, or report that opens one episode.
- List streams, schemas, time range, sample counts, and synchronized observation windows.
- Show frame and clock metadata.

Acceptance criteria:

- A recorded episode can be inspected without running the live robot or simulator.
- Dataset view preserves runtime semantics.
- The output is clear enough for the README video.

## 10. Capture README Demo Video

Labels: `documentation`, `demo`

Status: smoke script and capture guide scaffolded in `examples/navigation_manipulation_demo/`. Actual video capture has not been performed.

Problem:

The README needs a short video that communicates RoMi's direction.

Scope:

- Capture simulator or robot view.
- Capture graph, recording, replay, policy, diagnostics, and dataset view.
- Upload the video as a GitHub asset.
- Embed the asset URL in README.

Acceptance criteria:

- Video is 60 to 90 seconds.
- The README explains live, replay, dataset, policy, and diagnostics.
- The video does not imply production readiness.
