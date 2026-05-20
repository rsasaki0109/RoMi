# RoMi Policy Compare: romi_2d_nav_manip_demo

- report kind: romi.counterfactual_policy_compare
- clock: sim_time @ 11.8s
- stage: grasp
- observation window: 5/6 fresh
- actuator authority: none
- command stream: not_emitted
- promotion required: external_supervisor

## Policies

| policy | role | latency | authority | actuator | command stream |
| --- | --- | ---: | --- | --- | --- |
| mock_policy_v1 | baseline | 0.9ms | proposed_only | none | not_emitted |
| mock_policy_v2_guarded | counterfactual | 1.85ms | proposed_only | none | not_emitted |

## Action Diffs

| target | baseline | counterfactual | changed |
| --- | --- | --- | --- |
| base | hold_position | hold_position | no |
| end_effector | carry_object | hold_until_inputs_fresh | yes |
| gripper | hold_closed | hold_last_safe | yes |
