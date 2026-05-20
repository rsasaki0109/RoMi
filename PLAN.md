# RoMi Project Plan

RoMi is an early pre-MVP robotics middleware project. The current goal is not to
build a full robotics framework. The current goal is to make one narrow idea
clear, credible, and useful:

> Replay a robot episode, swap a policy, and inspect what changed before
> touching actuators.

This plan describes the next practical steps for turning the current demo into a
stronger repository foundation for replay-first, inspectable, simulation-native,
policy-runtime aware robot middleware.

## Current Position

RoMi currently has a small but coherent prototype path:

- A ROS2-free navigation + manipulation source.
- A browser-based RoMi 2D semi-humanoid simulator.
- A RoMi Studio mini inspector in the browser.
- Stream samples for RGB, depth, camera info, joint state, odometry, TF, task
  goal, diagnostics, and non-authoritative policy proposals.
- An episode recorder prototype.
- A replay source prototype.
- A mock policy prototype.
- A dataset inspector prototype.
- A ROS2 bridge prototype path.
- README media showing the simulator and Studio inspector.
- Sample artifacts for dataset inspection and policy comparison.
- CI checks for the smoke demo and browser/native contract.

This is enough to communicate the intended contract. It is not enough to claim
production readiness, runtime completeness, or a final architecture.

## Repository Message

The repository should communicate this in the first few seconds:

RoMi is a Physical AI-friendly robotics middleware direction for replay-first,
inspectable, simulation-native robot runtimes. It lets a user record or generate
a robot episode, replay it, compare policy behavior, inspect runtime state, and
keep actuator authority boundaries explicit.

The strongest current message is:

```text
recorded or simulated episode
  -> replay
  -> policy proposal
  -> counterfactual policy comparison
  -> dataset and evaluation artifacts
  -> no actuator authority unless an external supervisor promotes it
```

RoMi is not anti-ROS. RoMi should interoperate with ROS2, DDS, MCAP, simulators,
and vendor SDKs. Bridge-first remains the right positioning.

## Design Principles

### Replay-First

Live robot data, simulator data, recorded episodes, and datasets should map into
the same logical stream contract where practical.

Replay should not be an afterthought. Replay should be a normal way to inspect,
evaluate, debug, and compare policy behavior.

### Inspectable Runtime

The runtime graph, stream freshness, event envelopes, frame metadata, policy
inputs, policy outputs, latency, and authority boundaries should be visible.

If a robot behavior changes, a user should be able to ask:

- Which stream changed?
- Which policy input was stale or missing?
- Which action proposal changed?
- Was actuator authority ever granted?
- What was the clock and frame context?

### Simulation-Native

RoMi should work well with simulation without becoming one simulator's extension.
The browser demo is intentionally a contract demo, not a final simulator.

Future simulator bridges should preserve:

- Event time.
- Scenario identity.
- Stream IDs.
- Frame IDs.
- Policy observation windows.
- Episode metadata.

### Policy-Runtime Aware

RoMi should understand that modern robot runtimes include ML policies, VLA
models, GPU inference, tensor-native data, dataset loading, evaluation runs, and
policy deployment constraints.

Policy output must remain separate from actuator authority.

### Transport-Agnostic

RoMi should not be Python-only, C++-only, Rust-only, DDS-only, ROS2-only, Zenoh-only,
or MCAP-only.

The project should define contracts first, then prove adapters.

### Bridge-First ROS2 Relationship

ROS2 remains valuable for drivers, tf2, Nav2, Autoware, lifecycle patterns,
visualization, and existing robot deployments.

RoMi should interoperate first. Replacement is not the first milestone.

## What Exists Today

### Demo

The navigation + manipulation demo is now the primary repository proof point.

It demonstrates:

- ROS2-free simulation source.
- Shared scenario between browser and native smoke source.
- RoMi-shaped event envelopes.
- Runtime graph visibility.
- Replay seek controls.
- Event envelope inspection.
- Policy observation-window freshness.
- Counterfactual policy comparison.
- Safety and actuator authority boundary display.
- Dataset report generation.
- Exportable `policy_compare.md` and `policy_compare.json`.

### Sample Artifacts

Committed examples:

- `examples/navigation_manipulation_demo/sample_output/dataset-report/report.md`
- `examples/navigation_manipulation_demo/sample_output/policy_compare.md`
- `examples/navigation_manipulation_demo/sample_output/policy_compare.json`

These artifacts help a visitor understand the output without running anything.

### CI

Current CI checks:

