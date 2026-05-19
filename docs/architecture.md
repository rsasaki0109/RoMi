# RoMi Architecture Draft

This is a high-level architecture draft for RoMi. It describes intended system boundaries and design planes. It does not choose final technologies or claim an implementation exists.

## Architecture Goals

RoMi should provide a contract layer that connects:

- Live robots
- Simulators
- Recorded logs
- Datasets
- ML policies
- Deployment runtimes
- Existing robotics middleware such as ROS2

The architecture should remain transport-agnostic, replay-first, inspectable, and simulation-native.

## Plane Model

RoMi is organized conceptually into seven planes.

### Control Plane

The control plane manages runtime graph structure and component lifecycle.

Responsibilities:

- Node and graph registration
- Lifecycle state transitions
- Dependency and health tracking
- Runtime configuration
- Supervision policies
- Start, stop, restart, degrade, and failover semantics

### Data Plane

The data plane moves typed data between producers and consumers.

Responsibilities:

- Pub/sub-style streams
- Request/response and action-like interactions
- Local and distributed data movement
- Transport adapters
- Backpressure, rate, queue, and delivery diagnostics
- Efficient movement of large payloads such as images, point clouds, and tensors

### Semantic Plane

The semantic plane describes what data means.

Responsibilities:

- Schemas and schema versions
- Time domains and clocks
- Coordinate frames and transforms
- Units, encodings, and tensor metadata
- World, map, scene, and episode identity
- Compatibility checks

### Log / Dataset Plane

The log and dataset plane makes runtime data durable and reusable.

Responsibilities:

- Episode recording
- Replay sources
- Dataset views
- MCAP-compatible logging direction
- Indexing and chunking
- Provenance and runtime metadata
- Notebook-friendly loading without losing time and frame semantics

### Interop Plane

The interop plane connects RoMi to existing systems.

Responsibilities:

- ROS2 topic, service, action, and tf2 bridges
- rosbag2 and MCAP bridges
- Simulator adapters
- Vendor SDK adapters
- DDS and other transport integration
- Migration tools and diagnostics

### Safety Plane

The safety plane defines authority and intervention boundaries.

Responsibilities:

- Actuator command authority
- Policy output gating
- Safety monitors
- Command limits
- Emergency stop integration
- Audit logs for authority changes and interventions

### Observability Plane

The observability plane makes runtime behavior inspectable.

Responsibilities:

- Graph inspection
- Stream rates, latency, drops, and queue depth
- QoS and transport diagnostics
- Frame and time diagnostics
- Policy inference diagnostics
- Health, lifecycle, and supervision events
- APIs for tools, dashboards, notebooks, and automated agents

## Diagram

```text
            +----------------------------------------------+
            |        tools, notebooks, dashboards          |
            |        tests, agents, operator UIs           |
            +----------------------+-----------------------+
                                   |
                         observability plane
                                   |
+-------------------+    +---------+----------+    +-------------------+
|   control plane   |----|   runtime graph    |----|   safety plane    |
| lifecycle, health |    | nodes and contracts|    | authority, limits |
+---------+---------+    +---------+----------+    +---------+---------+
          |                        |                         |
          |                semantic plane                    |
          |       schemas, clocks, frames, worlds            |
          |                        |                         |
+---------+------------------------+-------------------------+---------+
|                              data plane                              |
|       streams, requests, actions, transports, tensor payloads        |
+----------------------+-----------------------+-----------------------+
                       |                       |
        +--------------+----------+   +--------+----------------+
        | log / dataset plane     |   | interop plane           |
        | episodes, replay, MCAP  |   | ROS2, DDS, sims, SDKs   |
        +-------------------------+   +-------------------------+
```

## Technology Posture

RoMi should not choose final technologies prematurely.

Open design areas include:

- Schema language and compatibility model
- In-process and cross-process runtime APIs
- Shared memory strategy
- DDS and Zenoh integration boundaries
- MCAP logging layout
- Notebook and dataset APIs
- ROS2 bridge implementation strategy
- Policy runtime integration model

The architecture should allow technology choices to be evaluated against replayability, inspectability, simulation friendliness, and interoperability.
