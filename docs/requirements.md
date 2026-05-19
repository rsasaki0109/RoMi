# Requirements For Next-Generation Robotics Middleware

This document captures early requirements for RoMi. These are design requirements, not claims about implemented functionality.

## Transport-Agnostic Data Plane

RoMi should separate data semantics from transport mechanics.

Requirements:

- Support multiple transport adapters over time, such as local IPC, shared memory, DDS, Zenoh, simulator APIs, vendor SDKs, and log readers.
- Avoid exposing transport-specific assumptions as core application contracts.
- Allow transport capabilities and limitations to be inspected at runtime.
- Preserve metadata needed for timing, reliability, ordering, and diagnostics.

## Online/Offline Symmetry

Live, simulated, replayed, and dataset-backed execution should share the same conceptual runtime model where practical.

Requirements:

- Allow logs and datasets to act as graph data sources.
- Allow replay to exercise the same downstream nodes used in live execution.
- Preserve event time, receive time, processing time, and replay time.
- Make deterministic replay a design goal where the underlying components allow it.

## Tensor-Native And Schema-Native Data Model

Robot data should be explicit enough for middleware and efficient enough for ML workflows.

Requirements:

- Provide schema definitions for common robotics and ML data types.
- Represent images, point clouds, proprioception, actions, embeddings, and model outputs without lossy conventions.
- Support versioning and compatibility checks for schemas.
- Make tensor metadata explicit, including shape, dtype, layout, device, encoding, and units where relevant.
- Support structured validation and introspection.

## Time, Frame, And World Semantics

RoMi should preserve the context needed to interpret robot data.

Requirements:

- Represent clocks and clock domains explicitly.
- Preserve transform trees and frame relationships across live execution, replay, and datasets.
- Track world or scene identifiers when data spans simulation scenarios, maps, or environments.
- Expose diagnostics for missing, stale, conflicting, or inconsistent frame data.
- Support simulation time and recorded time without hiding the distinction.

## Dataset-Native Logging

Logging should serve both robotics debugging and ML dataset workflows.

Requirements:

- Record structured episodes with schema, timing, frame, transport, and provenance metadata.
- Preserve enough information for replay, evaluation, and dataset extraction.
- Keep MCAP compatibility as an important design direction.
- Support chunked, indexed, and inspectable logs.
- Allow notebook-friendly loading without discarding runtime semantics.

## Replay-First Runtime

Replay should be a primary runtime mode, not an afterthought.

Requirements:

- Run graph components from recorded streams.
- Control replay speed, seeking, pausing, stepping, and clock behavior.
- Compare live and replayed graph behavior.
- Surface replay determinism limits.
- Support replay-based evaluation of policy nodes.

## Runtime Introspection

RoMi should make the running system inspectable.

Requirements:

- Expose the runtime graph, nodes, streams, schemas, rates, latency, drops, queue depth, and backpressure.
- Provide frame and time diagnostics.
- Expose policy inputs, outputs, confidence metadata, latency, and authority boundaries where available.
- Make observability available to tools, notebooks, and automated agents.

## Lifecycle And Supervision

Distributed robot components need explicit lifecycle and supervision contracts.

Requirements:

- Define component states such as configured, active, degraded, failed, and stopped.
- Support restart, dependency, and health policies.
- Provide lifecycle events that are loggable and replayable.
- Preserve enough state to understand runtime failures after the fact.

## Simulation Friendliness

Simulation should be a first-class execution mode.

Requirements:

- Support simulation clocks and deterministic stepping where available.
- Preserve scenario, world, map, asset, and simulator metadata.
- Allow simulator streams to connect through the same graph contracts as live robot streams.
- Support replay from simulated episodes and comparison against live episodes.
- Avoid binding the core architecture to a single simulator.

## Deployment Friendliness

RoMi should support deployment-oriented robot runtime contracts.

Requirements:

- Make resource, lifecycle, health, and authority boundaries explicit.
- Support policy inference nodes without assuming one ML framework.
- Expose latency and throughput budgets.
- Allow components to be placed across CPUs, GPUs, accelerators, hosts, and processes.
- Keep runtime assumptions inspectable for production debugging.

## ROS2/DDS/MCAP Interoperability

RoMi should interoperate with existing robotics infrastructure.

Requirements:

- Bridge ROS2 topics, services, actions, parameters where appropriate, and tf2 transforms.
- Preserve ROS2 QoS metadata and expose diagnostics for incompatible QoS settings.
- Support rosbag2 and MCAP bridge paths.
- Allow DDS-backed deployments without making DDS the only transport.
- Provide migration paths for systems using Nav2, Autoware, simulator stacks, and robot drivers.

## AI-Agent-Friendly Developer Experience

The repository and tools should be readable by humans and automation.

Requirements:

- Keep repository structure predictable and modular.
- Make schemas, runtime contracts, bridges, and examples easy to locate.
- Prefer explicit docs over hidden conventions.
- Provide small examples that can be inspected and replayed.
- Keep architecture decisions traceable.

## Safety And Actuator Authority Boundaries

Middleware for policy deployment must make authority explicit.

Requirements:

- Represent which component has authority to command actuators.
- Distinguish proposed actions, filtered actions, approved actions, and applied commands.
- Support policy gates, safety monitors, limits, and emergency stop integration.
- Log authority changes and safety interventions.
- Avoid making ML policy output equivalent to actuator command authority by default.