- Python syntax.
- JavaScript syntax.
- JSON syntax.
- RoMi-native smoke demo.
- Demo contract.
- Browser/native contract.
- Sample policy compare artifact contract.

## Near-Term Goal

The next near-term goal is to make RoMi look like a serious replay-first robot
runtime contract, not just a visual demo.

The repository should make a senior robotics or ML engineer think:

- This is not trying to clone ROS.
- This is about runtime contracts around replay, policies, datasets, simulation,
  and safety boundaries.
- The demo is small, but the architecture direction is coherent.
- The sample artifacts are inspectable and reproducible.

## Milestone A: README And Demo Credibility

Status: mostly done, keep polishing.

Goal:

Make the repository immediately understandable from the README.

Already done:

- README starts with the core replay/policy comparison value.
- README embeds actual simulator media.
- README links sample dataset and policy compare artifacts.
- Demo can run without ROS2.
- ROS2 interop remains present but optional.

Next actions:

- Keep the README short above the fold.
- Keep the demo video current when Studio changes.
- Add one screenshot or short artifact preview if GitHub video rendering is weak.
- Add a concise "What is implemented vs planned" table.
- Add a "Why not ROS replacement?" note near the ROS2 bridge section if confusion
  appears in issues.

Exit criteria:

- A new visitor can understand the demo in under 30 seconds.
- A technical visitor can find sample artifacts in under one minute.
- The README does not overclaim production readiness.

## Milestone B: Replay Evaluation Timeline

Status: next recommended feature.

Goal:

Move from "compare two policies at one replay time" to "evaluate policy behavior
across the whole replay."

Planned user-facing feature:

- Add an `Eval` or `Timeline` view to RoMi Studio.
- Generate `evaluation_timeline.md`.
- Generate `evaluation_timeline.json`.
- Show where policy outputs changed.
- Show stale or missing inputs over replay time.
- Show latency bands.
- Show safety boundary state.
- Summarize by runtime stage.

Planned report shape:

```json
{
  "schema_version": "0.1.0",
  "report_kind": "romi.replay_evaluation_timeline",
  "episode_id": "romi_2d_nav_manip_demo",
  "clock_domain": "sim_time",
  "samples": [
    {
      "time_sec": 11.8,
      "stage": "grasp",
      "fresh_inputs": 5,
      "required_inputs": 6,
      "policy_latency_ms": 0.9,
      "changed_actions": 2,
      "command_stream_emitted": false
    }
  ],
  "stage_summary": [
    {
      "stage": "grasp",
      "samples": 10,
      "changed_action_samples": 7,
      "min_fresh_inputs": 5,
      "max_latency_ms": 1.9
    }
  ]
}
```

Implementation plan:

1. Add `evaluationTimelineReport()` in the browser simulator.
2. Sample replay time points from existing event state.
3. Reuse `policyCompareReport()` logic for each sampled time.
4. Aggregate by stage.
5. Add markdown and JSON export helpers.
6. Add Studio tab or compact panel.
7. Add browser/native contract checks.
8. Add committed sample artifacts.
9. Update README media if the UI changes visibly.

Non-goals for this milestone:

- No real learned policy benchmark.
- No GPU inference integration.
- No final metrics schema.
- No actuator commands.

Exit criteria:

- A visitor can see that RoMi evaluates replayed policy behavior over time.
- The output is an inspectable artifact, not only a UI.
- The report keeps actuator authority boundaries explicit.

## Milestone C: Artifact Reproducibility

Status: partially done.

Goal:

Make sample artifacts reproducible from local commands.

Problem:

The smoke demo currently generates dataset reports from CLI tools. The browser
Studio generates policy compare artifacts. That is acceptable for a prototype,
but users should eventually have a single reproducible path for sample artifacts.

Planned actions:

- Add a small script such as `examples/navigation_manipulation_demo/generate_sample_artifacts.py`.
- Generate or refresh:
  - README media.
  - Dataset report sample.
  - Policy compare sample.
  - Future evaluation timeline sample.
- Keep generated sample files deterministic enough for review.
- Document which artifacts are browser-derived and which are CLI-derived.

Exit criteria:

- A contributor can regenerate committed sample artifacts with one documented
  command.
- The output does not require ROS2.
- CI can validate the artifacts without needing to commit large transient files.

## Milestone D: Contracts And Schemas

Status: scaffolded, needs consolidation.

Goal:

Turn the demo's implicit stream and report shapes into reviewable schemas.

Priority schema targets:

