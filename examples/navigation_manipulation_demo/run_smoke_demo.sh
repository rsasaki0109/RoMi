#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

RUN_ID="${ROMI_DEMO_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
ARTIFACT_ROOT="${ROMI_DEMO_ARTIFACT_ROOT:-${SCRIPT_DIR}/artifacts/smoke}"
RUN_DIR="${ARTIFACT_ROOT}/${RUN_ID}"

EPISODE_ID="${ROMI_DEMO_EPISODE_ID:-nav_manip_demo_${RUN_ID}}"
DEMO_SOURCE="${ROMI_DEMO_SOURCE:-native}"
BRIDGE_DURATION_SEC="${ROMI_DEMO_BRIDGE_DURATION_SEC:-7}"
SIM_DURATION_SEC="${ROMI_DEMO_SIM_DURATION_SEC:-}"
SIM_RATE_HZ="${ROMI_DEMO_SIM_RATE_HZ:-}"
DIAGNOSTICS_PERIOD_SEC="${ROMI_DEMO_DIAGNOSTICS_PERIOD_SEC:-}"

SCENARIO="${ROMI_DEMO_SCENARIO:-${SCRIPT_DIR}/scenario.json}"
STREAM_MAP="${SCRIPT_DIR}/stream-map.example.json"
RUNTIME_GRAPH="${SCRIPT_DIR}/runtime-graph.example.json"
SOURCE_EVENTS="${RUN_DIR}/source-events.jsonl"
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

rm -rf "${RUN_DIR}"
mkdir -p "${RUN_DIR}"

echo "[romi demo] run id: ${RUN_ID}"
echo "[romi demo] output: ${RUN_DIR}"
echo "[romi demo] source: ${DEMO_SOURCE}"

case "${DEMO_SOURCE}" in
  native)
    echo "[romi demo] generating RoMi-native navigation + manipulation simulation"
    NATIVE_ARGS=(
      "${SCRIPT_DIR}/romi_native_sim_source.py"
      --output "${SOURCE_EVENTS}"
      --scenario "${SCENARIO}"
    )
    if [[ -n "${SIM_DURATION_SEC}" ]]; then
      NATIVE_ARGS+=(--duration-sec "${SIM_DURATION_SEC}")
    fi
    if [[ -n "${SIM_RATE_HZ}" ]]; then
      NATIVE_ARGS+=(--rate-hz "${SIM_RATE_HZ}")
    fi
    if [[ -n "${DIAGNOSTICS_PERIOD_SEC}" ]]; then
      NATIVE_ARGS+=(--diagnostics-period-sec "${DIAGNOSTICS_PERIOD_SEC}")
    fi
    python3 "${NATIVE_ARGS[@]}"
    ;;
  ros2)
    require_command ros2
    python3 - <<'PY'
try:
    import rclpy  # noqa: F401
except Exception as exc:
    raise SystemExit(f"error: rclpy is not available: {exc}")
PY

    echo "[romi demo] starting ROS2 bridge for ${BRIDGE_DURATION_SEC}s"
    python3 "${REPO_ROOT}/bridges/ros2/rclpy_bridge/romi_ros2_bridge.py" \
      --stream-map "${STREAM_MAP}" \
      --output "${SOURCE_EVENTS}" \
      --diagnostics-period-sec "${DIAGNOSTICS_PERIOD_SEC:-0.5}" \
      --duration-sec "${BRIDGE_DURATION_SEC}" &
    BRIDGE_PID=$!

    sleep 0.8

    echo "[romi demo] publishing scripted ROS2 navigation + manipulation simulation"
    python3 "${SCRIPT_DIR}/ros2_demo_sim_publisher.py" \
      --duration-sec "${SIM_DURATION_SEC:-5.5}" \
      --rate-hz "${SIM_RATE_HZ:-12}"

    wait "${BRIDGE_PID}"
    ;;
  *)
    echo "error: ROMI_DEMO_SOURCE must be 'native' or 'ros2'." >&2
    exit 1
    ;;
esac

echo "[romi demo] recording episode"
python3 "${REPO_ROOT}/tools/episode_recorder/romi_record_episode.py" \
  --input "${SOURCE_EVENTS}" \
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
echo "[romi demo] visual simulator: ${SCRIPT_DIR}/romi_2d_sim/index.html"
echo "[romi demo] shared scenario: ${SCENARIO}"
