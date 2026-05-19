# README Demo Video Plan

The first public RoMi demo video should make the project understandable in under two minutes. It should show why RoMi exists without implying that the runtime is production-ready.

## Goal

Create a README-ready demo video showing a navigation + manipulation episode that is:

- Replay-first
- Inspectable
- Simulation-friendly
- ROS2-interoperable
- Dataset-aware
- Policy-runtime aware

The demo can use a simulator first. It should not depend on a specific simulator, robot, ML framework, or transport as a permanent architectural choice.

## Demo Narrative

The video should communicate one idea:

> RoMi connects live or simulated robot execution, recorded episodes, replay, policy evaluation, and runtime diagnostics through one inspectable contract layer.

The implementation contract is defined in [demo-spec.md](demo-spec.md). Work items are tracked in [demo-backlog.md](demo-backlog.md). The example scaffold is in [../examples/navigation_manipulation_demo](../examples/navigation_manipulation_demo), and capture steps are in [capture-guide.md](../examples/navigation_manipulation_demo/capture-guide.md).

The intended scenario:

1. A robot starts in a simulated or live environment.
2. It navigates to a manipulation area.
3. It observes an object, target, shelf, drawer, bin, or station.
4. It runs a mock policy over synchronized navigation and manipulation observations.
5. The policy emits proposed actions without direct actuator authority.
6. RoMi records the episode.
7. The same episode is replayed.
8. Graph, latency, frame, QoS, and policy diagnostics are shown.
9. A notebook or dataset view opens the recorded episode.

## Recommended First Video

Length: 60 to 90 seconds.

Recommended structure:

```text
0:00 - 0:10  README title frame and runtime graph overview
0:10 - 0:25  ROS2 simulator or robot publishes navigation and manipulation streams
0:25 - 0:40  RoMi bridge records an episode while graph diagnostics update
0:40 - 0:55  Mock policy consumes observations and emits proposed actions
0:55 - 1:10  Episode replay runs through the same graph
1:10 - 1:25  Dataset or notebook view inspects synchronized observations
1:25 - 1:30  Summary frame: live, replay, dataset, policy, diagnostics
```

## Signals To Show

The first demo should include a narrow but representative set of signals.

Navigation:

- Odometry
- TF and static TF
- Navigation goal or waypoint
- Path or local plan if available
- Velocity command or proposed velocity command

Manipulation:

- RGB or RGB-D camera stream
- Joint state
- End-effector pose or transform
- Gripper state or command proposal
- Object, target, or task marker

Runtime:

- Node graph
- Stream schemas
- Message rates
- Latency
- Drops or gaps
- Frame diagnostics
- QoS diagnostics from the ROS2 bridge where available
- Policy input freshness and inference latency

Dataset / replay:

- Episode ID
- Time range
- Stream list
- Replay clock state
- Synchronized observation window

## Mock Policy Contract

The demo policy can be a stub. It exists to validate the runtime contract, not to prove model quality.

The policy should:

- Consume synchronized observation windows.
- Receive navigation and manipulation context.
- Emit proposed actions, not direct actuator commands.
- Report input freshness and inference latency.
- Run against live bridged streams and replayed streams.
- Make actuator authority boundaries visible.

Example proposed actions:

- Navigate to waypoint
- Align base near manipulation target
- Move end effector toward target pose
- Open or close gripper

## README Embed Target

When the first video exists, the README should embed it near the top under `Target Demo Video: Navigation + Manipulation`.

Preferred README content:

```markdown
https://github.com/<org>/<repo>/assets/<asset-id>
```

GitHub renders uploaded video assets directly in Markdown. Large binary video files should usually not be committed to the repository unless there is a clear reason.

## Acceptance Criteria

The first demo is good enough when a senior robotics engineer can see:

- RoMi is not being presented as a full ROS replacement.
- ROS2 interop is bridge-first.
- Live and replay paths share the same graph concept.
- Recorded data can become a dataset view.
- Policy inference is part of the runtime contract.
- Proposed policy actions are separate from actuator authority.
- Runtime diagnostics are visible and useful.
- The demo is credible without claiming production readiness.

## Non-Goals

The first demo should not try to:

- Replace Nav2, MoveIt, Autoware, or ROS2.
- Prove a real learned policy.
- Support every robot message type.
- Benchmark transport performance.
- Introduce a permanent language or transport decision.
- Claim hardware safety certification.
