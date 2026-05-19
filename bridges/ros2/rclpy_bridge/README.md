# rclpy Bridge Prototype

Status: prototype.

This directory contains a small ROS2 bridge prototype for the navigation + manipulation README demo. It is intentionally scoped to `bridges/ros2/` so RoMi core does not become ROS2-only or Python-only.

The prototype reads a stream map JSON file, subscribes to supported ROS2 topics, and writes RoMi stream envelopes and bridge diagnostics as JSON Lines.

## Requirements

- ROS2 environment with `rclpy`
- ROS2 Python message packages for the configured stream map
- A robot or simulator publishing the configured topics

No dependency is added at the repository root.

## Run

From the repository root, inside a sourced ROS2 environment:

```bash
python3 bridges/ros2/rclpy_bridge/romi_ros2_bridge.py \
  --stream-map examples/navigation_manipulation_demo/stream-map.example.json \
  --output examples/navigation_manipulation_demo/artifacts/ros2-bridge-events.jsonl
```

Optional:

```bash
python3 bridges/ros2/rclpy_bridge/romi_ros2_bridge.py \
  --stream-map examples/navigation_manipulation_demo/stream-map.example.json \
  --output examples/navigation_manipulation_demo/artifacts/ros2-bridge-events.jsonl \
  --diagnostics-period-sec 1.0 \
  --duration-sec 30
```

## Output

Each line is a JSON object.

Event kinds:

- `bridge_start`
- `stream_sample`
- `diagnostic_event`
- `bridge_stop`

Large payloads such as images and point clouds are not serialized into JSON. The prototype writes payload summaries and metadata first. This keeps the bridge useful for diagnostics and video capture without pretending to solve high-throughput transport.

## Current Supported ROS2 Types

- `sensor_msgs/msg/Image`
- `sensor_msgs/msg/CameraInfo`
- `sensor_msgs/msg/PointCloud2`
- `sensor_msgs/msg/JointState`
- `nav_msgs/msg/Odometry`
- `nav_msgs/msg/Path`
- `geometry_msgs/msg/PoseStamped`
- `geometry_msgs/msg/Twist`
- `tf2_msgs/msg/TFMessage`

Unsupported source types are skipped with a diagnostic event.

## Design Notes

- This is a bridge adapter, not RoMi core.
- Message conversion is explicit and narrow.
- The output envelope preserves source topic, source type, timestamps, frame ID, stream ID, and bridge receive time.
- QoS capture is currently subscription-side metadata plus runtime diagnostics. Discovery-level QoS inspection is a later step.
