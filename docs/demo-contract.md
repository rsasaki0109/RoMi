# Navigation + Manipulation Demo Contract

This document defines the current contract demonstrated by the RoMi navigation + manipulation demo. It is narrower than the RoMi architecture vision and should be read as a pre-MVP contract target, not a final runtime specification.

The goal is to make the README demo inspectable as middleware work:

- A simulator or robot source emits stable RoMi stream envelopes.
- The same logical stream graph can be recorded and replayed.
- A mock policy can run over replayed observations.
- Policy output remains non-authoritative.
- A dataset report can inspect streams, time, frames, diagnostics, and policy output.

## Current Scope

In scope:

- ROS2-free native source for the demo scenario
- Browser simulator capture using the same scenario
- Structured JSONL stream samples
- Episode recording
- Replay source
- Mock `policy.proposed_action`
- Dataset report
- CI contract checks for the smoke path

Out of scope:

- Production robot runtime
- Full ROS2 replacement
- Final storage format
- Final transport choice
- Real learned policy quality
- Hardware actuator authority
- Safety certification

## Scenario Contract

The demo scenario is defined in [scenario.json](../examples/navigation_manipulation_demo/scenario.json).

The machine-readable demo contract is defined in [contract.example.json](../examples/navigation_manipulation_demo/contract.example.json). CI checkers read this file instead of duplicating stream invariants in test code.

The scenario represents a semi-humanoid mobile manipulator, `RoMi-H`, that:

1. Starts in a known map.
2. Navigates toward a manipulation zone.
3. Observes an object.
4. Reaches, grasps, and places the object.
5. Emits stream samples suitable for recording and replay.
6. Lets a mock policy emit proposed actions.
7. Produces a dataset inspection report.

The browser simulator and native smoke source should both read this scenario. Visual motion and JSONL artifacts are expected to stay aligned at the scenario level.

## Required Source Streams

The current smoke contract requires these source streams:

| Stream | Semantic type | Frame | Purpose |
| --- | --- | --- | --- |
| `robot.camera.rgb` | `rgb_image` | `camera_color_optical_frame` | Visual observation summary |
| `robot.camera.depth` | `depth_image` | `camera_depth_optical_frame` | Depth observation summary |
| `robot.camera.info` | `camera_info` | `camera_color_optical_frame` | Camera calibration summary |
| `robot.joints.state` | `joint_state` | `base_link` | Semi-humanoid joint state |
| `robot.base.odom` | `odometry` | `odom` | Mobile base pose and velocity |
| `robot.frames.tf` | `transform_tree` | `map->odom` | Frame graph summary |
| `task.goal` | `task_goal` | `map` | Task intent |

Derived streams:

| Stream | Producer | Authority |
| --- | --- | --- |
| `policy.proposed_action` | Mock policy | `proposed_only` |
| runtime diagnostics | Native source, recorder, replay, tools | Informational |

The demo may later add `policy.observation`, richer diagnostics, or simulator-specific streams, but those are not required by the current CI contract.

## Event Envelope

Current stream samples use a JSONL envelope with these fields:

```json
{
  "schema_version": "0.1.0",
  "schema_id": "romi.robotics.stream_metadata/0.1.0",
  "kind": "stream_sample",
  "stream_id": "robot.camera.rgb",
  "semantic_type": "rgb_image",
  "source_system": "romi_native_sim",
  "source_topic": null,
  "source_message_type": "romi.robotics.ImageSummary",
  "event_time_ns": 0,
  "clock_domain": "sim_time",
  "frame_id": "camera_color_optical_frame",
  "payload_summary": {},
  "metadata": {}
}
```

The envelope is intentionally transport-agnostic. A ROS2 bridge, simulator bridge, replay source, or future MCAP reader should map into the same logical stream identity.

The shared event envelope schema is
[`schemas/core/stream_sample.schema.json`](../schemas/core/stream_sample.schema.json).
It is validated against RoMi-native source events, browser simulator events,
replay events, policy events, and a representative ROS2 bridge `/tf_static`
sample in CI.

Start and stop lifecycle events use
[`schemas/core/lifecycle_event.schema.json`](../schemas/core/lifecycle_event.schema.json).
Committed report artifacts are indexed by
[`sample_output/report_manifest.json`](../examples/navigation_manipulation_demo/sample_output/report_manifest.json),
validated by
[`schemas/core/report_manifest.schema.json`](../schemas/core/report_manifest.schema.json).

## Payload Summary Contract

The demo uses compact summaries instead of full sensor payloads.

The current payload summary schemas are:

- [`image_summary.schema.json`](../schemas/robotics/image_summary.schema.json)
- [`camera_info_summary.schema.json`](../schemas/robotics/camera_info_summary.schema.json)
- [`joint_state_summary.schema.json`](../schemas/robotics/joint_state_summary.schema.json)
- [`odometry_summary.schema.json`](../schemas/robotics/odometry_summary.schema.json)
- [`transform_tree_summary.schema.json`](../schemas/robotics/transform_tree_summary.schema.json)
- [`task_goal_summary.schema.json`](../schemas/robotics/task_goal_summary.schema.json)

`tests/check_demo_contract.py` validates these schemas against source and replay
payload summaries from smoke runs.

Required image summary fields:

- `height`
- `width`
- `encoding`
- `step`
- `data_len`

Native/browser depth summary behavior:

