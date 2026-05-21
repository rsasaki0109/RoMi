# Demo Backlog

This backlog turns the navigation + manipulation demo spec into implementation-sized work items. It is written so each item can become a GitHub issue.

## 1. Define Static Demo Stream Map

Labels: `documentation`, `schema`, `demo`

Status: scaffolded in `examples/navigation_manipulation_demo/stream-map.example.json`.

Problem:

The README demo needs stable stream names before bridge, replay, or policy code exists.

Scope:

- Define source topic to RoMi stream mapping.
- Include navigation, manipulation, frame, policy, and diagnostics streams.
- Document required metadata for each stream.

Acceptance criteria:

- Stream names match `docs/demo-spec.md`.
- Each stream has purpose, source direction, expected rate if known, and required metadata.
- The mapping does not assume one simulator or transport.

## 2. Draft Demo Schema Sketches

Labels: `schema`, `demo`

Status: partially implemented in `schemas/`.

Problem:

The demo needs structured data contracts for observations, actions, diagnostics, and episode metadata.

Scope:

- Sketch schemas for image metadata, depth or point cloud metadata, joint state, odometry, transform, task goal, policy observation, proposed action, and diagnostics event.
- Include schema version fields.
- Include time and frame references where relevant.

Acceptance criteria:

- Schemas are reviewable before implementation.
- Tensor-like payload metadata includes shape, dtype, layout, encoding, and frame or camera context where relevant.
- Proposed action schema is separate from actuator command authority.

Current note:

- `schemas/ml/policy_compare.schema.json` and
  `schemas/ml/evaluation_timeline.schema.json` now validate the committed
  Studio report samples.
- Event envelope, dataset report, and safety authority schemas remain open.

## 3. Create Example Episode Metadata

Labels: `replay`, `dataset`, `demo`

Status: scaffolded in `examples/navigation_manipulation_demo/episode-metadata.example.json`.

Problem:

The demo needs a concrete episode shape to guide recording, replay, and dataset inspection.

Scope:

- Add sample episode metadata.
- Include stream list, schema versions, clock mode, bridge metadata, frame graph metadata, and policy metadata.
- Keep MCAP compatibility as a design direction.

Acceptance criteria:

- Metadata can describe one navigation + manipulation run.
- Live and replay modes can refer to the same stream IDs.
- Runtime graph metadata is present.

## 4. Add Static Diagnostics Report

Labels: `observability`, `demo`

Status: scaffolded in `examples/navigation_manipulation_demo/diagnostics.example.json`.

Problem:

The README video needs something visible before a full runtime UI exists.

Scope:

- Create a static or generated diagnostics report format.
- Include graph, stream rates, latency, drops, frame status, replay clock state, QoS metadata, and policy freshness.
- Make the output suitable for video capture.

Acceptance criteria:

- A reviewer can inspect the graph and runtime state from the report.
- Diagnostics clearly separate bridge, replay, policy, and recorder status.
- No production readiness is implied.

## 5. Implement Minimal ROS2 Bridge Path

Labels: `bridge`, `ros2`, `demo`

Status: initial `rclpy` JSONL prototype scaffolded in `bridges/ros2/rclpy_bridge/`.

Problem:

The demo needs a bridge-first path from ROS2 or simulator topics into RoMi stream names.

Scope:

- Support selected common ROS2 messages from the demo spec.
- Preserve timestamps, frame IDs, and QoS metadata where available.
- Emit bridge diagnostics.

Acceptance criteria:

- Required source streams can be observed through RoMi stream names.
- QoS metadata is visible.
- The bridge remains an adapter, not the core runtime model.

## 6. Add Episode Recorder

Labels: `replay`, `mcap`, `demo`

Status: prototype implemented in `tools/episode_recorder/`.

Problem:

The demo must record a structured episode.

Scope:

- Record selected streams and metadata.
- Preserve event time, bridge receive time, and schema metadata.
- Keep the file format path compatible with MCAP-oriented design.

Acceptance criteria:

- One demo episode can be recorded.
- The episode includes stream, schema, time, frame, graph, bridge, and policy metadata.
- Missing streams or schema mismatches are reported.

