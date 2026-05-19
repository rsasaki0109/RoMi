# ROS2 Interoperability

RoMi should be ROS2-interoperable by design. The goal is bridge-first integration, not replacement-first migration.

ROS2 remains valuable for robot drivers, Nav2, Autoware, simulator integrations, visualization, tf2, actions, lifecycle components, and distributed systems built on DDS. RoMi should preserve access to that ecosystem while adding replay-first, dataset-aware, policy-runtime aware contracts.

## Bridge-First Strategy

A bridge-first approach lets teams evaluate RoMi incrementally:

- Existing ROS2 systems can keep running.
- RoMi can observe, record, replay, and inspect selected streams first.
- Teams can add policy or dataset workflows without rewriting every driver and subsystem.
- Migration risk stays bounded to explicit bridge boundaries.
- ROS2 tooling remains available during transition.

Replacement-first would require recreating too much ecosystem surface before proving RoMi's value.

## ROS2 Topic Bridge

The topic bridge should map ROS2 topics into RoMi streams and, where appropriate, map RoMi streams back into ROS2 topics.

Design requirements:

- Preserve topic name, type, schema, namespace, and publisher/subscriber metadata.
- Preserve timestamps and distinguish message time from bridge receive time.
- Preserve or expose ROS2 QoS configuration.
- Support common robotics data such as images, camera info, point clouds, IMU, odometry, joint states, diagnostics, and commands.
- Avoid assuming every RoMi stream must be a ROS2 topic internally.

## tf2 Bridge

The tf2 bridge should preserve coordinate frame semantics across ROS2 and RoMi.

Design requirements:

- Bridge `/tf` and `/tf_static` into RoMi frame graph representations.
- Preserve frame IDs, parent-child relationships, timestamps, and static transform semantics.
- Provide diagnostics for missing, stale, cyclic, conflicting, or disconnected transforms.
- Support replay of frame data with recorded time and simulation time.
- Allow RoMi tools to inspect frame graphs without requiring direct ROS2 tooling.

## rosbag2 / MCAP Bridge

RoMi should support log interop rather than treating logs as one-way exports.

Design requirements:

- Read relevant rosbag2 storage formats where practical.
- Treat MCAP compatibility as a core logging direction.
- Preserve ROS2 message metadata, schema information, QoS metadata where available, and timing information.
- Allow recorded ROS2 data to feed RoMi replay graphs.
- Allow RoMi episodes to be exported or viewed with MCAP-compatible tooling where feasible.

## Service And Action Bridge

ROS2 services and actions are important for command, planning, navigation, manipulation, and lifecycle workflows.

Design requirements:

- Bridge service request/response interactions into RoMi request contracts where appropriate.
- Bridge long-running ROS2 actions into RoMi action-like contracts where appropriate.
- Preserve goal, feedback, result, cancellation, and timeout semantics.
- Expose diagnostics for latency, failures, retries, and cancellation behavior.
- Avoid flattening long-running actions into simple messages when semantics matter.

## QoS Diagnostics

QoS behavior is often a source of integration failures.

Design requirements:

- Expose reliability, durability, history, depth, deadline, lifespan, liveliness, and lease duration where available.
- Detect incompatible publisher/subscriber QoS settings.
- Report message loss, queue growth, deadline misses, and bridge backpressure.
- Include QoS metadata in logs when useful for replay and debugging.
- Make transport assumptions visible to users and tools.

## Nav2 Migration Strategy

Nav2 users should be able to adopt RoMi incrementally.

Possible path:

1. Bridge ROS2 sensor, odometry, map, TF, costmap, path, goal, and command topics.
2. Record and replay navigation episodes through RoMi.
3. Add graph, latency, QoS, and frame diagnostics around the existing Nav2 stack.
4. Introduce policy or evaluation nodes that consume replayed navigation data.
5. Move selected non-driver components behind RoMi contracts only when the contract is clearer than the ROS2 boundary.

RoMi should not require replacing Nav2 to provide value.

## Autoware Migration Strategy

Autoware-style systems have large graphs and strong requirements for introspection, replay, simulation, and safety.

Possible path:

1. Bridge selected perception, localization, planning, control, TF, map, and diagnostic streams.
2. Record scenario episodes in an MCAP-compatible direction.
3. Use RoMi replay to run evaluation and policy experiments against recorded scenarios.
4. Add diagnostics for latency, transforms, QoS, and authority boundaries.
5. Keep ROS2 and DDS deployment paths available while RoMi contracts are evaluated.

RoMi should support coexistence with Autoware-style architectures before proposing migration of core components.

## Interop Principles

- Preserve semantics before optimizing convenience.
- Make bridge boundaries explicit and observable.
- Treat ROS2 metadata as useful runtime context, not disposable adapter detail.
- Keep RoMi internal contracts independent from ROS2-specific assumptions where possible.
- Prefer incremental migration paths over ecosystem replacement.
