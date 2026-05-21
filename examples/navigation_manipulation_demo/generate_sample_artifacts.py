#!/usr/bin/env python3
"""Regenerate committed sample artifacts for the navigation/manipulation demo."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


EPISODE_ID = "nav_manip_demo_sample"
SCENARIO_NAME = "navigation_to_table_and_mock_pick"
WORLD_ID = "demo_world"
ROBOT_ID = "mobile_manipulator_demo"
NORMALIZED_POLICY_LATENCY_MS = 0.004


def parse_args(argv: list[str]) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    example_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--example-dir", type=Path, default=example_dir)
    parser.add_argument("--output-dir", type=Path, default=example_dir / "sample_output")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional working directory. Defaults to a temporary directory.",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep the generated intermediate episode and JSONL files. Use --work-dir for a stable kept path.",
    )
    return parser.parse_args(argv)


def run_command(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in events),
        encoding="utf-8",
    )


def normalize_policy_events(path: Path) -> None:
    events = load_jsonl(path)
    for event in events:
        payload = event.get("payload_summary")
        if isinstance(payload, dict) and "inference_latency_ms" in payload:
            payload["inference_latency_ms"] = NORMALIZED_POLICY_LATENCY_MS
    write_jsonl(path, events)


def decorate_dataset_report(markdown: str) -> str:
    sample_note = [
        "This committed sample shows the shape of the report produced by:",
        "",
        "```bash",
        "examples/navigation_manipulation_demo/generate_sample_artifacts.py",
        "```",
        "",
        "Fresh local smoke runs write ignored output under `examples/navigation_manipulation_demo/artifacts/`.",
    ]
    if "This committed sample shows the shape" not in markdown:
        markdown = markdown.replace(
            "Prototype RoMi dataset inspection report.\n",
            "Prototype RoMi dataset inspection report.\n\n" + "\n".join(sample_note) + "\n",
            1,
        )

    artifact_section = [
        "## Policy And Timeline Artifacts",
        "",
        "RoMi Studio can replay the episode state, compare the baseline mock policy against a guarded counterfactual policy, and export review artifacts:",
        "",
        "- Policy compare Markdown: [`../policy_compare.md`](../policy_compare.md)",
        "- Policy compare JSON: [`../policy_compare.json`](../policy_compare.json)",
        "- Evaluation timeline Markdown: [`../evaluation_timeline.md`](../evaluation_timeline.md)",
        "- Evaluation timeline JSON: [`../evaluation_timeline.json`](../evaluation_timeline.json)",
        "- Safety authority Markdown: [`../safety_authority.md`](../safety_authority.md)",
        "- Safety authority JSON: [`../safety_authority.json`](../safety_authority.json)",
        "- Safety boundary: `proposed_only`, actuator authority `none`, command stream `not_emitted`",
        "",
        "",
    ]
    if "## Policy And Timeline Artifacts" not in markdown:
        markdown = markdown.replace("## Observation Window\n", "\n".join(artifact_section) + "## Observation Window\n", 1)

    return markdown


def normalize_dataset_report(report: dict[str, Any]) -> dict[str, Any]:
    report["generated_at_unix_ns"] = 0
    report["episode_dir"] = "examples/navigation_manipulation_demo/sample_output/dataset-report"
    return report


def write_report_manifest(output_dir: Path) -> None:
    manifest = {
        "schema_version": "0.1.0",
        "manifest_kind": "romi.report_artifact_manifest",
        "generated_by": "examples/navigation_manipulation_demo/generate_sample_artifacts.py",
        "artifacts": [
            {
                "artifact_id": "dataset_report",
                "report_kind": "dataset_inspection_report",
                "json_path": "dataset-report/report.json",
                "markdown_path": "dataset-report/report.md",
                "schema_path": "../../../schemas/core/dataset_report.schema.json",
            },
            {
                "artifact_id": "policy_compare",
                "report_kind": "romi.counterfactual_policy_compare",
                "json_path": "policy_compare.json",
                "markdown_path": "policy_compare.md",
                "schema_path": "../../../schemas/ml/policy_compare.schema.json",
                "authority_boundary": {
                    "policy_authority": "proposed_only",
                    "actuator_authority": "none",
                    "command_stream_emitted": False,
                },
            },
            {
                "artifact_id": "evaluation_timeline",
                "report_kind": "romi.replay_evaluation_timeline",
                "json_path": "evaluation_timeline.json",
                "markdown_path": "evaluation_timeline.md",
                "schema_path": "../../../schemas/ml/evaluation_timeline.schema.json",
                "authority_boundary": {
                    "policy_authority": "proposed_only",
                    "actuator_authority": "none",
                    "command_stream_emitted": False,
                },
            },
            {
                "artifact_id": "safety_authority",
                "report_kind": "romi.safety_authority_report",
                "json_path": "safety_authority.json",
                "markdown_path": "safety_authority.md",
                "schema_path": "../../../schemas/core/safety_authority.schema.json",
                "authority_boundary": {
                    "policy_authority": "proposed_only",
                    "actuator_authority": "none",
                    "command_stream_emitted": False,
                },
            },
        ],
    }
    (output_dir / "report_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


STUDIO_ARTIFACT_SCRIPT = r"""
(async () => {
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const repo = process.argv[1];
const outputDir = process.argv[2];
const scenario = JSON.parse(fs.readFileSync(path.join(repo, "examples/navigation_manipulation_demo/scenario.json"), "utf8"));

function fakeClassList() {
  return { add() {}, remove() {}, toggle() {} };
}

function fakeContext() {
  return new Proxy({}, {
    get(target, prop) {
      if (!(prop in target)) target[prop] = () => {};
      return target[prop];
    },
    set(target, prop, value) {
      target[prop] = value;
      return true;
    },
  });
}

function fakeElement(id = "") {
  return {
    id,
    dataset: {},
    style: {},
    className: "",
    value: "0",
    textContent: "",
    innerHTML: "",
    classList: fakeClassList(),
    setAttribute() {},
    addEventListener() {},
    appendChild() {},
    append() {},
    click() {},
    querySelector() { return fakeElement("nested"); },
    closest() { return null; },
    getContext: id === "simCanvas" ? () => fakeContext() : undefined,
    width: 960,
    height: 620,
  };
}

const elements = new Map();
function byId(id) {
  if (!elements.has(id)) elements.set(id, fakeElement(id));
  return elements.get(id);
}

const modeButtons = ["live", "replay", "policy", "compare", "timeline", "safety", "dataset"]
  .map((mode) => ({ ...fakeElement(`mode-${mode}`), dataset: { mode } }));

const context = {
  console,
  URLSearchParams,
  Date,
  Math,
  Number,
  String,
  Boolean,
  Array,
  Object,
  JSON,
  Set,
  Blob: class Blob {},
  fetch: async () => ({ ok: true, json: async () => scenario }),
};

context.document = {
  body: { classList: fakeClassList() },
  getElementById: byId,
  querySelectorAll: (selector) => selector === ".mode-tab" ? modeButtons : [],
  querySelector: () => fakeElement("query"),
  createElement: fakeElement,
};
context.window = {
  location: { search: "" },
  requestAnimationFrame() {},
  URL: { createObjectURL() { return "blob:fake"; }, revokeObjectURL() {} },
};
context.globalThis = context;

vm.createContext(context);
vm.runInContext(
  fs.readFileSync(path.join(repo, "examples/navigation_manipulation_demo/romi_2d_sim/sim.js"), "utf8"),
  context,
);

for (let i = 0; i < 20 && !context.window.romiCapture.ready(); i += 1) {
  await new Promise((resolve) => setTimeout(resolve, 10));
}
if (!context.window.romiCapture.ready()) {
  throw new Error(context.window.romiCapture.error() || "simulator API did not become ready");
}

context.window.romiCapture.seekToSeconds(11.8);
fs.writeFileSync(path.join(outputDir, "policy_compare.json"), `${context.window.romiCapture.policyCompareReportJson()}\n`);
fs.writeFileSync(path.join(outputDir, "policy_compare.md"), `${context.window.romiCapture.policyCompareReportMarkdown()}\n`);
fs.writeFileSync(path.join(outputDir, "evaluation_timeline.json"), `${context.window.romiCapture.evaluationTimelineReportJson()}\n`);
fs.writeFileSync(path.join(outputDir, "evaluation_timeline.md"), `${context.window.romiCapture.evaluationTimelineReportMarkdown()}\n`);
context.window.romiCapture.seekToSeconds(13.6);
fs.writeFileSync(path.join(outputDir, "safety_authority.json"), `${context.window.romiCapture.safetyReportJson()}\n`);
fs.writeFileSync(path.join(outputDir, "safety_authority.md"), `${context.window.romiCapture.safetyReportMarkdown()}\n`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""


def generate_studio_artifacts(*, repo_root: Path, output_dir: Path) -> None:
    if shutil.which("node") is None:
        raise RuntimeError("node is required to regenerate Studio sample artifacts")
    run_command(["node", "-e", STUDIO_ARTIFACT_SCRIPT, str(repo_root), str(output_dir)], cwd=repo_root)


def generate_dataset_artifact(*, repo_root: Path, example_dir: Path, output_dir: Path, work_dir: Path) -> None:
    source_events = work_dir / "source-events.jsonl"
    episode_dir = work_dir / "episode"
    replay_events = work_dir / "replay-events.jsonl"
    policy_events = work_dir / "policy-events.jsonl"
    dataset_report_dir = work_dir / "dataset-report"

    run_command(
        [
            sys.executable,
            str(example_dir / "romi_native_sim_source.py"),
            "--output",
            str(source_events),
            "--scenario",
            str(example_dir / "scenario.json"),
        ],
        cwd=repo_root,
    )
    run_command(
        [
            sys.executable,
            str(repo_root / "tools/episode_recorder/romi_record_episode.py"),
            "--input",
            str(source_events),
            "--output",
            str(episode_dir),
            "--episode-id",
            EPISODE_ID,
            "--scenario-name",
            SCENARIO_NAME,
            "--mode",
            "simulation",
            "--world-id",
            WORLD_ID,
            "--robot-id",
            ROBOT_ID,
            "--runtime-graph",
            str(example_dir / "runtime-graph.example.json"),
        ],
        cwd=repo_root,
    )
    run_command(
        [
            sys.executable,
            str(repo_root / "tools/replay_source/romi_replay_episode.py"),
            "--episode",
            str(episode_dir),
            "--output",
            str(replay_events),
            "--no-sleep",
        ],
        cwd=repo_root,
    )
    run_command(
        [
            sys.executable,
            str(repo_root / "tools/mock_policy/romi_mock_policy.py"),
            "--input",
            str(replay_events),
            "--output",
            str(policy_events),
        ],
        cwd=repo_root,
    )
    normalize_policy_events(policy_events)
    run_command(
        [
            sys.executable,
            str(repo_root / "tools/dataset_inspector/romi_inspect_dataset.py"),
            "--episode",
            str(episode_dir),
            "--policy-events",
            str(policy_events),
            "--output-dir",
            str(dataset_report_dir),
        ],
        cwd=repo_root,
    )

    target_dir = output_dir / "dataset-report"
    target_dir.mkdir(parents=True, exist_ok=True)
    report = normalize_dataset_report(load_json(dataset_report_dir / "report.json"))
    (target_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown = (dataset_report_dir / "report.md").read_text(encoding="utf-8")
    (target_dir / "report.md").write_text(decorate_dataset_report(markdown), encoding="utf-8")


def generate(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    example_dir = args.example_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.work_dir is not None:
        work_dir = args.work_dir.resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup = None
    else:
        cleanup = tempfile.TemporaryDirectory(prefix="romi-sample-artifacts-", ignore_cleanup_errors=True)
        work_dir = Path(cleanup.name)

    try:
        generate_dataset_artifact(
            repo_root=repo_root,
            example_dir=example_dir,
            output_dir=output_dir,
            work_dir=work_dir,
        )
        generate_studio_artifacts(repo_root=repo_root, output_dir=output_dir)
        write_report_manifest(output_dir)
        return {
            "output_dir": str(output_dir),
            "work_dir": str(work_dir),
            "kept_work_dir": bool(args.work_dir or args.keep_work_dir),
            "artifacts": [
                "dataset-report/report.md",
                "dataset-report/report.json",
                "report_manifest.json",
                "policy_compare.md",
                "policy_compare.json",
                "evaluation_timeline.md",
                "evaluation_timeline.json",
                "safety_authority.md",
                "safety_authority.json",
            ],
        }
    finally:
        if cleanup is not None and not args.keep_work_dir:
            cleanup.cleanup()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    result = generate(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
