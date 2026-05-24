# romi_lerobot_import

Import one episode of a [LeRobot](https://github.com/huggingface/lerobot) v3
dataset into a RoMi episode JSONL. Reads parquet directly over HTTP — no `torch`
or `lerobot` package required (only `pyarrow`).

```bash
python3 romi_lerobot_import.py --repo-id lerobot/pusht --episode 0 --output episode.jsonl
python3 romi_lerobot_import.py --episode 0 --offline   # use cached files only
```

## Mapping

The agent pose becomes `robot.base.odom` (`odometry`), the recorded teleop/expert
`action` becomes `expert.action` (`command`, tagged `recorded_demonstration`),
and the dataset task string becomes `task.goal` (`task_goal`). This keeps RoMi's
existing 2D navigation action space, so the envelopes validate against
`schemas/core/stream_sample.schema.json`.

Downloaded files are cached under `~/.cache/romi-lerobot/` by default
(`--cache-dir` to override).

Pair with [`tools/vla_policy`](../vla_policy) and [`tools/policy_eval`](../policy_eval).
See [`examples/lerobot_vla_eval`](../../examples/lerobot_vla_eval).
