# Turtlesim-Style Navigation + Manipulation Demo

This is a browser-based visual simulator for the RoMi navigation + manipulation contract demo.

It is intentionally lightweight:

- No ROS2 required.
- No server required.
- No build step required.
- Runs from `index.html`.
- Emits RoMi-shaped JSONL events in the browser for inspection/export.

Open the demo locally:

```bash
xdg-open examples/navigation_manipulation_demo/turtlesim_demo/index.html
```

The simulator shows a small mobile manipulator navigating to a work area, reaching for an object, grasping it, and placing it in a bin. The right-side panels expose stream counts, runtime stage, policy proposal state, and a recent event log.

This is not a physics simulator. It is a visual contract demo for RoMi stream, replay, observability, and policy-runtime semantics.
