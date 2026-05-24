# romi_vla_policy

Run a pluggable, non-authoritative RoMi policy over a RoMi episode/replay JSONL.
The policy reads stream samples and proposes `navigate_to_goal` actions. Output
is always `proposed_only` and validates against `schemas/ml/policy_io.schema.json`.

```bash
# Deterministic offline baseline (no network, no API key, no GPU)
python3 romi_vla_policy.py --input episode.jsonl --backend heuristic --output policy.jsonl

# Learned k-NN behavior-cloning policy (numpy only)
python3 build_bc_memory.py --episodes 1-20 --output bc_memory.json
python3 romi_vla_policy.py --input episode.jsonl --backend bc_knn \
  --bc-memory bc_memory.json --output policy.jsonl

# Real reasoning policy (needs ANTHROPIC_API_KEY)
python3 romi_vla_policy.py --input episode.jsonl --backend claude --output policy.jsonl
```

## Backends

| Backend | Description |
| --- | --- |
| `heuristic` | Deterministic proportional go-to-anchor controller. Always runs. |
| `bc_knn` | Non-parametric behavior cloning: proposes a distance-weighted average of the actions taken in the nearest demonstrated states. Learned from data, deterministic, numpy only. Build its memory with `build_bc_memory.py`. |
| `claude` | Lets a Claude model reason over a compact textual observation and propose the next target. Requires `ANTHROPIC_API_KEY`. |

All backends share one observation/output envelope, so a real local VLA
(OpenVLA / SmolVLA) can be added behind the same `propose()` interface later.

The policy never commands an actuator. Each proposal carries an explicit
`safety_boundary` with `actuator_authority: none`.

Evaluate proposals against recorded expert actions with
[`tools/policy_eval`](../policy_eval).
