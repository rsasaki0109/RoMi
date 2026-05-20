# RoMi 2D Navigation + Manipulation Demo

This is a browser-based visual simulator for the RoMi semi-humanoid navigation + manipulation contract demo.

It is intentionally lightweight:

- No ROS2 required.
- No build step required.
- Runs from `index.html`.
- Emits RoMi-shaped JSONL events in the browser for inspection/export.
- Loads the shared `../scenario.json` used by the native smoke pipeline.

Open the demo locally:

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory examples/navigation_manipulation_demo
# in another terminal:
xdg-open http://127.0.0.1:8000/romi_2d_sim/
```

The simulator shows a semi-humanoid mobile manipulator navigating to a work area, reaching for an object, grasping it, and placing it in a bin. The right-side panels expose stream counts, runtime stage, policy proposal state, and a recent event log.

This is not a physics simulator. It is a visual contract demo for RoMi stream, replay, observability, and policy-runtime semantics.
