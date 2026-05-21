# RoMi Replay Evaluation Timeline: romi_2d_nav_manip_demo

- report kind: romi.replay_evaluation_timeline
- clock: sim_time
- duration: 16s
- samples: 17
- policies: mock_policy_v1 vs mock_policy_v2_guarded
- actuator authority: none
- command stream: not_emitted
- promotion required: external_supervisor

## Samples

| time | stage | inputs fresh | latency | changed actions | command stream |
| ---: | --- | ---: | ---: | ---: | --- |
| 0s | initialize | 6/6 | 2.15ms | 2 | not_emitted |
| 0.4s | initialize | 5/6 | 2.35ms | 2 | not_emitted |
| 1.6s | navigate | 5/6 | 2.63ms | 3 | not_emitted |
| 3.2s | navigate | 6/6 | 2.61ms | 3 | not_emitted |
| 4.8s | navigate | 5/6 | 2.84ms | 3 | not_emitted |
| 5.04s | navigate | 6/6 | 2.64ms | 3 | not_emitted |
| 6.4s | navigate | 5/6 | 2.7ms | 3 | not_emitted |
| 8s | navigate | 6/6 | 2.25ms | 3 | not_emitted |
| 9.6s | reach | 5/6 | 2.16ms | 3 | not_emitted |
| 10.4s | reach | 5/6 | 2.16ms | 3 | not_emitted |
| 11.2s | reach | 6/6 | 1.68ms | 2 | not_emitted |
| 12.16s | grasp | 6/6 | 1.65ms | 2 | not_emitted |
| 12.8s | place | 5/6 | 1.87ms | 2 | not_emitted |
| 13.76s | place | 5/6 | 1.96ms | 2 | not_emitted |
| 14.4s | place | 5/6 | 2.05ms | 2 | not_emitted |
| 15.36s | report | 5/6 | 2.22ms | 2 | not_emitted |
| 16s | report | 6/6 | 2.15ms | 2 | not_emitted |

## Stage Summary

| stage | samples | changed samples | min fresh inputs | max latency | command stream |
| --- | ---: | ---: | ---: | ---: | --- |
| initialize | 2 | 2 | 5 | 2.35ms | not_emitted |
| navigate | 6 | 6 | 5 | 2.84ms | not_emitted |
| reach | 3 | 3 | 5 | 2.16ms | not_emitted |
| grasp | 1 | 1 | 6 | 1.65ms | not_emitted |
| place | 3 | 3 | 5 | 2.05ms | not_emitted |
| report | 2 | 2 | 5 | 2.22ms | not_emitted |
