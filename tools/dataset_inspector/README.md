# Dataset Inspector Prototype

Status: prototype.

This tool reads a prototype RoMi episode directory and produces a small dataset-style inspection report.

It is intended for the README navigation + manipulation demo path:

```text
episode directory + optional policy output -> report.json / report.md
```

The report shows:

- Episode metadata
- Stream list and sample counts
- Time range
- Frame IDs
- Diagnostics summary
- Policy proposed actions
- A synchronized observation window around a selected timestamp

## Run

From the repository root:

```bash
python3 tools/dataset_inspector/romi_inspect_dataset.py \
  --episode examples/navigation_manipulation_demo/artifacts/episodes/nav_manip_demo_001 \
  --policy-events examples/navigation_manipulation_demo/artifacts/policy-events.jsonl \
  --output-dir examples/navigation_manipulation_demo/artifacts/dataset-report
```

Without policy output:

```bash
python3 tools/dataset_inspector/romi_inspect_dataset.py \
  --episode examples/navigation_manipulation_demo/artifacts/episodes/nav_manip_demo_001 \
  --output-dir examples/navigation_manipulation_demo/artifacts/dataset-report
```

## Output

- `report.json`: structured report for tools and agents
- `report.md`: human-readable report for README demo video capture

## Notes

- This is a dataset inspection view, not a training framework.
- It preserves runtime semantics instead of flattening the episode into anonymous rows.
- It does not require ROS2.