## 7. Add Replay Source

Labels: `replay`, `runtime`, `demo`

Status: prototype implemented in `tools/replay_source/`.

Problem:

The demo must replay recorded data through the same logical graph as live input.

Scope:

- Read the recorded episode.
- Re-emit streams by recorded event time.
- Expose replay clock state.
- Surface gaps and frame issues.

Acceptance criteria:

- Mock policy can run against replayed observations.
- Live and replay paths share stream names and schema assumptions.
- Replay mode is visible in diagnostics.

## 8. Add Mock Policy Node

Labels: `runtime`, `policy`, `demo`

Status: prototype implemented in `tools/mock_policy/`.

Problem:

The demo needs to show policy-runtime awareness without requiring a real learned model.

Scope:

- Consume synchronized observations.
- Emit proposed base, end-effector, or gripper actions.
- Report input freshness and inference latency.
- Avoid direct actuator authority.

Acceptance criteria:

- The policy runs in live and replay modes.
- Proposed actions are visible in diagnostics.
- The authority boundary is explicit.

## 9. Add Dataset Inspection View

Labels: `dataset`, `tooling`, `demo`

Status: prototype implemented in `tools/dataset_inspector/`.

Problem:

The demo must show that recorded episodes can become inspectable dataset artifacts.

Scope:

- Provide a notebook, script, or report that opens one episode.
- List streams, schemas, time range, sample counts, and synchronized observation windows.
- Show frame and clock metadata.

Acceptance criteria:

- A recorded episode can be inspected without running the live robot or simulator.
- Dataset view preserves runtime semantics.
- The output is clear enough for the README video.

## 10. Capture README Demo Video

Labels: `documentation`, `demo`

Status: refreshed after compare, timeline, safety, dataset, and bridge diagnostics updates.

Problem:

The README needs a short video that communicates RoMi's direction.

Scope:

- Capture simulator or robot view.
- Capture graph, recording, replay, policy, diagnostics, and dataset view.
- Upload the video as a GitHub asset.
- Embed the asset URL in README.

Acceptance criteria:

- Video is 60 to 90 seconds.
- The README explains live, replay, dataset, policy, and diagnostics.
- The video does not imply production readiness.

Current implementation:

- README media assets were regenerated from `romi_2d_sim/?capture=readme`.
- Capture layout now shows Studio modes without tab overlap.
- `capture_readme_video.py` can use Chrome from common Windows install paths.
- The capture script can use system `ffmpeg` or Python `imageio-ffmpeg`.
- Browser/capture Python dependencies live in `requirements-browser.txt`.
- Missing browser dependencies now point to the exact install command.

## 11. Add Replay Evaluation Timeline

Labels: `demo`, `replay`, `policy`, `observability`

Status: implemented first pass in RoMi Studio.

Problem:

Policy comparison at one replay time is useful, but RoMi's core message is
stronger when policy behavior can be inspected across the whole replay.

Scope:

- Add a Studio `Timeline` view.
- Export `evaluation_timeline.md`.
- Export `evaluation_timeline.json`.
- Show changed policy actions, input freshness, latency, stage summary, and
  command stream boundary.

Acceptance criteria:

- The artifact is committed under `sample_output/`.
- The report keeps actuator authority as `none`.
- Browser/native contract checks cover the Studio API and UI surface.

## 12. Add Sample Artifact Generator

Labels: `tooling`, `demo`, `documentation`

Status: implemented.

Problem:

Committed demo artifacts need a reproducible local path instead of manual
browser export steps.

Scope:

- Add `examples/navigation_manipulation_demo/generate_sample_artifacts.py`.
- Regenerate dataset report, policy compare, and evaluation timeline samples.
- Keep the path ROS2-free.
- Document the command.

Acceptance criteria:

- A contributor can refresh committed sample artifacts with one command.
- Generated artifacts are deterministic enough for review.
- README and demo docs link the command.

## 13. Validate Report Schemas

Labels: `schema`, `policy`, `observability`, `ci`

Status: implemented for policy compare and evaluation timeline.

Problem:

Sample artifacts should be contract checks, not only static examples.

Scope:

