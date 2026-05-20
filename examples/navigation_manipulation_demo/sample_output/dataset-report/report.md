# Dataset Report: nav_manip_demo_sample

Prototype RoMi dataset inspection report.

This committed sample shows the shape of the report produced by:

```bash
examples/navigation_manipulation_demo/run_smoke_demo.sh
```

It is a static reference artifact for README review. Fresh local runs write ignored output under `examples/navigation_manipulation_demo/artifacts/`.

## Episode

- Scenario: `navigation_to_table_and_mock_pick`
- Mode: `simulation`
- World: `demo_world`
- Robot: `mobile_manipulator_demo`
- Clock domain: `sim_time`
- Start time ns: `0`
- End time ns: `15916666603`

## Streams

| Stream | Samples | Type | Frames |
| --- | ---: | --- | --- |
| robot.base.odom | 192 | romi.robotics.OdometrySummary | odom |
| robot.camera.depth | 192 | romi.robotics.ImageSummary | camera_depth_optical_frame |
| robot.camera.info | 192 | romi.robotics.CameraInfoSummary | camera_color_optical_frame |
| robot.camera.rgb | 192 | romi.robotics.ImageSummary | camera_color_optical_frame |
| robot.frames.tf | 192 | romi.robotics.TransformTreeSummary | map->odom |
| robot.joints.state | 192 | romi.robotics.JointStateSummary | base_link |
| task.goal | 16 | romi.robotics.PoseGoalSummary | map |

## Diagnostics

- Events: `32`
- By severity: `{'info': 32}`
- By category: `{'native_sim': 32}`

## Policy

- Proposed action samples: `16`
- Freshness status: `{'robot.base.odom:ok': 16, 'robot.camera.depth:ok': 16, 'robot.camera.info:ok': 16, 'robot.camera.rgb:ok': 16, 'robot.frames.tf:ok': 16, 'robot.joints.state:ok': 16, 'task.goal:ok': 16}`

| Time ns | Actions | Authority | Latency ms |
| ---: | ---: | --- | ---: |
| 0 | 3 | proposed_only | 0.004 |
| 999999996 | 3 | proposed_only | 0.004 |
| 1999999992 | 3 | proposed_only | 0.004 |
| 2999999988 | 3 | proposed_only | 0.004 |
| 3999999984 | 3 | proposed_only | 0.004 |
| 4999999980 | 3 | proposed_only | 0.004 |
| 5999999976 | 3 | proposed_only | 0.004 |
| 6999999972 | 3 | proposed_only | 0.004 |
| 7999999968 | 3 | proposed_only | 0.004 |
| 8999999964 | 3 | proposed_only | 0.004 |

## Policy Compare Artifact

RoMi Studio can replay the episode state, compare the baseline mock policy against a guarded counterfactual policy, and export review artifacts:

- Markdown: [`../policy_compare.md`](../policy_compare.md)
- JSON: [`../policy_compare.json`](../policy_compare.json)
- Safety boundary: `proposed_only`, actuator authority `none`, command stream `not_emitted`

## Observation Window

- Target time ns: `0`
- Window ms: `250.0`

| Stream | Status | Delta ms | Frame | Payload Summary |
| --- | --- | ---: | --- | --- |
| robot.base.odom | ok | 0.0 | odom | `{"child_frame_id": "base_link", "position": {"x": 0.0, "y": 0.0, "z": 0.0}, "stage": "initialize"}` |
| robot.camera.depth | ok | 0.0 | camera_depth_optical_frame | `{"data_len": 28800, "encoding": "16UC1", "height": 90, "step": 320, "synthetic_scene": {"object_state": "on_table", "target_depth_mm": 620}, "width": 160}` |
| robot.camera.info | ok | 0.0 | camera_color_optical_frame | `{"d_len": 0, "distortion_model": "plumb_bob", "height": 90, "k_len": 9, "p_len": 12, "width": 160}` |
| robot.camera.rgb | ok | 0.0 | camera_color_optical_frame | `{"data_len": 43200, "encoding": "rgb8", "height": 90, "step": 480, "synthetic_scene": {"object_state": "on_table", "target_visible": true}, "width": 160}` |
| robot.frames.tf | ok | 0.0 | map->odom | `{"transform_count": 6, "frames_sample": [{"parent_frame_id": "map", "child_frame_id": "odom", "stamp_ns": 0}], "synthetic_base_translation": {"x": 0.0, "y": 0.0, "z": 0.0}}` |
| robot.joints.state | ok | 0.0 | base_link | `{"joint_count": 7, "position_count": 7, "velocity_count": 7, "effort_count": 7, "joint_names_sample": ["waist_yaw", "torso_lift", "right_shoulder_pitch", "right_elbow", "right_wrist", "gripper_left", "gripper_right"]}` |
| task.goal | ok | 0.0 | map | `{"position": {"x": 1.6, "y": 0.0, "z": 0.0}, "scenario_id": "romi_2d_nav_manip_demo", "target_object": "orange_cube"}` |

This report is a prototype dataset view. It preserves stream, time, frame, diagnostics, and policy metadata for inspection.
