# Replay Source Prototype

Status: prototype.

This tool reads a prototype RoMi episode directory and re-emits recorded `stream_sample` events as replayed RoMi stream samples.

It is intended for the README navigation + manipulation demo path:

```text
episode directory -> replay source -> mock policy / diagnostics
```

## Run

From the repository root:

```bash
python3 tools/replay_source/romi_replay_episode.py \
  --episode examples/navigation_manipulation_demo/artifacts/episodes/nav_manip_demo_001 \
  --output examples/navigation_manipulation_demo/artifacts/replay-events.jsonl \
  --no-sleep
```

For time-scaled replay:

```bash
python3 tools/replay_source/romi_replay_episode.py \
  --episode examples/navigation_manipulation_demo/artifacts/episodes/nav_manip_demo_001 \
  --output examples/navigation_manipulation_demo/artifacts/replay-events.jsonl \
  --speed 2.0
```

## Output

The replay output is JSON Lines.

Event kinds:

- `replay_start`
- `stream_sample`
- `diagnostic_event`
- `replay_stop`

Replayed `stream_sample` events preserve the original `stream_id`, `schema_id`, `event_time_ns`, and payload summary. They set `source_system` to `replay` and add a `replay` object with original event time, replay elapsed time, speed, and episode ID.

## Notes

- This reads the JSONL prototype episode layout from `tools/episode_recorder`.
- It is not a final replay runtime.
- It does not require a live ROS2 graph.
