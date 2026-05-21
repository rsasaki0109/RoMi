# RoMi Schemas

These schemas are early drafts used to make RoMi's runtime contracts explicit. They are not stable API commitments.

Current purpose:

- Make demo streams and metadata reviewable.
- Separate robot semantics from transport details.
- Preserve time, frame, graph, replay, policy, and diagnostics context.
- Provide a concrete starting point for JSON, MCAP, notebook, bridge, and replay tooling discussions.

Suggested directories:

- `core/`: episode, runtime graph, clocks, diagnostics, lifecycle, and observability metadata
- `robotics/`: images, camera info, point clouds, odometry, joint state, transforms, goals, and commands
- `ml/`: policy observations, proposed actions, embeddings, model outputs, and evaluation metadata
- `observability/`: bridge, QoS, frame, latency, and runtime inspection reports

Current ML report schemas:

- `ml/policy_io.schema.json`: non-authoritative policy proposed-action payload
  summaries
- `ml/policy_compare.schema.json`: counterfactual policy comparison at one replay time
- `ml/evaluation_timeline.schema.json`: replay-wide policy evaluation timeline

Both ML report schemas currently include runtime graph metadata so generated
artifacts identify the source, replay, policy, evaluation, and safety-boundary
nodes that produced the report.

Current core report schemas:

- `core/stream_sample.schema.json`: shared stream sample event envelope
- `core/lifecycle_event.schema.json`: shared start/stop event envelope
- `core/report_manifest.schema.json`: committed report artifact manifest
- `core/dataset_report.schema.json`: dataset inspection report, including
  schema-linked observation window rows
- `core/safety_authority.schema.json`: safety and actuator authority boundary report

Current observability schemas:

- `observability/ros2_bridge_diagnostics.schema.json`: ROS2 bridge topic, QoS, TF, timing, and limitation diagnostics report

Current robotics payload summary schemas:

- `robotics/image_summary.schema.json`: RGB and depth image summary payloads
- `robotics/camera_info_summary.schema.json`: camera calibration summary payloads
- `robotics/joint_state_summary.schema.json`: joint state summary payloads
- `robotics/odometry_summary.schema.json`: odometry summary payloads
- `robotics/transform_tree_summary.schema.json`: TF summary payloads
- `robotics/task_goal_summary.schema.json`: task goal summary payloads

These drafts should remain small until the MVP implementation validates the contracts.
