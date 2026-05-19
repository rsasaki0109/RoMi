# Navigation + Manipulation Demo Spec

This document defines the first README-target demo for RoMi. It is a concrete demo specification, not a final architecture or production implementation plan.

## Objective

Show RoMi as a Physical AI-friendly contract layer across:

- ROS2 or simulator streams
- Runtime graph inspection
- Episode recording
- Replay through the same graph shape
- Mock policy inference
- Dataset-style episode access
- Diagnostics for time, frames, latency, QoS, and policy freshness

The demo should be credible before it is broad. It should prove the contract shape, not solve every robotics use case.

## Scenario

A mobile manipulator, simulated or real, performs a simple task:

1. Start in a known environment.
2. Navigate to a work area.
3. Observe a manipulation target.
4. Produce a proposed manipulation action from a mock policy.
5. Record the episode.
6. Replay the episode through the same logical graph.
7. Inspect graph, frame, latency, QoS, and policy diagnostics.
8. Load synchronized observations from the recorded episode.

The first version may use a simulator and a scripted robot behavior. A learned policy is not required.

## Demo Boundaries

### In Scope

- ROS2 bridge boundary for selected topics.
- Small runtime graph representation.
- Structured stream metadata.
- Episode metadata and MCAP-compatible logging direction.
- Replay source contract.
- Mock policy node contract.
- Diagnostics output suitable for video capture.
- Dataset-style inspection of one recorded episode.

### Out Of Scope

- Full ROS2 replacement.
- Full distributed runtime.
- Real learned policy quality.
- Full Nav2 or MoveIt migration.
- Production safety certification.
- Final transport choice.
- Final language choice.

## Minimum Runtime Graph

```text
                 +---------------------+
                 | ROS2 robot or sim   |
                 +----------+----------+
                            |
                            v
                     +------+------+
                     | RoMi bridge |
                     +------+------+
                            |
       +--------------------+--------------------+
       |                    |                    |
       v                    v                    v
 navigation streams   manipulation streams   frame streams
       |                    |                    |
       +----------+---------+--------------------+
                  |
                  v
          +-------+--------+
          | observation    |
          | synchronizer   |
          +-------+--------+
                  |
          +-------+--------+       +----------------+
          | mock policy    +------>| proposed action|
          +-------+--------+       +----------------+
                  |
                  v
          +-------+--------+
          | diagnostics    |
          +----------------+

          +----------------+
          | episode record |
          +-------+--------+
                  |
                  v
          +-------+--------+
          | replay source  |
          +----------------+
```

The first implementation may represent this graph as static metadata if a full runtime graph implementation does not exist yet.

## Required Streams

The exact topic names may vary by simulator or robot. The demo should map source topics into stable RoMi stream names.

| RoMi stream | ROS2 source direction | Purpose |
| --- | --- | --- |
| `robot.camera.rgb` | image topic | Visual observation |
| `robot.camera.depth` | depth image or point cloud topic | Spatial observation |
| `robot.camera.info` | camera info topic | Camera calibration |
| `robot.joints.state` | joint state topic | Manipulator state |
| `robot.base.odom` | odometry topic | Navigation state |
| `robot.frames.tf` | `/tf` and `/tf_static` | Frame graph |
| `task.goal` | navigation goal, marker, or scripted goal | Task intent |
| `policy.observation` | RoMi-derived stream | Synchronized policy input |
| `policy.proposed_action` | RoMi-derived stream | Non-authoritative action proposal |
| `runtime.diagnostics` | RoMi-derived stream | Runtime inspection |

## Recommended ROS2 Message Coverage

The first bridge should prefer common ROS2 message families where available:

- `sensor_msgs/Image`
- `sensor_msgs/CameraInfo`
- `sensor_msgs/PointCloud2` or depth image equivalent
- `sensor_msgs/JointState`
- `nav_msgs/Odometry`
- `geometry_msgs/TransformStamped`
- `tf2_msgs/TFMessage`
- `geometry_msgs/PoseStamped`
- `nav_msgs/Path`
- `geometry_msgs/Twist` for proposed or observed base command where useful

The bridge does not need to support every ROS2 message type.

## Episode Contract

An episode should include:

- Episode ID
- Scenario or environment ID
- Robot ID or robot profile
- Start and end time
- Clock mode
- Stream list
- Schema versions
- Frame graph metadata
- Bridge metadata
- QoS metadata where available
- Runtime graph metadata
- Policy node metadata
- Diagnostics events

The logging direction should remain MCAP-compatible where practical.

## Replay Contract

Replay should:

- Preserve recorded event time.
- Expose replay time separately.
- Support start, stop, pause, seek, and speed controls as design goals.
- Recreate the same logical graph inputs used by the mock policy.
- Report missing streams, timing gaps, frame issues, and schema mismatches.

The first version may implement replay as a minimal reader or scripted playback if that is enough to validate the contract.

## Mock Policy Contract

The mock policy should be intentionally simple.

Inputs:

- Recent RGB or RGB-D observation
- Joint state
- Odometry
- Relevant frame transforms
- Task goal or marker

Outputs:

- Proposed base action
- Proposed end-effector action
- Proposed gripper action
- Confidence or status field
- Inference latency
- Input freshness report

Authority:

- The mock policy emits proposed actions only.
- A separate safety or authority boundary decides whether actions may reach actuators.
- The first demo can stop at proposed actions and does not need to command hardware.

## Diagnostics To Show

The demo video should show enough diagnostics to make RoMi's value visible:

- Runtime graph nodes and streams
- Stream rates
- Latency by stream
- Drops or gaps
- QoS metadata from ROS2 bridge
- Frame tree status
- Missing or stale transform warnings
- Replay clock state
- Policy input freshness
- Policy inference latency
- Proposed action stream

Diagnostics may start as terminal output, JSON, a simple generated report, or a minimal UI. The first demo should optimize for clear video capture.

## Dataset View

The first dataset view should show:

- Episode metadata
- Stream list
- Time range
- Sample count by stream
- Synchronized observation window
- Access to image or tensor-like payload metadata
- Frame and clock metadata

This may start as a notebook or script-generated report. It should not force the runtime to become notebook-centric.

## Video Capture Requirements

The README video should capture:

- Simulator or robot view
- RoMi graph or stream view
- Recording status
- Replay status
- Mock policy proposed actions
- Diagnostics
- Dataset or notebook inspection

The video should be short enough for a README and should avoid claiming production readiness.

## Acceptance Checklist

- [ ] A ROS2 robot or simulator publishes the required source streams.
- [ ] RoMi bridge maps source topics into named streams.
- [ ] A runtime graph view lists bridge, recorder, replay source, mock policy, and diagnostics nodes.
- [ ] An episode is recorded with metadata.
- [ ] The episode can be replayed.
- [ ] The mock policy runs on live and replayed observations.
- [ ] Proposed actions are visibly non-authoritative.
- [ ] Frame diagnostics are visible.
- [ ] Latency or stream diagnostics are visible.
- [ ] Dataset-style inspection can open the recorded episode.
- [ ] README can embed the final video without committing large binary video files.

## Implementation Order

1. Create example scaffold and fixed stream names.
2. Define static schemas and episode metadata.
3. Add a bridge stub or adapter for selected ROS2 streams.
4. Add episode recording path.
5. Add replay source path.
6. Add mock policy node.
7. Add diagnostics output.
8. Add dataset inspection report or notebook.
9. Capture README video.
