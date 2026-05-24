#!/usr/bin/env python3
"""Score and rank policies across multiple held-out LeRobot episodes.

For each episode in a held-out set, this imports the episode, runs each policy,
and counterfactually evaluates the proposals against the recorded expert
actions. It then aggregates per-policy metrics into a leaderboard report
(JSON + Markdown) and an optional bar-chart PNG.

This turns the single-episode counterfactual eval into a dataset-scale policy
comparison: "how do these policies score against expert demonstrations across a
held-out set, before any actuator is touched?"
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.1.0"
REPORT_KIND = "romi.policy_eval_leaderboard"

TOOLS = Path(__file__).resolve().parents[1]
IMPORT = TOOLS / "lerobot_import" / "romi_lerobot_import.py"
POLICY = TOOLS / "vla_policy" / "romi_vla_policy.py"
EVAL = TOOLS / "policy_eval" / "romi_policy_eval.py"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="lerobot/pusht", help="HuggingFace dataset repo id.")
    parser.add_argument("--episodes", default="0,21,22,23,24", help="Held-out episodes, e.g. '0,21-24'.")
    parser.add_argument(
        "--bc-memory",
        type=Path,
        default=None,
        help="bc_knn memory JSON. When set, a bc_knn policy is added to the leaderboard.",
    )
    parser.add_argument(
        "--neural-weights",
        type=Path,
        default=None,
        help="neural_bc weights JSON. When set, a neural_bc policy is added to the leaderboard.",
    )
    parser.add_argument("--json-output", type=Path, default=None, help="Leaderboard JSON path.")
    parser.add_argument("--md-output", type=Path, default=None, help="Leaderboard Markdown path.")
    parser.add_argument("--png-output", type=Path, default=None, help="Leaderboard bar-chart PNG path.")
    parser.add_argument("--tolerance-px", type=float, default=20.0, help="Agreement tolerance (pixels).")
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache" / "romi-lerobot")
    parser.add_argument("--offline", action="store_true", help="Use cached dataset files only.")
    return parser.parse_args(argv)


def parse_episodes(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(range(int(lo), int(hi) + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def policy_specs(args: argparse.Namespace) -> list[dict[str, Any]]:
    specs = [{"name": "heuristic", "extra": ["--backend", "heuristic"]}]
    if args.bc_memory is not None:
        specs.append(
            {
                "name": "bc_knn",
                "extra": ["--backend", "bc_knn", "--bc-memory", str(args.bc_memory)],
            }
        )
    if args.neural_weights is not None:
        specs.append(
            {
                "name": "neural_bc",
                "extra": ["--backend", "neural_bc", "--neural-weights", str(args.neural_weights), "--device", "cpu"],
            }
        )
    return specs


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    episodes = parse_episodes(args.episodes)
    specs = policy_specs(args)
    per_policy: dict[str, list[dict[str, Any]]] = {spec["name"]: [] for spec in specs}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for episode in episodes:
            episode_jsonl = tmp_dir / f"ep{episode}.jsonl"
            import_cmd = [
                sys.executable, str(IMPORT), "--repo-id", args.repo_id,
                "--episode", str(episode), "--cache-dir", str(args.cache_dir),
                "--output", str(episode_jsonl),
            ]
            if args.offline:
                import_cmd.append("--offline")
            run(import_cmd)

            for spec in specs:
                policy_jsonl = tmp_dir / f"ep{episode}.{spec['name']}.jsonl"
                eval_json = tmp_dir / f"ep{episode}.{spec['name']}.eval.json"
                run([
                    sys.executable, str(POLICY), "--input", str(episode_jsonl),
                    "--output", str(policy_jsonl), *spec["extra"],
                ])
                run([
                    sys.executable, str(EVAL), "--episode", str(episode_jsonl),
                    "--policy", str(policy_jsonl), "--json-output", str(eval_json),
                    "--tolerance-px", str(args.tolerance_px),
                ])
                report = json.loads(eval_json.read_text(encoding="utf-8"))
                per_policy[spec["name"]].append(
                    {
                        "episode": episode,
                        "mean_action_error_px": report["summary"]["mean_action_error_px"],
                        "agreement_rate": report["summary"]["agreement_rate_within_tolerance"],
                        "matched_steps": report["matched_steps"],
                    }
                )

    leaderboard = []
    for name, rows in per_policy.items():
        errors = [r["mean_action_error_px"] for r in rows]
        agreements = [r["agreement_rate"] for r in rows]
        leaderboard.append(
            {
                "policy_id": name,
                "episodes": len(rows),
                "mean_action_error_px": round(statistics.fmean(errors), 4),
                "mean_agreement_rate": round(statistics.fmean(agreements), 4),
                "per_episode": rows,
            }
        )
    leaderboard.sort(key=lambda entry: entry["mean_action_error_px"])

    return {
        "schema_version": SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "dataset": args.repo_id,
        "reference": "recorded_expert_action",
        "tolerance_px": args.tolerance_px,
        "held_out_episodes": episodes,
        "best_policy": leaderboard[0]["policy_id"],
        "safety_boundary": {
            "policy_authority": "proposed_only",
            "actuator_authority": "none",
            "command_stream_emitted": False,
            "blocked_reason": "proposal_not_actuator_authority",
        },
        "leaderboard": leaderboard,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# RoMi Policy Evaluation Leaderboard",
        "",
        f"Counterfactual scoring of {len(report['leaderboard'])} policies against recorded "
        f"expert actions across {len(report['held_out_episodes'])} held-out `{report['dataset']}` "
        f"episodes ({', '.join(str(e) for e in report['held_out_episodes'])}).",
        "",
        "| Rank | Policy | Mean action error | Mean agreement | Episodes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for rank, entry in enumerate(report["leaderboard"], start=1):
        lines.append(
            f"| {rank} | `{entry['policy_id']}` | {entry['mean_action_error_px']} px | "
            f"{round(entry['mean_agreement_rate'] * 100, 1)}% | {entry['episodes']} |"
        )
    lines += [
        "",
        f"**Best policy: `{report['best_policy']}`** (lowest mean action error vs expert).",
        "",
        "All policies stay `proposed_only`; actuator authority is `none`. Scoring a policy "
        "against held-out expert demonstrations never commands an actuator.",
        "",
        f"_Generated by `tools/policy_eval/romi_batch_eval.py` ({report['report_kind']})._",
    ]
    return "\n".join(lines) + "\n"


def render_chart(report: dict[str, Any], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    entries = report["leaderboard"]
    names = [e["policy_id"] for e in entries]
    errors = [e["mean_action_error_px"] for e in entries]
    agreements = [e["mean_agreement_rate"] * 100 for e in entries]
    x = np.arange(len(names))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.4), dpi=82, facecolor="#0d1117")
    for ax in (ax1, ax2):
        ax.set_facecolor("#161b22")
        ax.tick_params(colors="#8b949e", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.set_xticks(x)
        ax.set_xticklabels(names, color="#e6edf3", fontsize=9)

    ax1.bar(x, errors, color="#f0883e", width=0.6)
    ax1.set_title("mean action error vs expert (px) - lower is better", color="#8b949e", fontsize=8.5, loc="left")
    for i, v in enumerate(errors):
        ax1.text(i, v, f" {v:.1f}", color="#e6edf3", fontsize=8, ha="center", va="bottom")

    ax2.bar(x, agreements, color="#3fb950", width=0.6)
    ax2.set_ylim(0, 100)
    ax2.set_title("mean agreement within tolerance (%) - higher is better", color="#8b949e", fontsize=8.5, loc="left")
    for i, v in enumerate(agreements):
        ax2.text(i, v, f" {v:.0f}%", color="#e6edf3", fontsize=8, ha="center", va="bottom")

    fig.suptitle(
        f"RoMi policy leaderboard · {report['dataset']} · {len(report['held_out_episodes'])} held-out episodes",
        color="#e6edf3", fontsize=10.5, fontweight="bold", x=0.5, y=0.99,
    )
    fig.text(0.5, 0.01, "proposed_only · actuator_authority: none", color="#8b949e", fontsize=7.5, ha="center")
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="#0d1117")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    report = build_report(args)

    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_output is not None:
        args.md_output.parent.mkdir(parents=True, exist_ok=True)
        args.md_output.write_text(render_markdown(report), encoding="utf-8")
    if args.png_output is not None:
        render_chart(report, args.png_output)
    if not any([args.json_output, args.md_output, args.png_output]):
        sys.stdout.write(render_markdown(report))

    best = report["leaderboard"][0]
    print(
        f"leaderboard: best={report['best_policy']} "
        f"mean_error={best['mean_action_error_px']}px over {len(report['held_out_episodes'])} episodes",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