- Add draft schemas for `romi.counterfactual_policy_compare`.
- Add draft schemas for `romi.replay_evaluation_timeline`.
- Validate committed sample artifacts in CI.

Acceptance criteria:

- `tests/check_sample_artifact_schemas.py` validates the committed JSON samples.
- CI runs the validation step.
- Schema files remain small and readable.

## 14. Add Runtime Graph Contract Metadata To Reports

Labels: `runtime`, `schema`, `observability`

Status: implemented first pass.

Problem:

The browser graph and generated artifacts should describe the same logical
runtime graph, not separate UI-only and report-only concepts.

Scope:

- Add graph metadata to policy compare and evaluation timeline reports.
- Include node IDs, inputs, outputs, status, and authority boundary.
- Keep the graph representation compatible with `runtime-graph.example.json`.
- Add contract checks for graph metadata.

Acceptance criteria:

- Reports expose the graph context that produced the artifact.
- Policy output and command authority remain separate.
- The graph can describe live, replay, and report/evaluation paths.

## 15. Add Dataset Report And Safety Authority Schemas

Labels: `schema`, `dataset`, `safety`, `observability`

Status: implemented first pass.

Problem:

Policy compare and evaluation timeline now have schemas. Dataset and safety
artifacts should get the same treatment so the committed examples become a more
complete contract set.

Scope:

- Add schema coverage for the dataset report output.
- Add schema coverage for `romi.safety_authority_report`.
- Extend committed sample validation where practical.
- Keep schemas small and focused on current artifacts.

Acceptance criteria:

- CI validates the new schema-backed sample artifacts.
- Safety authority remains `proposed_only` for policy output and `none` for
  actuator authority.
- Dataset report schema preserves stream, timing, frame, diagnostics, and policy
  sections.

## 16. Improve ROS2 Bridge Diagnostics

Labels: `bridge`, `ros2`, `observability`

Status: implemented first pass.

Problem:

RoMi's bridge-first positioning is stronger when ROS2 bridge diagnostics expose
QoS, TF, timestamps, stream status, and adapter boundaries clearly.

Scope:

- Improve QoS metadata capture where available.
- Add TF bridge notes and sample output.
- Keep bridge output in the RoMi stream envelope.
- Add CI-safe checks where practical.

Acceptance criteria:

- A ROS2 user can understand what metadata the bridge preserves.
- Diagnostics clearly show bridge status and limitations.
- The repository avoids "ROS replacement" messaging.

Implemented:

- `stream-map.example.json` now includes `/tf_static` alongside `/tf`, both
  mapping into `robot.frames.tf` while preserving `source_topic`.
- `romi_ros2_bridge.py` handles multiple ROS2 topics per RoMi stream and marks
  static transform metadata.
- `ros2-qos-diagnostics.example.json` is a schema-backed committed bridge
  diagnostics sample covering topic status, QoS, TF, timing, limitations, and
  authority boundaries.
- `tests/check_ros2_bridge_diagnostics.py` validates the bridge diagnostics
  sample in CI without requiring ROS2.

## 17. Consolidate Event Envelope Schema

Labels: `schema`, `runtime`, `replay`, `bridge`, `ci`

Status: implemented first pass.

Problem:

Browser, native source, replay, policy, and bridge samples should share one
reviewable event envelope instead of relying only on local test assumptions.

Scope:

- Add a shared `stream_sample` event envelope schema.
- Validate native source, replay, policy, browser, and bridge-style samples.
- Keep payload-specific schemas separate from the event envelope.

Acceptance criteria:

- The schema preserves stream ID, semantic type, source system, source topic,
  message type, event time, clock domain, frame ID, payload summary, and
  metadata.
- Replay samples preserve replay metadata.
- ROS2 bridge samples can include QoS and bridge receive timing.
- CI catches envelope regressions in the smoke and browser/native contract
  checks.

Implemented:

- Added `schemas/core/stream_sample.schema.json`.
- `tests/check_demo_contract.py` validates source, replay, and policy JSONL
  stream samples against the schema.
- `tests/check_browser_native_contract.py` validates browser and native samples
  against the schema.
- `tests/check_ros2_bridge_diagnostics.py` validates a representative ROS2
  `/tf_static` stream sample shape against the schema.

