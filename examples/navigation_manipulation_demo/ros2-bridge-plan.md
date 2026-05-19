# ROS2 Bridge Plan For Navigation + Manipulation Demo

This plan connects the demo specification to the ROS2 bridge boundary. It is not an implementation yet.

## Goal

Use a ROS2 robot or simulator as the first data source for the README demo:

```text
ROS2 simulator or robot
        |
        v
RoMi ROS2 bridge
        |
        +-- runtime graph metadata
        +-- episode recorder input
        +-- observation synchronizer input
        +-- frame and QoS diagnostics
```

The bridge should prove that RoMi can interoperate with ROS2 without becoming ROS2-only.

## Required Topics

The exact source topic names may be remapped per simulator. The demo should keep RoMi stream names stable.

| Required | ROS2 topic example | ROS2 type | RoMi stream |
| --- | --- | --- | --- |
| yes | `/camera/color/image_raw` | `sensor_msgs/msg/Image` | `robot.camera.rgb` |
| yes | `/camera/depth/image_raw` | `sensor_msgs/msg/Image` | `robot.camera.depth` |
| yes | `/camera/color/camera_info` | `sensor_msgs/msg/CameraInfo` | `robot.camera.info` |
| yes | `/joint_states` | `sensor_msgs/msg/JointState` | `robot.joints.state` |
| yes | `/odom` | `nav_msgs/msg/Odometry` | `robot.base.odom` |
| yes | `/tf` | `tf2_msgs/msg/TFMessage` | `robot.frames.tf` |
| yes | `/tf_static` | `tf2_msgs/msg/TFMessage` | `robot.frames.tf` |
| yes | `/goal_pose` | `geometry_msgs/msg/PoseStamped` | `task.goal` |
| optional | `/plan` | `nav_msgs/msg/Path` | `task.path` |
| optional | `/cmd_vel` | `geometry_msgs/msg/Twist` | `robot.base.command_observed` |

## Bridge Output

For each mapped stream, the bridge should expose:

- RoMi stream ID
- Source topic
- Source message type
- Source timestamp
- Bridge receive timestamp
- Clock domain
- Frame ID where available
- QoS metadata where available
- Payload reference or converted payload
- Diagnostics status

## Demo Runtime Nodes

The first demo graph should include:

- `ros2_bridge`
- `episode_recorder`
- `replay_source`
- `observation_synchronizer`
- `mock_nav_manip_policy`
- `diagnostics_reporter`
- Optional `dataset_reporter`

## First Diagnostic Checks

The bridge should report:

- Required topic discovery status
- Message rate by stream
- Source timestamp age
- Bridge latency
- Frame ID presence
- `/tf` and `/tf_static` availability
- QoS metadata where available
- Missing or stale stream warnings

## First Success Criteria

The ROS2 bridge path is good enough for the first demo when:

- Required streams appear with stable RoMi stream names.
- Frame and timestamp metadata are preserved.
- The bridge can feed the static runtime graph shape.
- Episode metadata can reference bridge source topics.
- Diagnostics show stream rates, latency, QoS metadata, and frame status.
- The mock policy can consume observations from live bridged data or replayed data.

## Implementation Constraint

The bridge implementation may use a ROS2 client library, but RoMi core contracts should remain independent from that choice. The implementation should live under `bridges/ros2/` or a clearly scoped bridge package when the language stack is selected.
