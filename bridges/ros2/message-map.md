# ROS2 Message Map

This document defines the initial ROS2 message coverage for the navigation + manipulation demo. It is intentionally narrow.

## Mapping Principles

- Map ROS2 topics into stable RoMi stream names.
- Preserve ROS2 message type and topic metadata.
- Preserve event time and bridge receive time separately.
- Preserve frame IDs where available.
- Keep message conversion tables explicit and reviewable.
- Avoid making RoMi internal contracts mirror ROS2 message classes directly.

## Initial Required Mapping

| ROS2 message | Typical source topic | RoMi stream | Required metadata |
| --- | --- | --- | --- |
| `sensor_msgs/msg/Image` | `/camera/color/image_raw` | `robot.camera.rgb` | stamp, frame ID, encoding, width, height, step |
| `sensor_msgs/msg/Image` | `/camera/depth/image_raw` | `robot.camera.depth` | stamp, frame ID, encoding, width, height, step |
| `sensor_msgs/msg/CameraInfo` | `/camera/color/camera_info` | `robot.camera.info` | stamp, frame ID, intrinsics, distortion model |
| `sensor_msgs/msg/PointCloud2` | `/points` | `robot.camera.depth` or `robot.points` | stamp, frame ID, fields, point step, row step |
| `sensor_msgs/msg/JointState` | `/joint_states` | `robot.joints.state` | stamp, joint names, position, velocity, effort |
| `nav_msgs/msg/Odometry` | `/odom` | `robot.base.odom` | stamp, frame ID, child frame ID, pose, twist |
| `tf2_msgs/msg/TFMessage` | `/tf` | `robot.frames.tf` | parent frame, child frame, transform stamp |
| `tf2_msgs/msg/TFMessage` | `/tf_static` | `robot.frames.tf` | static transform marker |
| `geometry_msgs/msg/PoseStamped` | `/goal_pose` | `task.goal` | stamp, frame ID, pose |
| `nav_msgs/msg/Path` | `/plan` | `task.path` | stamp, frame ID, poses |
| `geometry_msgs/msg/Twist` | `/cmd_vel` or proposed command topic | `robot.base.command_observed` | linear and angular command values |

## Optional Later Mapping

These are useful but not required for the first README demo:

- `sensor_msgs/msg/Imu`
- `sensor_msgs/msg/LaserScan`
- `nav_msgs/msg/OccupancyGrid`
- `diagnostic_msgs/msg/DiagnosticArray`
- `control_msgs` action types
- `nav2_msgs` action types
- `moveit_msgs` planning and trajectory types

## Conversion Direction

Initial direction:

```text
ROS2 topic -> RoMi stream -> recorder / replay / policy / diagnostics
```

Later optional directions:

```text
RoMi proposed action -> safety gate -> ROS2 command topic
RoMi replay stream -> ROS2 republished topic
RoMi action contract -> ROS2 action client or server
```

The first demo should stop at proposed actions unless there is an explicit safety and authority boundary.
