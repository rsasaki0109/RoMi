# RoMi Bridges

Bridges connect RoMi contracts to existing robotics systems, simulators, logs, and vendor SDKs.

Bridge design principle:

> A bridge is an adapter at the boundary. It must not make the RoMi core depend on one robotics framework, transport, simulator, or language runtime.

Planned bridge areas:

- `ros2/`: ROS2 topics, tf2, QoS metadata, services/actions direction, rosbag2/MCAP interop direction
- `mcap/`: MCAP-compatible episode logging and reading direction
- `simulators/`: simulator adapters and scenario metadata direction

Current focus:

- ROS2 bridge path for the navigation + manipulation README demo.
