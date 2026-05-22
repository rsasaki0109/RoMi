# RoMi Safety Authority Report: romi_2d_nav_manip_demo

- report kind: romi.safety_authority_report
- clock: sim_time
- stage: place
- policy stream: policy.proposed_action
- policy authority: proposed_only
- actuator authority: none
- command stream: not_emitted
- promotion required: external_supervisor
- blocked reason: proposal_not_actuator_authority

## Proposed Actions

| target | action | authority | blocked | reason |
| --- | --- | --- | --- | --- |
| base | hold_position | proposed_only | yes | proposal_not_actuator_authority |
| end_effector | carry_object | proposed_only | yes | proposal_not_actuator_authority |
| gripper | hold_closed | proposed_only | yes | proposal_not_actuator_authority |
