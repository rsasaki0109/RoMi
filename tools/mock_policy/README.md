# Mock Policy Prototype

Status: prototype.

This tool reads RoMi JSONL stream samples from a live bridge output or replay output and emits a mock `policy.proposed_action` stream.

It is intended for the README navigation + manipulation demo path:

```text
bridge or replay JSONL -> mock policy -> proposed action JSONL
```

The mock policy is not a learned model. It exists to validate RoMi's policy-runtime contract:

- Consume observation streams.
- Track input freshness.
- Emit proposed actions.
- Report inference latency.
- Avoid direct actuator authority.

## Run

From the repository root:

```bash
python3 tools/mock_policy/romi_mock_policy.py \
  --input examples/navigation_manipulation_demo/artifacts/replay-events.jsonl \
  --output examples/navigation_manipulation_demo/artifacts/policy-events.jsonl
```

Optional:

```bash
python3 tools/mock_policy/romi_mock_policy.py \
  --input examples/navigation_manipulation_demo/artifacts/replay-events.jsonl \
  --output examples/navigation_manipulation_demo/artifacts/policy-events.jsonl \
  --trigger-stream task.goal \
  --required-stream task.goal \
  --freshness-max-age-ms 500
```

## Output

The output is JSON Lines.

Event kinds:

- `policy_start`
- `stream_sample` for `policy.proposed_action`
- `diagnostic_event`
- `policy_stop`

The proposed action is explicitly non-authoritative:

```json
{
  "stream_id": "policy.proposed_action",
  "payload_summary": {
    "kind": "proposed_action",
    "proposed_actions": [
      {
        "target": "base",
        "action_type": "navigate_to_goal",
        "authority": "proposed_only"
      }
    ]
  }
}
```

## Notes

- The tool accepts live bridge JSONL or replay JSONL.
- It does not command actuators.
- It does not require ROS2.
- It is not a final policy runtime.
