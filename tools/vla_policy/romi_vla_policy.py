#!/usr/bin/env python3
"""Run a pluggable, non-authoritative RoMi policy over a RoMi episode.

The policy reads RoMi stream samples (for example a LeRobot import) and proposes
``navigate_to_goal`` actions. Output is always ``proposed_only`` and never
commands an actuator.

Backends
--------
heuristic
    A deterministic, offline proportional controller toward a goal anchor.
    Needs no network, no API key, and no GPU, so it always runs (CI, demos).
claude
    Uses the Anthropic SDK to let a Claude model reason over a compact textual
    observation and propose the next target. Requires ANTHROPIC_API_KEY. This is
    the "real reasoning policy" path; the same adapter shape can host a local
    VLA (OpenVLA/SmolVLA) later.

The two backends share one observation envelope and one output envelope so the
counterfactual evaluation in romi_policy_eval.py can compare any backend against
the recorded expert actions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.1.0"
POLICY_SCHEMA_ID = "romi.ml.policy_io/0.1.0"

DEFAULT_TRIGGER = "robot.base.odom"
DEFAULT_REQUIRED = "robot.base.odom"


class JsonlWriter:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.file = sys.stdout if path is None else None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.file = path.open("w", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        self.file.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
        self.file.write("\n")

    def close(self) -> None:
        if self.path is not None:
            self.file.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a RoMi non-authoritative policy.")
    parser.add_argument("--input", required=True, type=Path, help="Episode/replay JSONL.")
    parser.add_argument("--output", type=Path, default=None, help="Policy JSONL. Defaults to stdout.")
    parser.add_argument(
        "--backend",
        choices=["heuristic", "bc_knn", "neural_bc", "claude"],
        default="heuristic",
        help="Policy backend. Defaults to heuristic (offline).",
    )
    parser.add_argument("--policy-id", default=None, help="Policy identifier override.")
    parser.add_argument(
        "--trigger-stream",
        action="append",
        default=[],
        help=f"Stream that triggers a proposal. Defaults to {DEFAULT_TRIGGER}.",
    )
    parser.add_argument(
        "--required-stream",
        action="append",
        default=[],
        help=f"Stream required before proposing. Defaults to {DEFAULT_REQUIRED}.",
    )
    parser.add_argument(
        "--freshness-max-age-ms",
        type=float,
        default=500.0,
        help="Maximum input age considered fresh.",
    )
    parser.add_argument(
        "--anchor",
        default="256,256",
        help="Heuristic goal anchor 'x,y' in dataset pixel coordinates.",
    )
    parser.add_argument(
        "--gain",
        type=float,
        default=0.6,
        help="Heuristic proportional gain toward the anchor (0..1).",
    )
    parser.add_argument(
        "--max-step",
        type=float,
        default=60.0,
        help="Heuristic maximum proposed step magnitude in pixels.",
    )
    parser.add_argument("--bc-memory", type=Path, default=None, help="bc_knn training memory JSON (from build_bc_memory.py).")
    parser.add_argument("--bc-k", type=int, default=5, help="bc_knn number of nearest demonstrations.")
    parser.add_argument("--neural-weights", type=Path, default=None, help="neural_bc weights JSON (from train_bc_mlp.py).")
    parser.add_argument("--device", default="cpu", help="neural_bc inference device (cpu keeps results deterministic).")
    parser.add_argument("--claude-model", default="claude-haiku-4-5-20251001", help="Claude model id.")
    parser.add_argument("--max-actions", type=int, default=None, help="Cap proposed actions.")
    return parser.parse_args(argv)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
    return events


def event_time_ns(event: dict[str, Any]) -> int:
    value = event.get("event_time_ns")
    if isinstance(value, int):
        return value
    replay = event.get("replay")
    if isinstance(replay, dict) and isinstance(replay.get("original_event_time_ns"), int):
        return replay["original_event_time_ns"]
    return time.time_ns()


def clock_domain(event: dict[str, Any]) -> str:
    value = event.get("clock_domain")
    return value if isinstance(value, str) else "unknown"


def agent_position(event: dict[str, Any]) -> dict[str, float] | None:
    payload = event.get("payload_summary")
    if not isinstance(payload, dict):
        return None
    position = payload.get("position")
    if not isinstance(position, dict):
        return None
    try:
        return {"x": float(position.get("x", 0.0)), "y": float(position.get("y", 0.0))}
    except (TypeError, ValueError):
        return None


def freshness_report(
    *, latest: dict[str, dict[str, Any]], current_time_ns: int, required: list[str], max_age_ms: float
) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for stream_id, sample in sorted(latest.items()):
        age_ms = (current_time_ns - event_time_ns(sample)) / 1_000_000.0
        if age_ms < 0:
            status = "future"
        elif age_ms <= max_age_ms:
            status = "ok"
        else:
            status = "stale"
        report[stream_id] = {"age_ms": abs(age_ms), "status": status, "required": stream_id in required}
    for stream_id in required:
        if stream_id not in report:
            report[stream_id] = {"age_ms": None, "status": "missing", "required": True}
    return report


def required_ready(freshness: dict[str, dict[str, Any]], required: list[str]) -> bool:
    return all(freshness.get(s, {}).get("status") in {"ok", "future", "fresh"} for s in required)


def clamp_step(dx: float, dy: float, max_step: float) -> tuple[float, float]:
    magnitude = (dx * dx + dy * dy) ** 0.5
    if magnitude <= max_step or magnitude == 0.0:
        return dx, dy
    scale = max_step / magnitude
    return dx * scale, dy * scale


class HeuristicBackend:
    """Deterministic proportional go-to-anchor baseline."""

    policy_id = "romi_heuristic_goto"

    def __init__(self, *, anchor: tuple[float, float], gain: float, max_step: float) -> None:
        self.anchor = anchor
        self.gain = gain
        self.max_step = max_step

    def propose(self, *, position: dict[str, float], history: list[dict[str, float]]) -> dict[str, float]:
        dx = self.gain * (self.anchor[0] - position["x"])
        dy = self.gain * (self.anchor[1] - position["y"])
        dx, dy = clamp_step(dx, dy, self.max_step)
        return {"x": position["x"] + dx, "y": position["y"] + dy}


class BCKnnBackend:
    """Non-parametric behavior-cloning policy over demonstrated (state, action) pairs.

    For the current agent state it proposes a distance-weighted average of the
    actions taken in the k nearest demonstrated states. Learned purely from data,
    deterministic, and needs only numpy - no torch, GPU, or API key.
    """

    policy_id = "romi_bc_knn"

    def __init__(self, *, memory_path: Path, k: int) -> None:
        try:
            import numpy as np  # local import: optional dependency
        except ImportError as exc:
            raise RuntimeError("The bc_knn backend needs numpy: pip install numpy") from exc
        if memory_path is None or not memory_path.exists():
            raise RuntimeError(
                "The bc_knn backend needs --bc-memory pointing to a memory JSON "
                "(build one with tools/vla_policy/build_bc_memory.py)."
            )
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
        self.np = np
        self.states = np.asarray(memory["states"], dtype=float)
        self.actions = np.asarray(memory["actions"], dtype=float)
        if self.states.shape[0] == 0:
            raise RuntimeError("bc_knn memory is empty.")
        self.k = max(1, min(k, self.states.shape[0]))

    def propose(self, *, position: dict[str, float], history: list[dict[str, float]]) -> dict[str, float]:
        np = self.np
        query = np.array([position["x"], position["y"]], dtype=float)
        distances = np.linalg.norm(self.states - query, axis=1)
        nearest = np.argpartition(distances, self.k - 1)[: self.k]
        weights = 1.0 / (distances[nearest] + 1e-6)
        goal = np.average(self.actions[nearest], axis=0, weights=weights)
        return {"x": float(goal[0]), "y": float(goal[1])}


class NeuralBCBackend:
    """A GPU-trained neural behavior-cloning policy (MLP) run for inference.

    Loads weights produced by train_bc_mlp.py and maps the agent state to a
    proposed action through a small MLP. Inference defaults to CPU so results are
    deterministic and reproducible regardless of GPU availability.
    """

    policy_id = "romi_neural_bc"

    def __init__(self, *, weights_path: Path, device: str) -> None:
        try:
            import torch  # local import: optional dependency
        except ImportError as exc:
            raise RuntimeError("The neural_bc backend needs torch: pip install torch") from exc
        if weights_path is None or not weights_path.exists():
            raise RuntimeError(
                "The neural_bc backend needs --neural-weights pointing to a weights JSON "
                "(train one with tools/vla_policy/train_bc_mlp.py)."
            )
        weights = json.loads(weights_path.read_text(encoding="utf-8"))
        arch = weights["arch"]
        self.torch = torch
        self.device = torch.device(device)

        import torch.nn as nn

        self.model = nn.Sequential(
            nn.Linear(arch["in_dim"], arch["hidden"]), nn.ReLU(),
            nn.Linear(arch["hidden"], arch["hidden"]), nn.ReLU(),
            nn.Linear(arch["hidden"], arch["out_dim"]),
        )
        state_dict = {name: torch.tensor(value, dtype=torch.float32) for name, value in weights["state_dict"].items()}
        self.model.load_state_dict(state_dict)
        self.model.to(self.device).eval()
        norm = weights["norm"]
        self.state_mean = torch.tensor(norm["state_mean"], dtype=torch.float32, device=self.device)
        self.state_std = torch.tensor(norm["state_std"], dtype=torch.float32, device=self.device)
        self.action_mean = torch.tensor(norm["action_mean"], dtype=torch.float32, device=self.device)
        self.action_std = torch.tensor(norm["action_std"], dtype=torch.float32, device=self.device)

    def propose(self, *, position: dict[str, float], history: list[dict[str, float]]) -> dict[str, float]:
        torch = self.torch
        with torch.no_grad():
            state = torch.tensor([position["x"], position["y"]], dtype=torch.float32, device=self.device)
            normalized = (state - self.state_mean) / self.state_std
            output = self.model(normalized.unsqueeze(0)).squeeze(0)
            goal = output * self.action_std + self.action_mean
        return {"x": float(goal[0]), "y": float(goal[1])}


class ClaudeBackend:
    """Real-reasoning policy backed by the Anthropic SDK."""

    policy_id = "romi_claude_policy"

    SYSTEM = (
        "You are a non-authoritative motion policy for a 2D pushing task. "
        "The workspace is pixel coordinates in roughly [0,512]x[0,512]. "
        "Given the agent's recent positions and the task, propose the next target "
        "position for the agent to move toward. You never command actuators; you only "
        "propose. Respond with a single minified JSON object: {\"x\": <float>, \"y\": <float>}. "
        "No prose, no code fences."
    )

    def __init__(self, *, model: str, task: str | None) -> None:
        try:
            import anthropic  # local import: optional dependency
        except ImportError as exc:
            raise RuntimeError(
                "The claude backend needs the anthropic package: pip install anthropic"
            ) from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "The claude backend needs ANTHROPIC_API_KEY in the environment."
            )
        self.client = anthropic.Anthropic()
        self.model = model
        self.task = task or "Push the object to its target."

    def propose(self, *, position: dict[str, float], history: list[dict[str, float]]) -> dict[str, float]:
        recent = history[-8:]
        trail = ", ".join(f"({p['x']:.0f},{p['y']:.0f})" for p in recent)
        user = (
            f"Task: {self.task}\n"
            f"Recent agent positions (oldest first): [{trail}]\n"
            f"Current agent position: ({position['x']:.1f}, {position['y']:.1f})\n"
            "Propose the next target position."
        )
        message = self.client.messages.create(
            model=self.model,
            max_tokens=64,
            system=[{"type": "text", "text": self.SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in message.content if block.type == "text").strip()
        try:
            parsed = json.loads(text)
            return {"x": float(parsed["x"]), "y": float(parsed["y"])}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Degrade safely: hold position rather than emit a malformed proposal.
            return {"x": position["x"], "y": position["y"]}


def build_backend(args: argparse.Namespace, task: str | None) -> Any:
    if args.backend == "heuristic":
        ax, ay = (float(v) for v in args.anchor.split(","))
        return HeuristicBackend(anchor=(ax, ay), gain=args.gain, max_step=args.max_step)
    if args.backend == "bc_knn":
        return BCKnnBackend(memory_path=args.bc_memory, k=args.bc_k)
    if args.backend == "neural_bc":
        return NeuralBCBackend(weights_path=args.neural_weights, device=args.device)
    return ClaudeBackend(model=args.claude_model, task=task)


def policy_sample(
    *,
    policy_id: str,
    backend_kind: str,
    goal: dict[str, float],
    trigger: dict[str, Any],
    latest: dict[str, dict[str, Any]],
    required: list[str],
    max_age_ms: float,
    sequence_index: int,
    inference_latency_ms: float,
) -> dict[str, Any]:
    current_time_ns = event_time_ns(trigger)
    freshness = freshness_report(
        latest=latest, current_time_ns=current_time_ns, required=required, max_age_ms=max_age_ms
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "proposed_action",
        "policy_id": policy_id,
        "time": {"event_time_ns": current_time_ns, "clock_domain": clock_domain(trigger)},
        "input_streams": sorted(latest.keys()),
        "freshness": freshness,
        "proposed_actions": [
            {
                "target": "base",
                "action_type": "navigate_to_goal",
                "values": {
                    "goal_position": {"x": goal["x"], "y": goal["y"]},
                    "mode": f"lerobot_eval_{backend_kind}",
                },
                "authority": "proposed_only",
            }
        ],
        "safety_boundary": {
            "policy_authority": "proposed_only",
            "actuator_authority": "none",
            "command_stream_emitted": False,
            "blocked_reason": "proposal_not_actuator_authority",
        },
        "inference_latency_ms": inference_latency_ms,
        "metadata": {
            "authority": "proposed_only",
            "trigger_stream": trigger.get("stream_id"),
            "sequence_index": sequence_index,
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_id": POLICY_SCHEMA_ID,
        "kind": "stream_sample",
        "stream_id": "policy.proposed_action",
        "semantic_type": "command",
        "source_system": "romi",
        "source_topic": None,
        "source_message_type": "romi/ml/PolicyProposedAction",
        "event_time_ns": current_time_ns,
        "policy_emit_wall_time_ns": time.time_ns(),
        "clock_domain": clock_domain(trigger),
        "frame_id": trigger.get("frame_id"),
        "payload_summary": payload,
        "metadata": {
            "policy_id": policy_id,
            "trigger_stream": trigger.get("stream_id"),
            "authority": "proposed_only",
            "sequence_index": sequence_index,
        },
    }


def find_task(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("stream_id") == "task.goal":
            payload = event.get("payload_summary")
            if isinstance(payload, dict):
                text = payload.get("task_text")
                if isinstance(text, str):
                    return text
    return None


def run_policy(args: argparse.Namespace) -> int:
    if not args.input.exists():
        raise FileNotFoundError(f"Input JSONL does not exist: {args.input}")

    trigger_streams = set(args.trigger_stream or [DEFAULT_TRIGGER])
    required_streams = args.required_stream or [DEFAULT_REQUIRED]

    events = load_jsonl(args.input)
    backend = build_backend(args, find_task(events))
    policy_id = args.policy_id or backend.policy_id

    writer = JsonlWriter(args.output)
    latest: dict[str, dict[str, Any]] = {}
    history: list[dict[str, float]] = []
    emitted = 0

    try:
        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "policy_start",
                "policy_id": policy_id,
                "backend": args.backend,
                "input": str(args.input),
                "trigger_streams": sorted(trigger_streams),
                "required_streams": required_streams,
                "freshness_max_age_ms": args.freshness_max_age_ms,
                "wall_time_ns": time.time_ns(),
            }
        )

        for event in events:
            if event.get("kind") != "stream_sample":
                continue
            stream_id = event.get("stream_id")
            if not isinstance(stream_id, str):
                continue
            latest[stream_id] = event
            if stream_id not in trigger_streams:
                continue

            now_ns = event_time_ns(event)
            freshness = freshness_report(
                latest=latest, current_time_ns=now_ns, required=required_streams, max_age_ms=args.freshness_max_age_ms
            )
            if not required_ready(freshness, required_streams):
                continue

            position = agent_position(event)
            if position is None:
                continue

            start_ns = time.perf_counter_ns()
            goal = backend.propose(position=position, history=history)
            inference_latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
            history.append(position)

            writer.write(
                policy_sample(
                    policy_id=policy_id,
                    backend_kind=args.backend,
                    goal=goal,
                    trigger=event,
                    latest=latest,
                    required=required_streams,
                    max_age_ms=args.freshness_max_age_ms,
                    sequence_index=emitted,
                    inference_latency_ms=inference_latency_ms,
                )
            )
            emitted += 1
            if args.max_actions is not None and emitted >= args.max_actions:
                break

        writer.write(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "policy_stop",
                "policy_id": policy_id,
                "backend": args.backend,
                "emitted_actions": emitted,
                "observed_streams": sorted(latest.keys()),
                "wall_time_ns": time.time_ns(),
            }
        )
    finally:
        writer.close()

    print(f"{policy_id} ({args.backend}) emitted {emitted} proposals", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run_policy(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
