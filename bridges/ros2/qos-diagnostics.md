# ROS2 QoS Diagnostics

QoS diagnostics are part of the first ROS2 bridge design because silent QoS mismatches can make robotics demos and deployments hard to debug.

## QoS Fields To Capture

When available from ROS2 discovery or subscription configuration, capture:

- Reliability
- Durability
- History
- Depth
- Deadline
- Lifespan
- Liveliness
- Lease duration
- Avoid ROS namespace and topic remapping loss

## Diagnostics To Emit

The bridge should emit diagnostic events for:

- No publisher discovered for required topic
- No compatible publisher discovered for required topic
- Publisher/subscriber QoS mismatch
- Sample gaps
- Message age above configured threshold
- Queue growth or bridge backpressure
- Deadline miss where available
- Unexpected topic type
- Multiple publishers with conflicting metadata

## Minimal Diagnostic Shape

```json
{
  "schema_version": "0.1.0",
  "event_id": "qos_warning_001",
  "time": {
    "event_time_ns": 12000000000,
    "clock_domain": "sim_time"
  },
  "severity": "warning",
  "source": "ros2_bridge",
  "category": "qos",
  "message": "Observed one sample gap on robot.base.odom.",
  "attributes": {
    "stream_id": "robot.base.odom",
    "source_topic": "/odom",
    "source_message_type": "nav_msgs/msg/Odometry",
    "expected_rate_hz": 50.0,
    "observed_gap_ms": 80.0
  }
}
```

This shape should remain compatible with `schemas/core/diagnostic_event.schema.json`.

## README Demo Requirement

The README demo should show at least one QoS or bridge diagnostic panel or report, even if the first run is healthy. It should be clear that bridge metadata is observable.
