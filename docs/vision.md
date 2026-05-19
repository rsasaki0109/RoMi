# RoMi Vision

RoMi is a Physical AI-friendly robotics middleware concept for replayable, inspectable, simulation-native robot runtimes.

It is not a rejection of ROS. It is an attempt to define a middleware layer that is native to replay, simulation, dataset, and policy workflows while remaining interoperable with existing robotics systems.

## Why ROS Succeeded

ROS succeeded because it made robotics integration practical.

Important strengths include:

- A shared component model for robot software
- Topic, service, and action communication patterns
- A large ecosystem of drivers, tools, and packages
- A common mental model for distributed robot systems
- Logging, visualization, and debugging tools
- Coordinate frame conventions through tf and tf2
- A culture of reusable robotics software

For many teams, ROS became the default integration surface between sensors, perception, planning, control, simulation, visualization, and robot-specific hardware.

## Where ROS2 and DDS Still Help

ROS2 improved several important areas:

- More explicit communication quality-of-service controls
- DDS-backed distributed communication
- Better support for production deployments than ROS1
- Improved lifecycle patterns
- Multi-language support
- Real-time-oriented design paths
- Stronger support for robotics products and fleets

DDS remains valuable where distributed systems need discovery, QoS, durability, deadlines, liveliness, and reliable communication across hosts and processes. ROS2 also remains a practical choice for Nav2, Autoware, many simulator integrations, robot drivers, and large parts of the robotics tooling ecosystem.

RoMi should preserve access to these strengths through interoperability rather than assuming they should be replaced.

## Why Modern Robot Learning Changes the Requirements

Modern robot learning workflows often begin with data rather than live runtime code. A team may collect episodes, curate datasets, train policies, evaluate on replay, test in simulation, and then deploy a policy into a constrained runtime.

This exposes middleware requirements that are not always first-class in classical systems:

- Logs must behave like runtime sources, not just archives.
- Dataset rows need time, frame, schema, and world semantics.
- Tensor data must move efficiently between cameras, policies, GPUs, logs, and notebooks.
- Evaluation often depends on replaying exact episodes and comparing policy behavior.
- Simulation is part of the development loop, not only a final integration target.
- Runtime graphs need to expose policy inputs, outputs, latency, authority, and failure modes.
- Developers need to move between notebooks, training jobs, simulators, logs, and deployed robot processes without rewriting core assumptions.

RoMi aims to make these workflows explicit in the middleware model.

## Why Manipulation Often Moves Toward SDK-Style Workflows

Manipulation and embodied AI workflows often use SDK-style stacks because they need tight control over:

- Robot-specific calibration and kinematics
- Teleoperation and demonstration collection
- Camera and tactile sensor synchronization
- Policy inference loops
- GPU memory movement
- Dataset curation and episode replay
- End-effector control, constraints, and safety gates

An SDK can provide a direct path from data collection to training to policy deployment. That can be more productive than assembling a large distributed graph for every experiment.

However, SDK-style workflows can become hard to inspect, replay, compose, or integrate with broader robot infrastructure. RoMi should learn from the productivity of SDKs while keeping middleware-level contracts visible.

## Why Autonomous Mobility Still Benefits From Modular Middleware

Autonomous mobility systems often require modular, inspectable, distributed middleware because they combine many long-running subsystems:

- Localization
- Mapping
- Perception
- Prediction
- Planning
- Control
- Health monitoring
- Fleet or mission management
- Simulation and scenario replay
- Operator visualization

ROS-style modularity remains useful here. Teams need independent components, typed interfaces, diagnostics, replay, and tooling that can support large runtime graphs.

RoMi should not force manipulation-style SDK workflows onto autonomous mobility, nor should it force mobility-style component graphs onto every manipulation experiment. It should support a clearer contract between both modes.

## What RoMi Aims To Become

RoMi aims to become a middleware contract layer for Physical AI-era robot systems:

- Replay-first runtime graphs
- Transport-agnostic data movement
- Schema-native and tensor-aware data models
- Time, frame, and world semantics across live, simulated, and recorded execution
- Dataset-native logging and loading
- Policy-runtime aware deployment contracts
- Runtime introspection for graphs, latency, frames, QoS, and authority
- Bridge-first interoperability with ROS2, DDS, MCAP, simulators, and vendor SDKs

The long-term goal is to make the same robot behavior easier to inspect across live robots, simulators, logs, datasets, notebooks, training loops, and deployment runtimes.

## What RoMi Does Not Aim To Become

RoMi does not aim to become:

- A full ROS replacement as its first objective
- A fork of ROS2 under a new name
- A single-language robotics framework
- A single-transport messaging stack
- A simulator-specific runtime
- An ML training framework
- A dataset format that ignores live robot execution
- A robot SDK tied to one vendor or hardware class

RoMi should be judged by whether it defines useful, interoperable runtime contracts for modern robotics workflows, not by whether it immediately recreates every feature of existing ecosystems.
