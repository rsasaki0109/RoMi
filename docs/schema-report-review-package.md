# Schema And Report Review Package

Draft PR title:

```text
Add schema-backed RoMi demo reports and contract validation
```

Draft commit message:

```text
Add schema-backed demo artifacts and contract checks
```

Draft PR body:

```markdown
## What Problem Does This Solve?

The navigation/manipulation demo exposed the right behavior, but too many
runtime artifacts were still informally checked. This makes the demo reviewable
through schema-backed stream envelopes, report artifacts, payload summaries,
browser/native parity checks, and refreshed README media.

## Change Type

- [ ] Runtime
- [x] Schema
- [x] Bridge
- [x] Documentation
- [x] Tooling
- [x] Test
- [ ] Other

## Interoperability

Keeps ROS2 as an interop bridge. Adds representative bridge diagnostics,
including `/tf_static`, without requiring ROS2 live execution in CI.

## Replayability

Strengthens live/replay symmetry with stream sample, lifecycle, dataset report,
policy, payload summary, and replay contract validation. Committed sample
artifacts are generated with normalized timestamps and paths.

## Observability

Adds schema-backed dataset, policy compare, evaluation timeline, safety,
manifest, payload summary, and ROS2 diagnostics artifacts.

## Transport Assumptions

Does not require ROS2, DDS, MCAP, a specific simulator, a specific ML framework,
or a specific transport. Schemas remain compact JSON contracts.

## Safety / Authority

Policy output remains `proposed_only`; reports and schemas keep policy
proposals separate from actuator commands and record that no command stream is
emitted.

## Testing

See `docs/schema-report-review-package.md` for the full local test list,
including the follow-up ROS2 Jazzy smoke verification.
```

## What Problem Does This Solve?

The navigation/manipulation demo had useful browser and native behavior, but many
runtime artifacts were still only informally checked. This change makes the demo
reviewable through committed schemas, generated sample artifacts, CI contract
checks, and refreshed README media.

## Change Type

- [ ] Runtime
- [x] Schema
- [x] Bridge
- [x] Documentation
- [x] Tooling
- [x] Test
- [ ] Other

## Interoperability

This keeps ROS2 as an interop bridge, not a required runtime for the browser or
native demo. It adds representative ROS2 bridge diagnostics schemas and samples,
including `/tf_static` coverage, without requiring a ROS2 live run in CI.

## Replayability

This strengthens live/replay symmetry by validating stream sample envelopes,
lifecycle events, payload summaries, dataset reports, policy reports, and replay
contract outputs. The generated sample artifacts are normalized so reviewers can
diff report content deterministically.

## Observability

This adds or tightens artifacts for:

- dataset inspection reports
- policy compare reports
- replay-wide evaluation timelines
- safety authority reports
- ROS2 bridge diagnostics
- report artifact manifests
- robotics payload summaries
- policy proposed-action payload summaries

The browser Studio surface now has refreshed README media covering the current
timeline, safety, dataset, policy, and graph inspection views.

## Transport Assumptions

This does not make ROS2, DDS, MCAP, a specific simulator, or a specific ML
framework mandatory. The schemas stay focused on compact JSON summaries and
transport-neutral event contracts.

## Safety / Authority

Policy output remains `proposed_only`. The reports and schemas explicitly keep
policy proposals separate from actuator command authority, and the safety report
records that no command stream is emitted.

## Main Files To Review

- `schemas/core/*`: stream sample, lifecycle, dataset report, safety authority,
  and report manifest schemas.
- `schemas/robotics/*`: compact payload summary schemas for image, camera info,
  joint state, odometry, TF, and task goal streams.
- `schemas/ml/*`: policy compare, evaluation timeline, and policy IO schemas.
- `schemas/observability/ros2_bridge_diagnostics.schema.json`: bridge
  diagnostics schema.
- `examples/navigation_manipulation_demo/generate_sample_artifacts.py`:
  committed sample artifact generator.