## 18. Tighten ROS2 Bridge Sample Run Instructions

Labels: `bridge`, `ros2`, `documentation`, `demo`

Status: implemented first pass.

Problem:

The bridge path had a prototype and diagnostics sample, but a contributor still
needed to infer the exact ROS2 smoke command, expected outputs, validation step,
and common failure modes.

Scope:

- Document one scripted ROS2 smoke run using `ROMI_DEMO_SOURCE=ros2`.
- List expected output files and validation commands.
- Make missing ROS2 Python dependencies fail before the bridge run starts.
- Ensure the scripted ROS2 publisher covers `/tf_static`.
- Add CI-safe checks for the runbook shape where possible.

Acceptance criteria:

- A ROS2 user can run the scripted bridge demo from a sourced ROS2 environment.
- The runbook names expected JSONL, episode, replay, policy, and report outputs.
- Troubleshooting covers missing ROS2 setup, missing Python packages, missing
  `/tf_static`, and topic name mismatches.
- CI can verify docs and static source expectations without requiring ROS2.

Implemented:

- `bridges/ros2/rclpy_bridge/README.md` now includes the scripted smoke command,
  expected outputs, validation command, direct bridge command, and troubleshooting.
- `run_smoke_demo.sh` checks ROS2 Python message packages and `numpy` before
  starting the bridge path.
- `ros2_demo_sim_publisher.py` publishes `/tf_static` with transient-local QoS.
- `tests/check_ros2_bridge_diagnostics.py` checks the publisher and runbook
  expectations without requiring ROS2.

## 19. Broader Event-Kind Schemas

Labels: `schema`, `runtime`, `reports`, `ci`

Status: implemented first pass.

Problem:

`stream_sample` had a shared envelope schema, but lifecycle and report artifact
metadata still depended on local conventions.

Scope:

- Add a shared lifecycle event schema for start/stop events.
- Validate replay and policy lifecycle events from generated JSONL.
- Validate representative ROS2 bridge lifecycle events without requiring ROS2.
- Add a committed report artifact manifest and schema.

Acceptance criteria:

- Replay and policy JSONL start/stop events are schema-checked.
- Bridge start/stop event shape is schema-checkable.
- Committed report artifacts are discoverable through a schema-backed manifest.
- Safety authority boundaries remain visible in report metadata.

Implemented:

- Added `schemas/core/lifecycle_event.schema.json`.
- Added `schemas/core/report_manifest.schema.json`.
- Added `sample_output/report_manifest.json`.
- `tests/check_demo_contract.py` validates replay and policy lifecycle events.
- `tests/check_ros2_bridge_diagnostics.py` validates representative bridge
  lifecycle events.
- `tests/check_sample_artifact_schemas.py` validates the report manifest and
  authority boundaries.

## 20. Tighten Stream Payload Summary Schemas

Labels: `schema`, `robotics`, `dataset`, `ci`

Status: implemented first pass.

Problem:

The stream sample envelope was schema-backed, but the contents of
`payload_summary` were still mostly validated with ad hoc assertions.

Scope:

- Add payload summary schemas for current required demo streams.
- Validate source and replay payload summaries in the smoke contract.
- Keep the schemas focused on compact summaries, not full image or tensor
  payloads.

Acceptance criteria:

- RGB and depth summaries require shape, encoding, byte count, and synthetic
  scene metadata.
- Camera info summaries require calibration vector lengths.
- Joint state summaries require count fields and sampled names/positions.
- Odometry summaries require pose, twist, child frame, and stage fields.
- TF summaries require stamped parent/child frame samples.
- Task goal summaries require scenario, target object, pose, and orientation.

Implemented:

- Added robotics payload schemas for image, camera info, joint state, odometry,
  transform tree, and task goal summaries.
- `tests/check_demo_contract.py` validates payload summaries for source and
  replay JSONL events.

## 21. Tighten Dataset Observation Window Schemas

Labels: `schema`, `dataset`, `ci`

Status: implemented first pass.

Problem:

The dataset report had a synchronized observation window, but each row only
carried a loose payload summary object.

Scope:

