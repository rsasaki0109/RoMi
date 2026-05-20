# MVP Proposal

This document proposes a pre-MVP direction for RoMi. The goal is to demonstrate a small, inspectable runtime contract rather than a broad robotics framework.

## MVP Goal

Demonstrate live/replay symmetry for a simple robot or simulator data flow:

1. Bridge data from a ROS2 robot or simulator.
2. Record a structured episode.
3. Replay the episode through the same conceptual graph.
4. Run a mock policy inference node.
5. Expose basic graph, latency, frame, and stream diagnostics.
6. Load the recorded episode from a notebook-friendly dataset view.

## Suggested Demo

A ROS2 robot or simulator runs a navigation + manipulation episode and publishes:

- Camera images and camera info
- Depth or point cloud data where available
- Joint states
- Odometry
- TF and static TF
- Navigation goal, waypoint, path, or local plan
- End-effector pose or gripper state where available

RoMi bridges these streams, records an episode, replays it, runs a mock navigation + manipulation policy, and exposes graph, latency, frame, and QoS diagnostics.

The mock policy does not need to control real hardware. It can consume observation streams and emit proposed actions into a non-authoritative stream.

The target README demo video is described in [demo-video.md](demo-video.md). The concrete demo contract is defined in [demo-spec.md](demo-spec.md).

## Demonstrated Concepts

### Live/Replay Symmetry

The same downstream graph shape should accept data from either:

- A live ROS2 bridge
- A recorded episode replay source

The MVP should make differences explicit, including clock mode, replay speed, missing data, and timing behavior.

### Simple Runtime Graph

The graph should be small enough to inspect:

```text
ROS2 bridge or replay source
        |
        +-- camera / depth stream ----+
        +-- joint / gripper stream ---+--> mock nav + manipulation policy
        +-- odometry / goal stream ---+        |
        +-- frame stream -------------+        v
        |                              proposed action stream
        +----------------------------> frame diagnostics
        |
        +---------------------> recorder / dataset view
```

Expected graph diagnostics:

- Nodes and edges
- Stream schemas
- Message rates
- Latency
- Drops or gaps
- Queue depth or backlog where available
- Component health

### Structured Schemas

The MVP should define a small set of schemas:

- Image
- Camera calibration metadata
- Depth image or point cloud metadata
- Joint state
- Odometry
- Transform
- Navigation goal or waypoint
- End-effector pose
- Gripper state
- Policy observation
- Policy proposed action
- Runtime diagnostic event

Schemas should include versioning and enough metadata to support replay and notebook loading.

### MCAP-Compatible Logging Direction

The first implementation does not need to solve every logging detail, but it should be designed toward MCAP compatibility.

The MVP should record:

- Stream data
- Schema metadata
- Topic or stream names
- Timing metadata
- Frame metadata
- Runtime graph metadata
- Bridge metadata

### ROS2 Bridge Direction

The MVP bridge should focus on a narrow set of common ROS2 data:

- `sensor_msgs/Image`
- `sensor_msgs/CameraInfo`
- `sensor_msgs/JointState`
- `nav_msgs/Odometry`
- `tf2_msgs/TFMessage`
- Common navigation goal, path, and command messages where useful for the demo

The bridge should expose QoS metadata and basic diagnostics. It should not attempt to wrap the entire ROS2 API surface in the first milestone.

### Notebook-Friendly Dataset Loading

The recorded episode should be easy to inspect from a notebook or script.

Initial dataset view goals:

- List streams and schemas
- Iterate by time range
- Fetch synchronized observation windows where possible
- Access tensor-like image data without losing metadata
- Inspect frame and clock metadata

This should not require the notebook workflow to become the runtime implementation.

### Policy Inference Node Concept

The MVP should include a mock policy node to validate middleware contracts.

The node should:

- Consume observation streams
- Track input timing and freshness
- Emit proposed actions
- Report inference latency
- Avoid direct actuator authority
- Work in live and replay modes
- Support both navigation context and manipulation context

The policy node can be a stub. The important part is the runtime contract around policy inputs, outputs, timing, and authority.

### Basic Runtime Introspection

The MVP should expose:

- Graph structure
- Stream schemas and rates
- Latency and drops
- Frame graph status
- Replay clock state
- Bridge status
- Policy node input freshness and inference latency

The interface could begin as CLI output, JSON, a simple local API, or a small dashboard. The final tooling choice should follow the MVP implementation path.

## Non-Goals

The MVP should not attempt to:

- Replace ROS2
- Implement a full distributed runtime
- Support every ROS2 message type
- Provide production safety certification
- Build a complete ML training stack
- Pick a permanent transport architecture
- Support every simulator

## Success Criteria

The MVP is successful if a senior robotics engineer can inspect the demo and understand:

- How live and replay data share the same runtime contract
- How schemas are represented
- How frame and time semantics are preserved
- How a navigation + manipulation policy node fits into the graph without owning actuator authority
- How ROS2 interop works at the bridge boundary
- How recorded data can be loaded for dataset workflows