- Event envelope.
- Stream sample.
- Diagnostic event.
- Dataset report.
- Policy proposed action.
- Policy compare report.
- Replay evaluation timeline.
- Safety authority report.

Planned actions:

- Add schema files under `schemas/`.
- Ensure sample artifacts declare schema version and report kind.
- Add JSON schema validation in CI for committed samples.
- Keep schema content small and readable.

Exit criteria:

- A user can inspect a schema before reading code.
- Sample artifacts validate against the schema.
- Versioning is explicit.

## Milestone E: Runtime Graph Contract

Status: browser graph exists, runtime model still prototype.

Goal:

Define the runtime graph contract independently from the browser UI.

Planned graph concepts:

- Source nodes.
- Recorder nodes.
- Replay source nodes.
- Policy nodes.
- Dataset/evaluation nodes.
- Bridge nodes.
- Safety boundary nodes.
- Observability nodes.

Planned actions:

- Add graph metadata to sample artifacts.
- Add a graph report that lists node inputs, outputs, status, and authority.
- Expose graph state in a CLI or JSON report.
- Keep browser Studio as a visualization of the same graph contract.

Exit criteria:

- The browser graph and CLI artifacts describe the same logical graph.
- Node authority and output streams are explicit.
- The graph can represent live, sim, and replay modes.

## Milestone F: ROS2 Bridge Credibility

Status: prototype bridge exists.

Goal:

Show that RoMi is bridge-first and ROS2-interoperable without becoming ROS2-only.

Near-term actions:

- Keep ROS2 bridge docs current.
- Add a short ROS2 bridge smoke path where practical.
- Capture QoS metadata where available.
- Preserve timestamps and frame IDs.
- Keep bridge output in the same RoMi stream envelope.

Demo migration examples to document:

- Turtlesim-like toy simulator is not enough for manipulation.
- Nav2-style navigation graphs can bridge selected streams first.
- Manipulation SDKs can bridge observations and proposed policy outputs.
- Autoware-style stacks need selected stream subsets and replay evaluation, not
  full graph replacement at first.

Exit criteria:

- A ROS2 user can understand how RoMi fits around an existing graph.
- The repository avoids "ROS is obsolete" messaging.
- Bridge examples remain adapters to the RoMi contract.

## Milestone G: MCAP And Dataset Direction

Status: design direction only.

Goal:

Align episode storage with common robotics tooling without prematurely choosing
a final storage layer.

Planned actions:

- Keep JSONL prototype simple for now.
- Document how event envelopes map to MCAP concepts.
- Add MCAP bridge or exporter only when the contract is stable enough.
- Make dataset loading notebook-friendly later, but do not make the repository
  Python-only.

Exit criteria:

- The project clearly says MCAP-compatible direction, not MCAP-only.
- Episode metadata preserves enough timing, frame, and schema information for
  replay and dataset extraction.

## Milestone H: Developer Experience

Status: early.

Goal:

Make the repository easy for humans and AI agents to inspect and modify.

Planned actions:

- Add a concise contributor guide.
- Keep examples small and runnable.
- Keep docs linked from README.
- Avoid hidden setup requirements.
- Prefer deterministic smoke tests.
- Add issue templates for focused architecture discussions.
- Add "good first issue" candidates after the next artifact milestone.

Exit criteria:

- A contributor can run the demo without ROS2.
- A contributor can understand the boundaries between docs, schemas, runtime
  prototypes, bridges, tools, examples, and tests.
- CI failures are actionable.

## 30 Day Plan

The next 30 days should focus on clarity and artifact depth, not broad runtime
scope.

Priority 1:

- Add replay evaluation timeline in Studio.
- Export `evaluation_timeline.md` and `evaluation_timeline.json`.
- Add committed sample artifacts.
- Add CI contract checks for the new artifacts.

Priority 2:

- Add `generate_sample_artifacts.py` or equivalent.
- Document artifact regeneration.
- Keep README media current.

Priority 3:

- Draft schemas for policy compare and evaluation timeline.
- Validate committed sample artifacts against those schemas.

Priority 4:

- Refresh `docs/roadmap.md` so it no longer describes the repository as docs-only.
- Keep `docs/demo-backlog.md` synchronized with implemented items.

## 60 Day Plan

The next 60 days should make RoMi feel like a coherent pre-MVP, not only a demo.

Priority 1:

- Consolidate event envelope and report schemas.
- Add graph contract metadata to reports.
- Add a minimal CLI command for artifact inspection if a language stack is
  already clearly justified.

