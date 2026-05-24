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

IMPORT="${REPO_ROOT}/tools/lerobot_import/romi_lerobot_import.py"
POLICY="${REPO_ROOT}/tools/vla_policy/romi_vla_policy.py"
EVAL="${REPO_ROOT}/tools/policy_eval/romi_policy_eval.py"

if [ "${OFFLINE}" -eq 1 ]; then
  echo "[1/3] offline mode: using committed sample episode"
  cp "${SCRIPT_DIR}/sample_output/episode.jsonl" "${EPISODE_JSONL}"
else
  echo "[1/3] importing ${REPO_ID} episode ${EPISODE}"
  python3 "${IMPORT}" --repo-id "${REPO_ID}" --episode "${EPISODE}" --output "${EPISODE_JSONL}"
fi

echo "[2/3] running ${BACKEND} policy"
python3 "${POLICY}" --input "${EPISODE_JSONL}" --backend "${BACKEND}" --output "${POLICY_JSONL}"

echo "[3/3] evaluating proposals vs recorded expert actions"
python3 "${EVAL}" --episode "${EPISODE_JSONL}" --policy "${POLICY_JSONL}" \
  --json-output "${EVAL_JSON}" --md-output "${EVAL_MD}"

echo
echo "artifacts written to ${OUT_DIR}:"
echo "  - episode.jsonl"
echo "  - policy.${BACKEND}.jsonl"
echo "  - policy_eval.json"
echo "  - policy_eval.md"