- `data_len == height * width * 2`
- `synthetic_scene.target_depth_mm` is present
- `synthetic_scene.object_state` is present

Native/browser RGB summary behavior:

- `data_len == height * width * 3`
- `synthetic_scene.target_visible` is present
- `synthetic_scene.object_state` is present

Native/browser TF summary behavior:

- `transform_count == 6`
- each sampled transform includes `stamp_ns`
- `synthetic_base_translation` is present
- `synthetic_object_position` is present

These summaries are not final robotics schemas. They are the current inspectable shape for smoke testing and README review.

## RoMi-H Joint Contract

The demo robot morphology is `semi_humanoid_mobile_manipulator`.

The current `robot.joints.state` summary must expose exactly seven joints:

1. `waist_yaw`
2. `torso_lift`
3. `right_shoulder_pitch`
4. `right_elbow`
5. `right_wrist`
6. `gripper_left`
7. `gripper_right`

The following invariants are checked by CI:

- `joint_count == 7`
- `len(joint_names_sample) == 7`
- `position_count == 7`
- `len(position_sample) == 7`
- `velocity_count == 7`
- `effort_count == 7`
- source metadata includes `robot_morphology: semi_humanoid_mobile_manipulator`
- source metadata includes `authority: observation_only`

## Time And Frame Contract

The smoke demo uses `sim_time`.

Source events must preserve:

- `event_time_ns`
- `clock_domain`
- `frame_id`

Replay events must:

- preserve recorded event time
- set `source_system` to `replay`
- keep stream IDs stable
- allow the same downstream mock policy path to run over replayed samples

The current replay prototype is a JSONL reader. It is not a final replay runtime, but it establishes online/offline symmetry for the demo.

## Policy Contract

The mock policy reads replayed observations and emits `policy.proposed_action`.

Policy samples must:

- use stream ID `policy.proposed_action`
- validate the payload summary against
  [`schemas/ml/policy_io.schema.json`](../schemas/ml/policy_io.schema.json)
- include payload time, input stream list, and structured freshness entries
- include input freshness metadata
- include `inference_latency_ms`
- include proposed base, end-effector, and gripper actions
- set event metadata authority to `proposed_only`
- set payload metadata authority to `proposed_only`
- set every proposed action authority to `proposed_only`

Policy output is not actuator command authority. The demo intentionally stops at proposed actions.

## Dataset Report Contract

The dataset inspector writes:

- `dataset-report/report.md`
- `dataset-report/report.json`

The report must include:

- episode metadata
- stream list
- diagnostics summary
- policy summary
- synchronized observation window

The observation window must include all required source streams with status `ok`.
Each window row also carries semantic type, source message type,
`payload_schema_id`, event time, frame, sample index, and signed/absolute delta
from the target time. For current required streams, the row payload summaries are
validated against the robotics payload schemas listed above.

A committed example is available at [sample_output/dataset-report/report.md](../examples/navigation_manipulation_demo/sample_output/dataset-report/report.md).

## CI Invariants

The workflow in [.github/workflows/ci.yml](../.github/workflows/ci.yml) currently checks:

- Python syntax for scripts under `bridges/`, `examples/`, `tools/`, and `tests/`
- JavaScript syntax for the browser simulator
- JSON syntax for schemas and example JSON files
- RoMi-native smoke demo execution
- demo contract invariants in [tests/check_demo_contract.py](../tests/check_demo_contract.py)
- browser/native stream contract alignment in [tests/check_browser_native_contract.py](../tests/check_browser_native_contract.py)

Both contract checkers load [contract.example.json](../examples/navigation_manipulation_demo/contract.example.json).
The browser/native checker also requires Chrome or Chromium plus the dependencies
in [requirements-browser.txt](../requirements-browser.txt).

The contract checker verifies:

- required source streams exist
- RoMi-H joint counts remain consistent
- image and depth summary sizes are coherent
- TF summary includes stamped frames
- replay samples use `source_system: replay`
- policy output is `policy.proposed_action`
- policy authority remains `proposed_only`
- policy payload summaries match `ml/policy_io.schema.json`
- dataset report includes the required streams
- observation window streams are `ok`
- observation window counts, bounds, payload schema IDs, and payload summaries
  match the current robotics payload schemas

The browser/native checker verifies:

- browser simulator and native source expose the same required stream names
- semantic types, frame IDs, and source message types align
- scenario and morphology metadata align
- image/depth dimensions and `data_len` match
- RoMi-H joint counts and names match
- TF frame pairs and stamped transform summaries match
- browser policy proposals remain `proposed_only`

## Bridge Relationship

The demo contract is bridge-first.

ROS2 is not required for the default smoke path, but the same stable stream names are intended to be targets for a ROS2 bridge. ROS2 interop should map topics, tf2, services/actions, QoS metadata, and rosbag2/MCAP artifacts into this contract where practical.

This is not a claim that ROS2 is obsolete. It is a contract layer for replay, simulation, dataset, policy, and deployment workflows.

## Open Questions

The following are intentionally unresolved:

- final schema format and validation tooling
- final storage format and MCAP mapping
- final transport choices
- whether browser export and native source should share generated code
- how `policy.observation` should be represented
- how actuator authority transitions should be modeled beyond `proposed_only`
- how simulator adapters should expose world state and contacts
- how richer manipulation semantics should represent grasp state

These should be resolved incrementally as the MVP becomes more concrete.
