#!/usr/bin/env python3
"""Validate committed sample artifacts against RoMi draft schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def robotics_payload_schema_paths(repo_root: Path) -> dict[str, Path]:
    robotics = repo_root / "schemas" / "robotics"
    return {
        "robot.camera.rgb": robotics / "image_summary.schema.json",
        "robot.camera.depth": robotics / "image_summary.schema.json",
        "robot.camera.info": robotics / "camera_info_summary.schema.json",
        "robot.joints.state": robotics / "joint_state_summary.schema.json",
        "robot.base.odom": robotics / "odometry_summary.schema.json",
        "robot.frames.tf": robotics / "transform_tree_summary.schema.json",
        "task.goal": robotics / "task_goal_summary.schema.json",
    }


def type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return (isinstance(value, int | float) and not isinstance(value, bool))
    if expected_type == "integer":
        return (isinstance(value, int) and not isinstance(value, bool))
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    raise AssertionError(f"unsupported schema type: {expected_type}")


def validate_schema(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        require(type_matches(value, schema_type), f"{path} expected {schema_type}, got {type(value).__name__}")
    elif isinstance(schema_type, list):
        require(
            any(type_matches(value, expected) for expected in schema_type),
            f"{path} expected one of {schema_type}, got {type(value).__name__}",
        )

    if "const" in schema:
        require(value == schema["const"], f"{path} expected const {schema['const']!r}, got {value!r}")

    if "enum" in schema:
        require(value in schema["enum"], f"{path} expected one of {schema['enum']!r}, got {value!r}")

    if "minimum" in schema and isinstance(value, int | float) and not isinstance(value, bool):
        require(value >= schema["minimum"], f"{path} expected >= {schema['minimum']}, got {value}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            require(key in value, f"{path} missing required property {key!r}")

        properties = schema.get("properties", {})
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in properties:
                validate_schema(child, properties[key], child_path)
                continue
            additional = schema.get("additionalProperties", True)
            if isinstance(additional, dict):
                validate_schema(child, additional, child_path)
            else:
                require(additional is not False, f"{child_path} is not allowed")

    if isinstance(value, list) and "items" in schema:
        if "minItems" in schema:
            require(len(value) >= schema["minItems"], f"{path} expected at least {schema['minItems']} items, got {len(value)}")
        if "maxItems" in schema:
            require(len(value) <= schema["maxItems"], f"{path} expected at most {schema['maxItems']} items, got {len(value)}")
        for index, item in enumerate(value):
            validate_schema(item, schema["items"], f"{path}[{index}]")


def validate_policy_compare(report: dict[str, Any]) -> None:
    require(len(report["policies"]) == 2, "policy compare should include two policies")
    require(
        {policy["role"] for policy in report["policies"]} == {"baseline", "counterfactual"},
        "policy compare policy roles mismatch",
    )
    require(
        report["observation_window"]["fresh_inputs"] <= report["observation_window"]["required_inputs"],
        "policy compare fresh inputs exceed required inputs",
    )
    require(
        report["observation_window"]["required_inputs"] == len(report["observation_window"]["streams"]),
        "policy compare required input count must match stream count",
    )
    require(len(report["diffs"]) > 0, "policy compare should include diffs")
    require(any(diff["changed"] for diff in report["diffs"]), "policy compare should include changed actions")
    validate_runtime_graph(report["runtime_graph"], expected_output="policy_compare.json")


def validate_evaluation_timeline(report: dict[str, Any]) -> None:
    require(report["sample_count"] == len(report["samples"]), "timeline sample_count mismatch")
    require(report["sample_count"] > 0, "timeline should include samples")
    require(any(sample["changed_actions"] > 0 for sample in report["samples"]), "timeline should include changed samples")
    require(
        all(sample["fresh_inputs"] <= sample["required_inputs"] for sample in report["samples"]),
        "timeline fresh inputs exceed required inputs",
    )

    stage_sample_counts: dict[str, int] = {}
    stage_changed_counts: dict[str, int] = {}
    for sample in report["samples"]:
        stage = sample["stage"]
        stage_sample_counts[stage] = stage_sample_counts.get(stage, 0) + 1
        if sample["changed_actions"] > 0:
            stage_changed_counts[stage] = stage_changed_counts.get(stage, 0) + 1

    for stage in report["stage_summary"]:
        stage_name = stage["stage"]
        require(stage["samples"] == stage_sample_counts.get(stage_name, 0), f"timeline stage sample mismatch: {stage_name}")
        require(
            stage["changed_action_samples"] == stage_changed_counts.get(stage_name, 0),
            f"timeline changed sample mismatch: {stage_name}",
        )

    validate_runtime_graph(report["runtime_graph"], expected_output="evaluation_timeline.json")


def validate_dataset_report(report: dict[str, Any]) -> None:
    require(report["episode"]["episode_id"] == "nav_manip_demo_sample", "dataset report episode id mismatch")
    require(report["generated_at_unix_ns"] == 0, "dataset report committed sample timestamp should be normalized")
    require(report["episode_dir"] == "examples/navigation_manipulation_demo/sample_output/dataset-report", "dataset report episode dir should be normalized")
    require(report["diagnostics"]["event_count"] > 0, "dataset report should include diagnostics")
    require(report["policy"]["sample_count"] > 0, "dataset report should include policy samples")
    require(len(report["streams"]) >= 7, "dataset report missing required stream summaries")
    window = report["observation_window"]
    window_streams = window["streams"]
    require(len(window_streams) >= 7, "dataset report missing observation window streams")
    require(window["window_start_time_ns"] <= window["target_time_ns"] <= window["window_end_time_ns"], "dataset report observation window bounds mismatch")
    require(window["required_stream_count"] == len(window_streams), "dataset report required stream count mismatch")
    require(window["available_stream_count"] == sum(1 for stream in window_streams if stream["status"] == "ok"), "dataset report available stream count mismatch")
    require(window["missing_stream_count"] == sum(1 for stream in window_streams if stream["status"] == "missing_in_window"), "dataset report missing stream count mismatch")

    repo_root = Path(__file__).resolve().parents[1]
    payload_schemas = {stream_id: load_json(path) for stream_id, path in robotics_payload_schema_paths(repo_root).items()}
    for stream in window_streams:
        stream_id = stream["stream_id"]
        schema = payload_schemas.get(stream_id)
        if schema is None:
            continue
        require(stream["payload_schema_id"] == schema["$id"], f"dataset report payload schema id mismatch: {stream_id}")
        if stream["status"] == "ok":
            require(stream["payload_summary"] is not None, f"dataset report payload missing: {stream_id}")
            validate_schema(stream["payload_summary"], schema, f"dataset_report.observation_window.{stream_id}.payload_summary")
            require(stream["event_time_ns"] is not None, f"dataset report event time missing: {stream_id}")
            require(stream["frame_id"] is not None, f"dataset report frame id missing: {stream_id}")
            require(stream["sample_index"] is not None, f"dataset report sample index missing: {stream_id}")
            require(stream["delta_abs_ms"] == abs(stream["delta_ms"]), f"dataset report delta_abs_ms mismatch: {stream_id}")
        else:
            require(stream["payload_summary"] is None, f"dataset report missing stream should not include payload: {stream_id}")
            require(stream["event_time_ns"] is None, f"dataset report missing stream should not include event time: {stream_id}")
    require(
        all(action["authority"] == "proposed_only" for action in report["policy"]["actions"]),
        "dataset report policy actions must remain proposed_only",
    )


def validate_safety_authority(report: dict[str, Any]) -> None:
    require(report["policy_authority"] == "proposed_only", "safety report policy authority mismatch")
    require(report["actuator_authority"] == "none", "safety report actuator authority mismatch")
    require(report["command_stream_emitted"] is False, "safety report command stream boundary mismatch")
    require(report["policy_samples"] > 0, "safety report should include policy samples")
    require(report["proposed_actions"], "safety report should include proposed actions")
    require(all(action["blocked"] is True for action in report["proposed_actions"]), "safety report actions should be blocked")
    require(
        all(action["authority"] == "proposed_only" for action in report["proposed_actions"]),
        "safety report actions must remain proposed_only",
    )


def validate_report_manifest(manifest: dict[str, Any], sample_dir: Path) -> None:
    artifacts = manifest["artifacts"]
    require(len(artifacts) == 4, "report manifest should include four report artifacts")
    artifact_ids = {artifact["artifact_id"] for artifact in artifacts}
    require(
        artifact_ids == {"dataset_report", "policy_compare", "evaluation_timeline", "safety_authority"},
        "report manifest artifact ids mismatch",
    )
    for artifact in artifacts:
        json_path = sample_dir / artifact["json_path"]
        require(json_path.exists(), f"report manifest JSON path does not exist: {artifact['json_path']}")
        markdown_path = artifact.get("markdown_path")
        if markdown_path is not None:
            require((sample_dir / markdown_path).exists(), f"report manifest markdown path does not exist: {markdown_path}")
        if "authority_boundary" in artifact:
            boundary = artifact["authority_boundary"]
            require(boundary["policy_authority"] == "proposed_only", "report manifest policy authority mismatch")
            require(boundary["actuator_authority"] == "none", "report manifest actuator authority mismatch")
            require(boundary["command_stream_emitted"] is False, "report manifest command boundary mismatch")


def validate_runtime_graph(graph: dict[str, Any], *, expected_output: str) -> None:
    node_ids = {node["node_id"] for node in graph["nodes"]}
    required_nodes = {"source", "record", "replay", "policy", "evaluation", "safety"}
    require(required_nodes.issubset(node_ids), f"runtime graph missing nodes: {sorted(required_nodes - node_ids)}")
    require(graph["active_path"] == ["source", "record", "replay", "policy", "evaluation", "safety"], "runtime graph active path mismatch")
    require(graph["authority_boundary"]["policy_authority"] == "proposed_only", "runtime graph policy authority mismatch")
    require(graph["authority_boundary"]["actuator_authority"] == "none", "runtime graph actuator authority mismatch")
    require(graph["authority_boundary"]["command_stream_emitted"] is False, "runtime graph command boundary mismatch")

    evaluation_nodes = [node for node in graph["nodes"] if node["node_id"] == "evaluation"]
    require(len(evaluation_nodes) == 1, "runtime graph should include exactly one evaluation node")
    require(expected_output in evaluation_nodes[0]["outputs"], f"runtime graph evaluation output missing {expected_output}")

    policy_nodes = [node for node in graph["nodes"] if node["node_id"] == "policy"]
    require(len(policy_nodes) == 1, "runtime graph should include exactly one policy node")
    require(policy_nodes[0]["authority"] == "proposed_only", "runtime graph policy node authority mismatch")

    safety_nodes = [node for node in graph["nodes"] if node["node_id"] == "safety"]
    require(len(safety_nodes) == 1, "runtime graph should include exactly one safety node")
    require(safety_nodes[0]["authority"] == "none", "runtime graph safety node authority mismatch")


def check_samples(repo_root: Path) -> None:
    sample_dir = repo_root / "examples" / "navigation_manipulation_demo" / "sample_output"
    checks = [
        (
            sample_dir / "policy_compare.json",
            repo_root / "schemas" / "ml" / "policy_compare.schema.json",
            validate_policy_compare,
        ),
        (
            sample_dir / "evaluation_timeline.json",
            repo_root / "schemas" / "ml" / "evaluation_timeline.schema.json",
            validate_evaluation_timeline,
        ),
        (
            sample_dir / "dataset-report" / "report.json",
            repo_root / "schemas" / "core" / "dataset_report.schema.json",
            validate_dataset_report,
        ),
        (
            sample_dir / "safety_authority.json",
            repo_root / "schemas" / "core" / "safety_authority.schema.json",
            validate_safety_authority,
        ),
    ]

    for artifact_path, schema_path, semantic_check in checks:
        artifact = load_json(artifact_path)
        schema = load_json(schema_path)
        validate_schema(artifact, schema)
        semantic_check(artifact)

    manifest_path = sample_dir / "report_manifest.json"
    manifest = load_json(manifest_path)
    manifest_schema = load_json(repo_root / "schemas" / "core" / "report_manifest.schema.json")
    validate_schema(manifest, manifest_schema)
    validate_report_manifest(manifest, sample_dir)

    print(
        json.dumps(
            {
                "validated_artifacts": [str(path.relative_to(repo_root)) for path, _, _ in checks] + [str(manifest_path.relative_to(repo_root))],
                "schema_count": len(checks) + 1,
            },
            sort_keys=True,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    check_samples(args.repo_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
