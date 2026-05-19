#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

RUN_ID="${ROMI_DEMO_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
ARTIFACT_ROOT="${ROMI_DEMO_ARTIFACT_ROOT:-${SCRIPT_DIR}/artifacts/smoke}"
RUN_DIR="${ARTIFACT_ROOT}/${RUN_ID}"

EPISODE_ID="${ROMI_DEMO_EPISODE_ID:-nav_manip_demo_${RUN_ID}}"
BRIDGE_DURATION_SEC="${ROMI_DEMO_BRIDGE_DURATION_SEC:-7}"
SIM_DURATION_SEC="${ROMI_DEMO_SIM_DURATION_SEC:-5.5}"
SIM_RATE_HZ="${ROMI_DEMO_SIM_RATE_HZ:-12}"
DIAGNOSTICS_PERIOD_SEC="${ROMI_DEMO_DIAGNOSTICS_PERIOD_SEC:-0.5}"

STREAM_MAP="${SCRIPT_DIR}/stream-map.example.json"
RUNTIME_GRAPH="${SCRIPT_DIR}/runtime-graph.example.json"
BRIDGE_EVENTS="${RUN_DIR}/ros2-bridge-events.jsonl"
EPISODE_DIR="${RUN_DIR}/episode"
REPLAY_EVENTS="${RUN_DIR}/replay-events.jsonl"
POLICY_EVENTS="${RUN_DIR}/policy-events.jsonl"
REPORT_DIR="${RUN_DIR}/dataset-report"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: required command not found: $1" >&2
    exit 1
  fi
}

require_command python3
require_command ros2

python3 - <<'PY'
try:
    import rclpy  # noqa: F401
except Exception as exc:
    raise SystemExit(f"error: rclpy is not available: {exc}")
PY

rm -rf "${RUN_DIR}"
mkdir -p "${RUN_DIR}"

echo "[romi demo] run id: ${RUN_ID}"
echo "[romi demo] output: ${RUN_DIR}"
echo "[romi demo] starting ROS2 bridge for ${BRIDGE_DURATION_SEC}s"

python3 "${REPO_ROOT}/bridges/ros2/rclpy_bridge/romi_ros2_bridge.py" \
  --stream-map "${STREAM_MAP}" \
  --output "${BRIDGE_EVENTS}" \
  --diagnostics-period-sec "${DIAGNOSTICS_PERIOD_SEC}" \
  --duration-sec "${BRIDGE_DURATION_SEC}" &
BRIDGE_PID=$!

sleep 0.8

echo "[romi demo] publishing scripted ROS2 navigation + manipulation simulation"
python3 "${SCRIPT_DIR}/ros2_demo_sim_publisher.py" \
  --duration-sec "${SIM_DURATION_SEC}" \
  --rate-hz "${SIM_RATE_HZ}"

wait "${BRIDGE_PID}"

echo "[romi demo] recording episode"
python3 "${REPO_ROOT}/tools/episode_recorder/romi_record_episode.py" \
  --input "${BRIDGE_EVENTS}" \
  --output "${EPISODE_DIR}" \
  --episode-id "${EPISODE_ID}" \
  --scenario-name navigation_to_table_and_mock_pick \
  --mode simulation \
  --world-id demo_world \
  --robot-id mobile_manipulator_demo \
  --runtime-graph "${RUNTIME_GRAPH}"

echo "[romi demo] replaying episode"
python3 "${REPO_ROOT}/tools/replay_source/romi_replay_episode.py" \
  --episode "${EPISODE_DIR}" \
  --output "${REPLAY_EVENTS}" \
  --no-sleep

echo "[romi demo] running mock policy"
python3 "${REPO_ROOT}/tools/mock_policy/romi_mock_policy.py" \
  --input "${REPLAY_EVENTS}" \
  --output "${POLICY_EVENTS}"

echo "[romi demo] generating dataset report"
python3 "${REPO_ROOT}/tools/dataset_inspector/romi_inspect_dataset.py" \
  --episode "${EPISODE_DIR}" \
  --policy-events "${POLICY_EVENTS}" \
  --output-dir "${REPORT_DIR}"

echo "[romi demo] rendering README animation from RoMi artifacts"
python3 "${SCRIPT_DIR}/render_sim_video.py" \
  --run-dir "${RUN_DIR}" \
  --gif "${REPO_ROOT}/docs/assets/romi-nav-manip-demo.gif" \
  --mp4 "${RUN_DIR}/romi-nav-manip-demo.mp4"

python3 - "${REPORT_DIR}/report.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("[romi demo] summary")
print(f"  episode: {report['episode']['episode_id']}")
print(f"  streams: {len(report['streams'])}")
print(f"  policy samples: {report['policy']['sample_count']}")
print(f"  observation window streams: {len(report['observation_window']['streams'])}")
PY

echo "[romi demo] done"
echo "[romi demo] report: ${REPORT_DIR}/report.md"