Priority 2:

- Improve ROS2 bridge diagnostics.
- Document QoS and TF bridge behavior with one reproducible example.

Priority 3:

- Add one notebook-friendly dataset loading example, but avoid making the core
  project Python-only.

Priority 4:

- Add a clear safety boundary document around `proposed_only` policy output and
  actuator authority promotion.

## 90 Day Plan

The next 90 days should prove RoMi's core thesis with a stronger external-facing
example.

Potential directions:

- A simulator bridge that is more realistic than the browser visual demo.
- A ROS2/Nav2-adjacent replay path with selected streams.
- A manipulation SDK bridge that records observations and compares policies.
- A small MCAP export path.
- A replay evaluation report suitable for CI regression checks.

The 90 day goal is not breadth. The goal is one credible vertical slice that
connects:

```text
source or bridge
  -> episode
  -> replay
  -> policy
  -> evaluation artifact
  -> safety boundary
  -> inspectable graph
```

## Issue Candidates

These can become GitHub issues after the plan is accepted.

### Add Replay Evaluation Timeline

Labels: `demo`, `replay`, `policy`, `observability`

Deliverables:

- Studio timeline view.
- `evaluation_timeline.md`.
- `evaluation_timeline.json`.
- Sample artifacts.
- Contract tests.

### Add Sample Artifact Generator

Labels: `tooling`, `demo`, `documentation`

Deliverables:

- One command to regenerate README-adjacent artifacts.
- Deterministic output where practical.
- Documentation.

### Add Policy Compare Schema

Labels: `schema`, `policy`, `replay`

Deliverables:

- JSON schema for `romi.counterfactual_policy_compare`.
- Validation test for committed sample artifact.

### Add Evaluation Timeline Schema

Labels: `schema`, `policy`, `observability`

Deliverables:

- JSON schema for `romi.replay_evaluation_timeline`.
- Validation test for committed sample artifact.

### Refresh Roadmap And Backlog

Labels: `documentation`, `planning`

Deliverables:

- Update `docs/roadmap.md` to reflect implemented prototype pieces.
- Update `docs/demo-backlog.md` statuses.
- Link `PLAN.md` as the current tactical plan.

### Improve ROS2 Bridge Diagnostics

Labels: `bridge`, `ros2`, `observability`

Deliverables:

- Clear QoS metadata capture.
- TF bridge notes.
- Bridge sample output.
- CI-safe checks where possible.

## Non-Goals

RoMi should not pursue these yet:

- Full ROS2 replacement.
- Full runtime scheduler.
- Production safety stack.
- Real actuator control.
- Full physics simulator.
- Real VLA policy integration.
- GPU inference framework selection.
- Final transport selection.
- Final language selection.
- Large SDK surface.

## Risks

### Looking Like A Toy

The browser demo is useful, but it can look toy-like if not connected to real
runtime artifacts. Sample reports, schemas, and replay evaluation artifacts are
the antidote.

### Looking Like ROS3

RoMi must keep bridge-first messaging. It should avoid claiming to replace ROS2.
Interop examples should stay visible.

### Overfitting To One Stack

The project must avoid becoming Python-only, browser-only, ROS2-only, or MCAP-only
before the contracts are clear.

### Too Much Documentation, Not Enough Proof

Docs should point to runnable examples and committed artifacts. Every major claim
should eventually have a small demo or sample file.

### Safety Ambiguity

Policy proposals must remain clearly separate from actuator commands. The current
`proposed_only` boundary should remain visible in UI, reports, and docs.

## Definition Of Done For New Features

A new RoMi demo feature should generally include:

- A small user-facing behavior.
- A structured JSON artifact when applicable.
- A readable Markdown artifact when applicable.
- A README or demo doc update.
- A contract test.
- Clear authority boundaries if policy output is involved.
- No claim of production readiness.

## Current Best Next Step

The highest-value next implementation is:

```text
Replay Evaluation Timeline
```

It extends the current policy compare work from one time point to a replay-wide
evaluation artifact. It strengthens the repository's central message without
requiring a heavy runtime implementation.

The second-best next step is:

```text
Sample Artifact Generator
```

It makes the repository easier to maintain and keeps the README, Studio demo, and
committed sample artifacts synchronized.

The recommended order is:

1. Replay Evaluation Timeline.
2. Sample Artifact Generator.
3. Policy compare and timeline schemas.
4. Roadmap/backlog refresh.
5. ROS2 bridge diagnostics polish.

