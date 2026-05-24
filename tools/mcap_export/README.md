# romi_mcap_export

Export a RoMi episode (and optional policy proposals) to an [MCAP](https://mcap.dev)
file that opens directly in [Foxglove Studio](https://foxglove.dev). Needs the
`mcap` package.

```bash
python3 romi_mcap_export.py \
  --episode episode.jsonl \
  --policy policy.bc_knn.jsonl \
  --output episode.mcap
```

## Mapping

RoMi streams map onto Foxglove well-known schemas so the 3D and Raw panels work
out of the box:

| RoMi stream | MCAP topic | Foxglove schema |
| --- | --- | --- |
| `robot.base.odom` | `/robot/base/pose` | `foxglove.PoseInFrame` |
| `expert.action` | `/expert/goal` | `foxglove.PoseInFrame` |
| `policy.proposed_action` | `/policy/proposed_goal` | `foxglove.PoseInFrame` |
| `task.goal` | `/task/goal` | `foxglove.Log` |

Event time, frame id, and stream identity are preserved. This is a mapping from
the existing stream envelope, not a new storage layer — RoMi stays
MCAP-compatible, not MCAP-only.

Open the result in Foxglove Studio (`File -> Open local file`) to scrub the
agent pose, the recorded expert goal, and the policy's proposed goal together on
one timeline.
