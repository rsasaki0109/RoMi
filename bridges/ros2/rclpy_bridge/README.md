# rclpy Bridge Prototype

Status: prototype.

This directory contains a small ROS2 bridge prototype for the navigation + manipulation README demo. It is intentionally scoped to `bridges/ros2/` so RoMi core does not become ROS2-only or Python-only.

The prototype reads a stream map JSON file, subscribes to supported ROS2 topics, and writes RoMi stream envelopes and bridge diagnostics as JSON Lines.

## Requirements

- ROS2 environment with `rclpy`
- ROS2 Python message packages for the configured stream map
- Python `numpy` for the demo publisher in `examples/navigation_manipulation_demo/ros2_demo_sim_publisher.py`
- A robot or simulator publishing the configured topics

No dependency is added at the repository root.

## Run

From the repository root, inside a sourced ROS2 environment, run the full demo
path:

```bash
source /opt/ros/<distro>/setup.bash
python3 -m pip install numpy

ROMI_DEMO_SOURCE=ros2 \
ROMI_DEMO_RUN_ID=ros2-local \
ROMI_DEMO_BRIDGE_DURATION_SEC=8 \
examples/navigation_manipulation_demo/run_smoke_demo.sh
```

The script starts the RoMi ROS2 bridge, publishes a scripted ROS2 navigation +
manipulation episode, records the bridge output, replays it, runs the mock
policy, and writes a dataset report.

If `ROS_DOMAIN_ID` is not set, the script uses an isolated demo domain so a
local ROS graph is less likely to leak unrelated topics into the smoke output.

Expected outputs:

```text
examples/navigation_manipulation_demo/artifacts/smoke/ros2-local/source-events.jsonl
examples/navigation_manipulation_demo/artifacts/smoke/ros2-local/episode/episode.json
examples/navigation_manipulation_demo/artifacts/smoke/ros2-local/replay-events.jsonl
examples/navigation_manipulation_demo/artifacts/smoke/ros2-local/policy-events.jsonl
examples/navigation_manipulation_demo/artifacts/smoke/ros2-local/dataset-report/report.md
examples/navigation_manipulation_demo/artifacts/smoke/ros2-local/dataset-report/report.json
```

Validate the generated run:

```bash
python3 tests/check_demo_contract.py examples/navigation_manipulation_demo/artifacts/smoke/ros2-local
```

To run only the bridge against an existing ROS2 robot or simulator:

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

Inspect bridge output quickly:

```bash
python3 - <<'PY'
import json
from collections import Counter
from pathlib import Path

path = Path("examples/navigation_manipulation_demo/artifacts/ros2-bridge-events.jsonl")
events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
print(Counter(event.get("kind") for event in events))
print(sorted({event.get("stream_id") for event in events if event.get("kind") == "stream_sample"}))
PY
```

Troubleshooting:

- `required command not found: ros2`: source your ROS2 setup file first.
- `ROS2 demo source dependencies are not available`: install/source the ROS2
  Python packages and install `numpy` for the demo publisher.
- Missing `/tf_static`: confirm the publisher or robot publishes static TF with
  transient-local durability. The included demo publisher does this.
- No `stream_sample` rows: verify topic names match
  `examples/navigation_manipulation_demo/stream-map.example.json`, or remap the
  source topics there.

## Output

Each line is a JSON object.

Event kinds:

- `bridge_start`
- `stream_sample`
- `diagnostic_event`
- `bridge_stop`

Large payloads such as images and point clouds are not serialized into JSON. The prototype writes payload summaries and metadata first. This keeps the bridge useful for diagnostics and video capture without pretending to solve high-throughput transport.

The stream map may contain multiple ROS2 topics for one RoMi stream. The demo uses this for `/tf` and `/tf_static`, which both emit `robot.frames.tf` samples while keeping distinct `source_topic`, QoS, and static-transform metadata.

The committed diagnostics sample is:

```text
examples/navigation_manipulation_demo/ros2-qos-diagnostics.example.json
```

It is validated by `tests/check_ros2_bridge_diagnostics.py` without requiring ROS2.

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
- `/tf_static` is represented with reliable, transient-local QoS and `static_transform` metadata.
