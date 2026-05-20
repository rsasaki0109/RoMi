# RoMi Tools

Small prototype tools live here while the runtime contract is still being validated.

Current tools:

- `episode_recorder/`: converts bridge JSONL output into a prototype episode directory with metadata, stream summary, diagnostics summary, and copied event log.
- `replay_source/`: replays stream samples from a prototype episode directory.
- `mock_policy/`: emits non-authoritative proposed actions from bridge or replay stream samples.
- `dataset_inspector/`: generates dataset-style inspection reports from episodes and optional policy output.

These tools are not the final RoMi runtime or CLI. They exist to support the README navigation + manipulation demo path.
