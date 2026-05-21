# RoMi ROS2 Bridge

Status: prototype boundary with an initial `rclpy` JSONL bridge.

The ROS2 bridge is the first planned bridge adapter for RoMi. It should connect selected ROS2 topics and tf2 streams into RoMi stream names, schemas, episode recording, replay, and diagnostics.

The bridge is not RoMi core. It is an interoperability boundary.

An initial prototype is available in [rclpy_bridge](rclpy_bridge). It reads the demo stream map, subscribes to supported ROS2 topics, and writes RoMi stream envelopes and diagnostics as JSON Lines. The rclpy README includes a full scripted ROS2 smoke run, expected outputs, validation command, and troubleshooting notes. A committed diagnostics example is available at [ros2-qos-diagnostics.example.json](../../examples/navigation_manipulation_demo/ros2-qos-diagnostics.example.json).

## Purpose

The ROS2 bridge should let existing ROS2 robots and simulators participate in RoMi workflows without requiring a rewrite.

Primary goals:

- Observe selected ROS2 topics as RoMi streams.
- Preserve timestamps, frame IDs, message types, topic names, and QoS metadata.
- Bridge `/tf` and `/tf_static` into RoMi frame graph metadata.
- Feed RoMi episode recording.
- Feed replay and dataset workflows.
- Emit bridge diagnostics for graph, latency, drops, QoS, and frame health.

## Non-Goals

The first bridge should not:

- Replace ROS2.
- Wrap the entire ROS2 API.
- Support every ROS2 message type.
- Make DDS the only RoMi transport.
- Make RoMi internals depend on ROS2 names, QoS policies, or message classes.
- Claim production readiness.

## Boundary

```text
ROS2 graph
  topics / tf2 / QoS / node metadata
        |
        v
RoMi ROS2 bridge adapter
  message mapping / timestamp capture / frame capture / QoS capture
        |
        v
RoMi contracts
  streams / schemas / runtime graph / episode metadata / diagnostics
```

The bridge may use a ROS2 client library when implemented. That implementation choice should stay inside `bridges/ros2/` and should not become a RoMi-wide language or transport decision.

## Initial Demo Scope

The first bridge should support the navigation + manipulation README demo.

Required source coverage:

| RoMi stream | ROS2 direction | Notes |
| --- | --- | --- |
| `robot.camera.rgb` | `sensor_msgs/msg/Image` | RGB image observation |
| `robot.camera.depth` | `sensor_msgs/msg/Image` or `sensor_msgs/msg/PointCloud2` | Depth or spatial observation |
| `robot.camera.info` | `sensor_msgs/msg/CameraInfo` | Camera calibration |
| `robot.joints.state` | `sensor_msgs/msg/JointState` | Manipulator state |
| `robot.base.odom` | `nav_msgs/msg/Odometry` | Navigation state |
| `robot.frames.tf` | `tf2_msgs/msg/TFMessage` from `/tf` and `/tf_static` | Frame graph |
| `task.goal` | `geometry_msgs/msg/PoseStamped` or equivalent | Navigation or manipulation target |
| `task.path` | `nav_msgs/msg/Path` where available | Navigation plan |

Derived RoMi streams:

| RoMi stream | Producer | Notes |
| --- | --- | --- |
| `policy.observation` | observation synchronizer | Synchronized policy input |
| `policy.proposed_action` | mock policy | Non-authoritative action proposal |
| `runtime.diagnostics` | bridge and diagnostics nodes | Graph, QoS, latency, frame, and policy diagnostics |

## Stream Envelope Direction

Bridge output should eventually use a common stream envelope.

Expected fields:

- `stream_id`
- `schema_id`
- `source_system`
- `source_topic`
- `source_message_type`
- `event_time_ns`
- `bridge_receive_time_ns`
- `clock_domain`
- `frame_id` where available
- `payload_ref` or payload value
- `metadata`

Large payloads such as images, depth frames, and point clouds should allow future zero-copy or external-payload strategies. The first demo can use simpler payload handling if the boundary is explicit.

## tf2 Handling

The bridge should treat transforms as semantic runtime data, not just messages.

Requirements:

- Subscribe to `/tf` and `/tf_static`.
- Preserve parent frame, child frame, transform timestamp, and static transform semantics.
- Emit frame graph metadata for episodes.
- Emit diagnostics for missing, stale, cyclic, conflicting, or disconnected transforms.
- Preserve recorded time for replay.

The current prototype maps both `/tf` and `/tf_static` into `robot.frames.tf` while preserving `source_topic` on each sample. `/tf_static` uses reliable, transient-local QoS metadata and is marked as a static transform source in diagnostics.

## QoS Diagnostics

The bridge should expose QoS because many ROS2 integration bugs are QoS bugs.

Capture where available:

- Reliability
- Durability
- History
- Depth
- Deadline
- Lifespan
- Liveliness
- Lease duration

Diagnostics should report:

- Incompatible QoS settings
- Missing publishers or subscribers
- Sample gaps
- Queue growth
- Deadline misses where available
- Bridge backpressure

The committed diagnostics sample is validated in CI without a ROS2 installation. It checks that QoS metadata is present, `/tf_static` remains visible, and policy output remains non-authoritative.

## Services And Actions

Services and actions are planned after the topic/tf2 demo path.

Initial direction:

- Preserve service request/response semantics where RoMi needs request-style contracts.
- Preserve action goal, feedback, result, cancellation, and timeout semantics where RoMi needs action-style contracts.
- Avoid flattening action workflows into plain topic messages when semantics matter.

The README demo does not require service or action bridging.

## Recording And Replay

The bridge should feed episode recording with enough metadata to replay and inspect later:

- ROS2 source topic
- ROS2 message type
- QoS metadata where available
- Source timestamp
- Bridge receive timestamp
- Frame metadata
- Stream schema ID
- Runtime graph node ID

Replay should not require a live ROS2 graph for RoMi-side policy and diagnostics evaluation. A later reverse bridge may republish replayed RoMi streams into ROS2 when useful, but that is not required for the first demo.

## Implementation Notes

The first prototype uses `rclpy` because it is the fastest path to a README demo. This does not make RoMi Python-only.

Implementation constraints:

- A practical ROS2 bridge will use an existing ROS2 client library.
- The bridge should publish RoMi stream metadata independent of that client library.
- The bridge should be testable with recorded or simulated ROS2 data.
- The bridge should keep message conversion tables explicit.
- Bridge diagnostics should be available before the full runtime UI exists.
- Large payloads should not be forced through JSON in the final design. The prototype writes payload summaries first.

## Related Files

- [ROS2 interop document](../../docs/ros2-interop.md)
- [Navigation + manipulation demo spec](../../docs/demo-spec.md)
- [Demo backlog](../../docs/demo-backlog.md)
- [Example bridge plan](../../examples/navigation_manipulation_demo/ros2-bridge-plan.md)
