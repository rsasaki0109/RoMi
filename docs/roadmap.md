# RoMi Roadmap

This roadmap is focused on turning the current replay-first demo into a credible
pre-MVP repository foundation. It is not a full product roadmap.

## Current Status

RoMi is in early concept / pre-MVP status, with a small runnable prototype path.

The repository now contains:

- A ROS2-free navigation + manipulation source.
- A browser-based RoMi 2D simulator with RoMi Studio.
- Episode recording and replay prototypes.
- A mock non-authoritative policy prototype.
- Dataset inspection output.
- Counterfactual policy comparison artifacts.
- Replay evaluation timeline artifacts.
- Sample artifact regeneration.
- Schema-backed CI validation for stream samples, lifecycle events, robotics
  payload summaries, policy payloads, report manifests, dataset reports, safety
  reports, policy compare artifacts, and evaluation timeline artifacts.
- A ROS2 bridge prototype path.

This is enough to communicate the intended contract. It is not production
runtime infrastructure, a final scheduler, or a ROS2 replacement.

## Milestone 0: Repository Foundation

Status: mostly done, ongoing polish.

Goal:

- Make the project understandable to senior robotics engineers.
- Establish that RoMi is Physical AI-friendly, replay-first, simulation-native,
  ROS2-interoperable, and transport-agnostic.
- Avoid positioning RoMi as a full ROS replacement.

Done:

- README foundation with simulator media and sample artifacts.
- Vision, requirements, architecture, ROS2 interop, MVP, and demo docs.
- Issue and PR templates.
- Current tactical plan in `PLAN.md`.

Remaining:

- License selection.
- Contributing guide.
- Architecture decision records.

## Milestone 1: Demo Contract

Status: implemented as a prototype contract.

Goal:

- Define the navigation + manipulation demo contract.
- Make stream names, graph shape, episode metadata, replay expectations, policy
  authority, and diagnostics explicit.

Done:

- `docs/demo-spec.md`
- `examples/navigation_manipulation_demo/README.md`
- `docs/demo-backlog.md`
- `examples/navigation_manipulation_demo/contract.example.json`
- Draft schemas under `schemas/`
- Example stream map, runtime graph, diagnostics, and episode metadata

Next:

- Keep docs synchronized with implemented artifacts.
- Consolidate event envelope and report schemas as the demo matures.

## Milestone 2: Runnable Demo Artifacts

Status: implemented for the current prototype.

Goal:

- Provide concrete artifacts that make the replay-first workflow inspectable
  without requiring ROS2.

Done:

- Browser simulator and Studio inspector.
- README media assets.
- Committed dataset report sample.
- Committed policy compare Markdown and JSON artifacts.
- Committed replay evaluation timeline Markdown and JSON artifacts.
- `generate_sample_artifacts.py` for reproducible sample output.

Next:

- Keep media current when Studio UI changes.
- Keep generated report metadata aligned with the browser Studio graph.

## Milestone 3: Minimal Live Bridge

Status: prototype path exists.

Goal:

- Connect selected ROS2 or simulator streams to RoMi demo stream names.

Current status:

- Bridge boundary scaffolded in `bridges/ros2/`.
- Demo-specific bridge plan in
  `examples/navigation_manipulation_demo/ros2-bridge-plan.md`.
- Initial `rclpy` JSONL bridge prototype in `bridges/ros2/rclpy_bridge/`.
- Schema-backed ROS2 bridge diagnostics sample and CI-safe checks exist.
- `/tf` and `/tf_static` are represented in the demo stream map.
- Scripted ROS2 smoke runbook lists setup, command, expected outputs,
  validation, and troubleshooting.
- Demo ROS2 publisher emits `/tf_static` with transient-local QoS.

Minimum streams:

- RGB image.
- Depth or point cloud.
- Camera info.
- Joint state.
- Odometry.
- TF and static TF.
- Task goal or marker.

Exit criteria:

- Stream metadata and diagnostics are visible.
- QoS metadata is captured where available.
- The bridge remains an adapter, not the core runtime model.

## Milestone 4: Episode Record And Replay

Status: prototype implemented.

Goal:

- Record one navigation + manipulation episode and replay it through the same
  logical graph.

Done:

- Prototype episode recorder in `tools/episode_recorder/`.
- Prototype replay source in `tools/replay_source/`.
- Smoke flow through source, recorder, replay, mock policy, and dataset
  inspector.

Next:

- Document MCAP mapping direction.
- Keep replay artifacts aligned with the shared stream sample envelope.

## Milestone 5: Policy Runtime And Evaluation

Status: first pass implemented.

Goal:

- Show policy-runtime awareness without requiring a trained model.

Done:

- Mock policy node.
- Proposed action stream with `proposed_only` authority.
- Observation-window freshness in Studio.
- Counterfactual policy comparison at one replay time.
- Replay evaluation timeline across sampled replay times.
- Safety boundary views and report checks.

Next:

- Keep actuator authority promotion explicitly out of scope until supervised by
  an external boundary.
- Add richer policy evaluation only after the current report contract remains
  stable across more examples.

## Milestone 6: Contracts And Schemas

Status: implemented for the current prototype surface.

Done:

- Draft stream, diagnostic, episode, graph, and policy IO schemas.
- Policy compare report schema.
- Replay evaluation timeline schema.
- Dataset report schema.
- Safety authority report schema.
- Stream sample event envelope schema.
- Lifecycle event schema.
- Report artifact manifest schema.
- Robotics payload summary schemas for image, camera info, joint state,
  odometry, transform tree, and task goal samples.
- CI validation for committed policy compare and timeline samples.
- CI validation for committed dataset and safety samples.
- CI validation for source, replay, policy, browser, and representative ROS2
  bridge stream sample envelopes.
- CI validation for replay and policy lifecycle events.
- CI validation for committed report artifact manifest metadata.
- CI validation for source and replay payload summaries.
- CI validation for dataset report observation-window bounds, stream counts,
  payload schema IDs, and window payload summaries.
- CI validation for native and browser policy proposed-action payload summaries.
- Non-ROS2 final check pass covering Python syntax, browser simulator syntax,
  committed schemas and artifacts, smoke contract output, browser/native
  parity, JSON syntax, and diff whitespace.
- Review package with PR title, scope, interoperability notes, safety notes,
  main review files, and known-test list.
- Commit/PR metadata with draft commit message, PR body, suggested review order,
  and optional split plan.

Next:

- Add MCAP mapping documentation when the stream envelope has another real
  example behind it.
- Re-run the live ROS2 smoke path when bridge mappings or ROS2 message handling
  change.
- Keep schemas small until the prototype proves the contract shape.

## Milestone 7: README Demo Video

Status: refreshed for the current Studio surface.

Goal:

- Keep the README visual proof aligned with the current Studio surface.

Current status:

- README embeds regenerated simulator media.
- Capture guide and capture script exist.
- Media shows the current compare, timeline, safety, and dataset Studio surface.
- Capture script has Chrome path detection and an `imageio-ffmpeg` encoding fallback.
- Browser/capture dependencies are documented in `requirements-browser.txt`.
- Browser/native contract checks provide clearer local setup errors.

Exit criteria:

- A new visitor can understand RoMi's direction from the README quickly.
- The video does not imply production readiness.
- The demo remains bridge-first and ROS2-interoperable.

## Near-Term Non-Goals

- Full runtime replacement for ROS2.
- Production deployment story.
- Final transport decision.
- Final language decision.
- Full simulator support matrix.
- Real learned policy benchmark.
- Real actuator control.