- `examples/navigation_manipulation_demo/sample_output/*`: generated review
  artifacts.
- `tests/check_sample_artifact_schemas.py`,
  `tests/check_demo_contract.py`,
  `tests/check_browser_native_contract.py`,
  `tests/check_ros2_bridge_diagnostics.py`: contract validation.
- `examples/navigation_manipulation_demo/romi_2d_sim/*`: Studio timeline,
  safety, policy, dataset, and capture-surface updates.
- `bridges/ros2/rclpy_bridge/romi_ros2_bridge.py`: bridge diagnostics and
  static TF handling.

## Suggested Review Order

1. Start with schemas and tests:
   `schemas/`, `tests/check_sample_artifact_schemas.py`,
   `tests/check_demo_contract.py`, and
   `tests/check_browser_native_contract.py`.
2. Review generated artifact shape:
   `examples/navigation_manipulation_demo/sample_output/*`.
3. Review browser Studio behavior:
   `examples/navigation_manipulation_demo/romi_2d_sim/*` and refreshed README
   media.
4. Review ROS2 bridge interop changes:
   `bridges/ros2/rclpy_bridge/romi_ros2_bridge.py`,
   `examples/navigation_manipulation_demo/stream-map.example.json`, and
   `examples/navigation_manipulation_demo/ros2-qos-diagnostics.example.json`.

## Optional Split Plan

If this is too large for one review, split it into:

1. `schemas-tests`: schema files, schema README, CI wiring, and validation
   tests.
2. `sample-artifacts`: sample artifact generator, committed report artifacts,
   dataset inspector enrichment, and demo contract docs.
3. `browser-studio-media`: Studio timeline/safety/dataset UI, browser contract
   updates, capture dependencies, and refreshed README media.
4. `ros2-bridge-diagnostics`: ROS2 bridge diagnostics schema/sample, `/tf_static`
   handling, stream map, bridge docs, and runbook updates.

Recommended single-PR path:

```text
Use one PR if reviewers are comfortable reviewing by section from this package.
Split only if binary media or ROS2 bridge changes slow down schema/test review.
```

## Testing

Ran locally without ROS2 live execution in the original schema/report review
pass:

```text
python -m py_compile tests\check_browser_native_contract.py tests\check_demo_contract.py tests\check_sample_artifact_schemas.py tests\check_ros2_bridge_diagnostics.py examples\navigation_manipulation_demo\generate_sample_artifacts.py examples\navigation_manipulation_demo\capture_readme_video.py tools\dataset_inspector\romi_inspect_dataset.py tools\mock_policy\romi_mock_policy.py tools\episode_recorder\romi_record_episode.py tools\replay_source\romi_replay_episode.py bridges\ros2\rclpy_bridge\romi_ros2_bridge.py examples\navigation_manipulation_demo\romi_native_sim_source.py examples\navigation_manipulation_demo\ros2_demo_sim_publisher.py
node --check examples\navigation_manipulation_demo\romi_2d_sim\sim.js
python tests\check_sample_artifact_schemas.py
python tests\check_ros2_bridge_diagnostics.py
python examples\navigation_manipulation_demo\generate_sample_artifacts.py --work-dir artifacts\final-ci-check --output-dir examples\navigation_manipulation_demo\sample_output
python tests\check_demo_contract.py artifacts\final-ci-check
python tests\check_browser_native_contract.py
JSON syntax check for schemas/examples/docs/tests/.github JSON and JSONL files
git diff --check
```

Temporary validation artifacts were removed after the checks.

## Notes

- Follow-up on 2026-05-25: a local ROS2 Jazzy smoke run passed with
  `ROMI_DEMO_SOURCE=ros2` and `tests/check_demo_contract.py`.
- `run_smoke_demo.sh` now uses an isolated demo `ROS_DOMAIN_ID` when one is not
  already set.
