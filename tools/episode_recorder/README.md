# Episode Recorder Prototype

Status: prototype.

This tool turns RoMi bridge JSONL output into a small episode directory. It is intended for the README navigation + manipulation demo path:

```text
ROS2 bridge JSONL -> episode directory -> replay source -> mock policy / diagnostics
```

The recorder does not implement MCAP yet. It preserves an MCAP-compatible direction by keeping stream IDs, schemas, timing, frame metadata, source topic metadata, and diagnostics explicit.

## Run

From the repository root:

```bash
python3 tools/episode_recorder/romi_record_episode.py \
  --input examples/navigation_manipulation_demo/artifacts/ros2-bridge-events.jsonl \
  --output examples/navigation_manipulation_demo/artifacts/episodes/nav_manip_demo_001 \
  --episode-id nav_manip_demo_001 \
  --scenario-name navigation_to_table_and_mock_pick \
  --mode simulation \
  --world-id demo_world \
  --robot-id mobile_manipulator_demo \
  --runtime-graph examples/navigation_manipulation_demo/runtime-graph.example.json
```

## Output

The output directory contains:

- `events.jsonl`: copied bridge events
- `episode.json`: episode metadata
- `streams.json`: stream summary
- `diagnostics.json`: diagnostics summary and sampled events
- `README.md`: human-readable episode summary

## Notes

- Large payloads are not moved by this prototype.
- The recorder expects bridge events shaped like `bridges/ros2/rclpy_bridge`.
- This is a demo tool, not a storage format commitment.
