# romi_policy_eval

Counterfactually evaluate proposed policy actions against recorded expert
actions over a replayed episode. Aligns `policy.proposed_action` proposals with
`expert.action` recorded demonstrations by event time and measures the action
error — before any actuator is touched.

```bash
python3 romi_policy_eval.py \
  --episode episode.jsonl \
  --policy policy.jsonl \
  --json-output policy_eval.json \
  --md-output policy_eval.md
```

## Output

A structured JSON report (`romi.counterfactual_policy_eval`, validated against
`schemas/ml/policy_eval.schema.json`) plus a readable Markdown summary with:

- mean / median / p95 / max action error (pixels),
- agreement rate within a tolerance,
- time of maximum divergence,
- an action-error sparkline across the replay,
- an explicit `proposed_only` / `actuator none` safety boundary.

This tool only evaluates proposals; it never promotes them to commands.

## Visualization

`romi_eval_visualize.py` renders a report into a shareable animated GIF (expert
vs proposed goal trajectories and action error over the replay) plus a poster
PNG. It reads only the evaluation report and needs `matplotlib` + `imageio`
(no ffmpeg).

```bash
python3 romi_eval_visualize.py \
  --report policy_eval.json \
  --gif-output eval.gif \
  --png-output eval.png
```

See [`examples/lerobot_vla_eval`](../../examples/lerobot_vla_eval) for an
end-to-end run on `lerobot/pusht`.
