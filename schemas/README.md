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

These drafts should remain small until the MVP implementation validates the contracts.
