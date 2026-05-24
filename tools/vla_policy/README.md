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

# GPU-trained neural behavior-cloning policy (torch)
python3 train_bc_mlp.py --episodes 1-50 --epochs 600 --output bc_mlp_weights.json
python3 romi_vla_policy.py --input episode.jsonl --backend neural_bc \
  --neural-weights bc_mlp_weights.json --device cpu --output policy.jsonl

# Real reasoning policy (needs ANTHROPIC_API_KEY)
python3 romi_vla_policy.py --input episode.jsonl --backend claude --output policy.jsonl
```

## Backends

| Backend | Description |
| --- | --- |
| `heuristic` | Deterministic proportional go-to-anchor controller. Always runs. |
| `bc_knn` | Non-parametric behavior cloning: proposes a distance-weighted average of the actions taken in the nearest demonstrated states. Learned from data, deterministic, numpy only. Build its memory with `build_bc_memory.py`. |
| `neural_bc` | A small MLP trained by gradient descent on demonstrations (GPU via `train_bc_mlp.py`). Inference defaults to CPU and is deterministic. The learned-action core that VLAs also share. |
| `claude` | Lets a Claude model reason over a compact textual observation and propose the next target. Requires `ANTHROPIC_API_KEY`. |

All backends share one observation/output envelope. The observation here is the
2D agent state, not pixels, so `neural_bc` is a behavior-cloning network rather
than a vision-language model; a real vision VLA (OpenVLA / SmolVLA) can be added
behind the same `propose()` interface once camera frames are imported.

The policy never commands an actuator. Each proposal carries an explicit
`safety_boundary` with `actuator_authority: none`.

Evaluate proposals against recorded expert actions with
[`tools/policy_eval`](../policy_eval).
