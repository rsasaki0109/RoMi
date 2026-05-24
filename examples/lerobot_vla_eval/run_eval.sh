#!/usr/bin/env bash
# Replay a LeRobot episode, run a non-authoritative policy, and counterfactually
# compare its proposed actions to the recorded expert actions.
#
# Usage:
#   ./run_eval.sh                 # fetch lerobot/pusht ep0, run heuristic policy
#   ./run_eval.sh --offline       # reuse the committed sample episode (no network)
#   BACKEND=claude ./run_eval.sh  # use the Claude reasoning policy (needs ANTHROPIC_API_KEY)
#
# Environment overrides:
#   REPO_ID   (default lerobot/pusht)
#   EPISODE   (default 0)
#   BACKEND   (default heuristic; or claude)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

REPO_ID="${REPO_ID:-lerobot/pusht}"
EPISODE="${EPISODE:-0}"
BACKEND="${BACKEND:-heuristic}"
OFFLINE=0
[ "${1:-}" = "--offline" ] && OFFLINE=1

OUT_DIR="${ROMI_EVAL_OUT_DIR:-${SCRIPT_DIR}/out}"
mkdir -p "${OUT_DIR}"
EPISODE_JSONL="${OUT_DIR}/episode.jsonl"
POLICY_JSONL="${OUT_DIR}/policy.${BACKEND}.jsonl"
EVAL_JSON="${OUT_DIR}/policy_eval.json"
EVAL_MD="${OUT_DIR}/policy_eval.md"
MCAP_OUT="${OUT_DIR}/episode.mcap"

IMPORT="${REPO_ROOT}/tools/lerobot_import/romi_lerobot_import.py"
POLICY="${REPO_ROOT}/tools/vla_policy/romi_vla_policy.py"
EVAL="${REPO_ROOT}/tools/policy_eval/romi_policy_eval.py"
MCAP="${REPO_ROOT}/tools/mcap_export/romi_mcap_export.py"

if [ "${OFFLINE}" -eq 1 ]; then
  echo "[1/4] offline mode: using committed sample episode"
  cp "${SCRIPT_DIR}/sample_output/episode.jsonl" "${EPISODE_JSONL}"
else
  echo "[1/4] importing ${REPO_ID} episode ${EPISODE}"
  python3 "${IMPORT}" --repo-id "${REPO_ID}" --episode "${EPISODE}" --output "${EPISODE_JSONL}"
fi

# bc_knn needs an imitation memory; default to the committed sample memory.
POLICY_ARGS=(--input "${EPISODE_JSONL}" --backend "${BACKEND}" --output "${POLICY_JSONL}")
if [ "${BACKEND}" = "bc_knn" ]; then
  POLICY_ARGS+=(--bc-memory "${ROMI_BC_MEMORY:-${SCRIPT_DIR}/sample_output/bc_memory.json}")
fi

echo "[2/4] running ${BACKEND} policy"
python3 "${POLICY}" "${POLICY_ARGS[@]}"

echo "[3/4] evaluating proposals vs recorded expert actions"
python3 "${EVAL}" --episode "${EPISODE_JSONL}" --policy "${POLICY_JSONL}" \
  --json-output "${EVAL_JSON}" --md-output "${EVAL_MD}"

echo "[4/4] exporting MCAP for Foxglove"
if python3 -c "import mcap" 2>/dev/null; then
  python3 "${MCAP}" --episode "${EPISODE_JSONL}" --policy "${POLICY_JSONL}" --output "${MCAP_OUT}"
else
  echo "  (skipped: pip install mcap to export Foxglove-ready .mcap)"
fi

echo
echo "artifacts written to ${OUT_DIR}:"
echo "  - episode.jsonl"
echo "  - policy.${BACKEND}.jsonl"
echo "  - policy_eval.json / policy_eval.md"
echo "  - episode.mcap (open in Foxglove Studio)"