- Add explicit window bounds and stream availability counts.
- Carry semantic type, source message type, payload schema ID, sample index, and
  signed/absolute time deltas per observation window row.
- Validate row payload summaries against the current robotics payload schemas.

Acceptance criteria:

- Dataset report JSON exposes target, start, and end times for the window.
- Window stream counts match the row statuses.
- Required demo stream payload schema IDs match the current robotics schemas.
- `tests/check_sample_artifact_schemas.py` and `tests/check_demo_contract.py`
  validate observation window payload summaries.

Implemented:

- `tools/dataset_inspector/romi_inspect_dataset.py` emits the enriched
  observation window rows.
- `schemas/core/dataset_report.schema.json` requires the new row metadata and
  window counts.
- Committed sample dataset report JSON was regenerated with the enriched window.

## 22. Tighten Policy Payload Summary Schema

Labels: `schema`, `policy`, `ci`

Status: implemented first pass.

Problem:

`policy.proposed_action` events had authority checks, but the payload schema
still allowed loose freshness entries and proposed action shapes.

Scope:

- Require payload time, input stream list, structured freshness entries,
  proposed actions, latency, and metadata authority.
- Constrain proposed action targets, known demo action types, and
  `proposed_only` authority.
- Validate native policy JSONL payloads and browser policy payloads with the
  same schema.

Acceptance criteria:

- `schemas/ml/policy_io.schema.json` rejects payloads missing freshness status,
  required flags, action authority, or metadata authority.
- `tests/check_demo_contract.py` validates generated `policy-events.jsonl`.
- `tests/check_browser_native_contract.py` validates the browser
  `policy.proposed_action` payload.

Implemented:

- Tightened `schemas/ml/policy_io.schema.json`.
- Browser simulator policy payloads now include schema-aligned time,
  input-stream, and freshness fields.
- Policy payload schema validation is wired into native and browser contract
  checks.

## 23. Non-ROS2 Final CI And Diff Sweep

Labels: `ci`, `demo`, `review`

Status: implemented.

Problem:

The schema, report, demo, and README media changes need a final non-ROS2 check
pass before review.

Scope:

- Run syntax checks for changed Python and browser simulator JavaScript.
- Validate committed sample artifacts and representative ROS2 diagnostics
  artifacts without launching ROS2.
- Generate a temporary native smoke artifact set and validate the demo contract.
- Validate browser/native parity through the browser contract checker.
- Check JSON syntax, diff whitespace, and temporary artifact cleanup.

Implemented:

- `python -m py_compile` passed for changed scripts and tests.
- `node --check` passed for the browser simulator.
- `tests/check_sample_artifact_schemas.py` passed.
- `tests/check_ros2_bridge_diagnostics.py` passed.
- `tests/check_demo_contract.py` passed against a generated temporary run.
- `tests/check_browser_native_contract.py` passed.
- JSON syntax and `git diff --check` passed.
- Temporary validation artifacts were removed.

## 24. Package Schema And Report Changes For Review

Labels: `review`, `docs`, `schema`

Status: implemented.

Problem:

The change set spans schemas, reports, browser Studio UI, ROS2 bridge examples,
media, and CI checks, so reviewers need a concise map of what changed and how it
was tested.

Scope:

- Prepare a PR-title draft.
- Summarize the problem, interoperability impact, replayability impact,
  observability changes, transport assumptions, and safety authority boundaries.
- List the highest-value files to review.
- Record the known local test commands and the fact that ROS2 live smoke was not
  run.

Implemented:

- Added `docs/schema-report-review-package.md` with a PR-ready review package.

## 25. Prepare Commit And PR Metadata

Labels: `review`, `git`, `docs`

Status: implemented.

Problem:

The review package needed concrete metadata that can be copied into a commit or
pull request without reconstructing the scope from the diff.

Scope:

- Draft a concise commit message.
- Draft a PR body aligned with `.github/PULL_REQUEST_TEMPLATE.md`.
- Provide a suggested review order.
- Provide an optional split plan if the one-PR path is too large.

Implemented:

- Added commit message, PR body, review order, and split plan to
  `docs/schema-report-review-package.md`.
