#!/usr/bin/env python3
"""Compare browser simulator events against the RoMi-native source contract."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def default_contract_path(repo_root: Path) -> Path:
    return repo_root / "examples" / "navigation_manipulation_demo" / "contract.example.json"


def required_stream_ids(contract: dict[str, Any]) -> list[str]:
    return [stream["stream_id"] for stream in contract["required_streams"]]


def stream_contract(contract: dict[str, Any], stream_id: str) -> dict[str, Any]:
    for stream in contract["required_streams"]:
        if stream["stream_id"] == stream_id:
            return stream
    raise AssertionError(f"missing stream contract: {stream_id}")


def load_capture_helpers(repo_root: Path) -> Any:
    helper_path = repo_root / "examples" / "navigation_manipulation_demo" / "capture_readme_video.py"
    spec = importlib.util.spec_from_file_location("romi_capture_readme_video", helper_path)
    require(spec is not None and spec.loader is not None, f"unable to load {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_stream_at_or_before(events: list[dict[str, Any]], stream_id: str, event_time_ns: int) -> dict[str, Any]:
    candidates = [
        event
        for event in events
        if event.get("kind") == "stream_sample"
        and event.get("stream_id") == stream_id
        and int(event.get("event_time_ns", -1)) <= event_time_ns
    ]
    require(candidates, f"missing native stream at or before {event_time_ns}: {stream_id}")
    return max(candidates, key=lambda event: int(event.get("event_time_ns", -1)))


def run_native_source(repo_root: Path, output: Path) -> list[dict[str, Any]]:
    script = repo_root / "examples" / "navigation_manipulation_demo" / "romi_native_sim_source.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--output",
            str(output),
            "--duration-sec",
            "16",
            "--rate-hz",
            "12",
        ],
        check=True,
    )
    return iter_jsonl(output)


def terminate(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def start_browser(repo_root: Path, chrome_bin: str, helpers: Any) -> tuple[Any, str, subprocess.Popen[bytes], subprocess.Popen[bytes], tempfile.TemporaryDirectory[str]]:
    example_dir = repo_root / "examples" / "navigation_manipulation_demo"
    server_port = helpers.free_port()
    debug_port = helpers.free_port()
    url = f"http://127.0.0.1:{server_port}/romi_2d_sim/?capture=readme"
    cdp = None

    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(server_port), "--bind", "127.0.0.1", "--directory", str(example_dir)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    chrome_profile = tempfile.TemporaryDirectory(prefix="romi-contract-chrome-")
    chrome = subprocess.Popen(
        [
            chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={chrome_profile.name}",
            "--window-size=1280,800",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        helpers.wait_for_http(url)
        version = helpers.wait_for_json(f"http://127.0.0.1:{debug_port}/json/version")
        cdp = helpers.CdpClient(version["webSocketDebuggerUrl"])
        target = cdp.send("Target.createTarget", {"url": "about:blank"})
        session_id = cdp.send("Target.attachToTarget", {"targetId": target["targetId"], "flatten": True})["sessionId"]

        cdp.send("Page.enable", session_id=session_id)
        cdp.send("Runtime.enable", session_id=session_id)
        cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False},
            session_id=session_id,
        )
        cdp.send("Page.navigate", {"url": url}, session_id=session_id)

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = cdp.send(
                "Runtime.evaluate",
                {"expression": "Boolean(window.romiCapture && window.romiCapture.ready())", "returnByValue": True},
                session_id=session_id,
            )
            if result.get("result", {}).get("value") is True:
                return cdp, session_id, server, chrome, chrome_profile
            time.sleep(0.1)

        raise TimeoutError("RoMi browser simulator did not become ready")
    except Exception:
        if cdp is not None:
            cdp.close()
        terminate(chrome)
        terminate(server)
        chrome_profile.cleanup()
        raise


def browser_snapshot(cdp: Any, session_id: str, sim_time_sec: float, contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    streams_js = json.dumps([*required_stream_ids(contract), contract["policy"]["stream_id"]])
    expression = f"""
      window.romiCapture.seek({sim_time_sec:.6f});
      JSON.stringify(Object.fromEntries({streams_js}.map((streamId) => [
        streamId,
        window.romiCapture.latestEvent(streamId)
      ])));
    """
    result = cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
    )
    return json.loads(result["result"]["value"])


def check_common_event_contract(browser_event: dict[str, Any], native_event: dict[str, Any], stream_id: str, contract: dict[str, Any]) -> None:
    stream = stream_contract(contract, stream_id)
    require(browser_event is not None, f"browser missing {stream_id}")
    require(browser_event.get("kind") == "stream_sample", f"browser {stream_id} must be a stream_sample")
    require(browser_event.get("stream_id") == stream_id, f"browser stream id mismatch: {stream_id}")
    require(browser_event.get("semantic_type") == native_event.get("semantic_type") == stream["semantic_type"], f"semantic_type mismatch for {stream_id}")
    require(browser_event.get("frame_id") == native_event.get("frame_id") == stream["frame_id"], f"frame_id mismatch for {stream_id}")
    require(
        browser_event.get("source_message_type") == native_event.get("source_message_type") == stream["source_message_type"],
        f"source_message_type mismatch for {stream_id}",
    )
    expected_clock = contract["source_invariants"]["clock_domain"]
    require(browser_event.get("clock_domain") == native_event.get("clock_domain") == expected_clock, f"clock_domain mismatch for {stream_id}")
    require(browser_event.get("metadata", {}).get("scenario_id") == native_event.get("metadata", {}).get("scenario_id") == contract["scenario_id"], f"scenario_id mismatch for {stream_id}")
    require(browser_event.get("metadata", {}).get("robot_morphology") == native_event.get("metadata", {}).get("robot_morphology") == contract["robot"]["morphology"], f"robot_morphology mismatch for {stream_id}")
    expected_authority = contract["source_invariants"]["observation_authority"]
    require(browser_event.get("metadata", {}).get("authority") == expected_authority, f"browser authority mismatch for {stream_id}")
    require(native_event.get("metadata", {}).get("authority") == expected_authority, f"native authority mismatch for {stream_id}")


def check_image_payload(browser_payload: dict[str, Any], native_payload: dict[str, Any], channels: int, stream_id: str) -> None:
    for key in ["height", "width", "encoding", "step", "data_len"]:
        require(browser_payload.get(key) == native_payload.get(key), f"{stream_id} payload {key} mismatch")
    require(browser_payload["data_len"] == browser_payload["height"] * browser_payload["width"] * channels, f"{stream_id} data_len mismatch")
    require("synthetic_scene" in browser_payload, f"{stream_id} missing synthetic_scene")


def check_stream_payload(browser_event: dict[str, Any], native_event: dict[str, Any], stream_id: str, contract: dict[str, Any]) -> None:
    stream = stream_contract(contract, stream_id)
    invariants = stream.get("payload_invariants", {})
    browser_payload = browser_event.get("payload_summary") or {}
    native_payload = native_event.get("payload_summary") or {}

    if stream_id == "robot.camera.rgb":
        check_image_payload(browser_payload, native_payload, invariants["channels"], stream_id)
        require(browser_payload.get("encoding") == invariants["encoding"], "browser RGB encoding mismatch")
        for field in invariants["required_synthetic_scene_fields"]:
            require(field in browser_payload.get("synthetic_scene", {}), f"browser RGB missing {field}")
    elif stream_id == "robot.camera.depth":
        check_image_payload(browser_payload, native_payload, invariants["channels"], stream_id)
        require(browser_payload.get("encoding") == invariants["encoding"], "browser depth encoding mismatch")
        for field in invariants["required_synthetic_scene_fields"]:
            require(field in browser_payload.get("synthetic_scene", {}), f"browser depth missing {field}")
    elif stream_id == "robot.camera.info":
        for key in ["height", "width", "distortion_model", "d_len", "k_len", "p_len"]:
            require(browser_payload.get(key) == native_payload.get(key), f"camera.info {key} mismatch")
        for key, expected in invariants.items():
            require(browser_payload.get(key) == expected, f"camera.info {key} contract mismatch")
    elif stream_id == "robot.joints.state":
        joint_contract = contract["robot"]["joint_state"]
        require(browser_payload.get("joint_count") == native_payload.get("joint_count") == joint_contract["joint_count"], "joint_count mismatch")
        require(browser_payload.get("joint_names_sample") == native_payload.get("joint_names_sample") == joint_contract["joint_names"], "joint names mismatch")
        for key in ["position_count", "velocity_count", "effort_count"]:
            require(browser_payload.get(key) == native_payload.get(key) == joint_contract[key], f"joint {key} mismatch")
        require(len(browser_payload.get("position_sample", [])) == joint_contract["position_count"], "browser position_sample length mismatch")
    elif stream_id == "robot.base.odom":
        require(browser_payload.get("child_frame_id") == native_payload.get("child_frame_id") == invariants["child_frame_id"], "odom child_frame_id mismatch")
        require("position" in browser_payload, "browser odom missing position")
        require("orientation" in browser_payload, "browser odom missing orientation")
    elif stream_id == "robot.frames.tf":
        require(browser_payload.get("transform_count") == native_payload.get("transform_count") == invariants["transform_count"], "TF transform_count mismatch")
        browser_frames = browser_payload.get("frames_sample", [])
        native_frames = native_payload.get("frames_sample", [])
        browser_pairs = [(frame.get("parent_frame_id"), frame.get("child_frame_id")) for frame in browser_frames]
        native_pairs = [(frame.get("parent_frame_id"), frame.get("child_frame_id")) for frame in native_frames]
        expected_pairs = [tuple(pair) for pair in invariants["frame_pairs"]]
        require(browser_pairs == native_pairs == expected_pairs, "TF frame pairs mismatch")
        require(all("stamp_ns" in frame for frame in browser_frames), "browser TF frames missing stamp_ns")
        for field in invariants["required_fields"]:
            require(field in browser_payload, f"browser TF missing {field}")
    elif stream_id == "task.goal":
        require(browser_payload.get("scenario_id") == native_payload.get("scenario_id"), "task.goal scenario_id mismatch")
        require(browser_payload.get("target_object") == native_payload.get("target_object") == invariants["target_object"], "task.goal target_object mismatch")


def check_policy_event(browser_event: dict[str, Any], contract: dict[str, Any]) -> None:
    policy_contract = contract["policy"]
    require(browser_event is not None, "browser missing policy.proposed_action")
    require(browser_event.get("stream_id") == policy_contract["stream_id"], "browser policy stream mismatch")
    require(browser_event.get("semantic_type") == policy_contract["semantic_type"], "browser policy semantic_type mismatch")
    require(browser_event.get("metadata", {}).get("authority") == policy_contract["authority"], "browser policy metadata authority mismatch")
    payload = browser_event.get("payload_summary") or {}
    require(payload.get("metadata", {}).get("authority") == policy_contract["authority"], "browser policy payload authority mismatch")
    actions = payload.get("proposed_actions", [])
    require(len(actions) == policy_contract["proposed_action_count"], "browser policy proposed action count mismatch")
    require(all(action.get("authority") == policy_contract["authority"] for action in actions), "browser policy action authority mismatch")
    observation_window = payload.get("observation_window", [])
    require(len(observation_window) == 6, "browser policy observation window count mismatch")
    observation_streams = {entry.get("stream_id") for entry in observation_window}
    for stream_id in ["robot.camera.rgb", "robot.camera.depth", "robot.joints.state", "robot.base.odom", "robot.frames.tf", "task.goal"]:
        require(stream_id in observation_streams, f"browser policy observation window missing {stream_id}")
    require(all(entry.get("status") in {"fresh", "stale", "missing"} for entry in observation_window), "browser policy observation status mismatch")
    require(payload.get("input_status", {}).get("required") == 6, "browser policy input_status required count mismatch")
    safety_boundary = payload.get("safety_boundary", {})
    require(safety_boundary.get("policy_authority") == policy_contract["authority"], "browser policy safety boundary policy authority mismatch")
    require(safety_boundary.get("actuator_authority") == "none", "browser policy actuator authority mismatch")
    require(safety_boundary.get("command_stream_emitted") is False, "browser policy must not emit actuator command stream")
    require(safety_boundary.get("blocked_reason") == "proposal_not_actuator_authority", "browser policy safety blocked reason mismatch")


def check_studio_seek_controls(cdp: Any, session_id: str) -> None:
    expression = """
      (() => {
        window.romiCapture.seekToSeconds(2.0);
        const placeButton = document.querySelector('[data-seek-progress="0.8100"]');
        if (!placeButton) {
          return JSON.stringify({button_present: false});
        }
        placeButton.click();
        const afterButton = {
          stage: document.getElementById('stageValue').textContent,
          seek: document.getElementById('seekValue').textContent,
          status: document.getElementById('modeStatus').textContent,
        };
        const seek = document.getElementById('seekControl');
        seek.value = '930';
        seek.dispatchEvent(new Event('input', {bubbles: true}));
        return JSON.stringify({
          button_present: true,
          after_button: afterButton,
          after_slider: {
            stage: document.getElementById('stageValue').textContent,
            seek: document.getElementById('seekValue').textContent,
            range: Number(seek.value),
            status: document.getElementById('modeStatus').textContent,
          },
        });
      })();
    """
    result = cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
    )
    payload = json.loads(result["result"]["value"])
    require(payload.get("button_present") is True, "Studio timeline seek button missing")
    require(payload["after_button"]["stage"] == "place", "Studio timeline button did not seek to place stage")
    require(payload["after_button"]["seek"].startswith("12."), "Studio timeline button did not update seek readout")
    require(payload["after_slider"]["stage"] == "report", "Studio slider did not seek to report stage")
    require(payload["after_slider"]["range"] == 930, "Studio slider range did not preserve requested value")


def check_studio_event_inspector(cdp: Any, session_id: str) -> None:
    expression = """
      (() => {
        document.body.classList.remove('capture-mode');
        window.romiCapture.seekToSeconds(11.5);
        window.romiCapture.selectLatestStreamEvent('policy.proposed_action');
        const preview = document.getElementById('eventLog').textContent;
        const summary = document.getElementById('eventSummary').textContent;
        const status = document.getElementById('eventInspectorStatus').textContent;
        const selectedChip = document.querySelector('.event-chip.active');
        const firstChip = document.querySelector('[data-event-index]');
        if (firstChip) {
          firstChip.click();
        }
        return JSON.stringify({
          status,
          summary,
          preview,
          chip_count: document.querySelectorAll('[data-event-index]').length,
          selected_chip: selectedChip ? selectedChip.textContent : '',
          after_chip_preview: document.getElementById('eventLog').textContent,
          scroll_width: document.documentElement.scrollWidth,
          window_width: window.innerWidth,
        });
      })();
    """
    result = cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
    )
    payload = json.loads(result["result"]["value"])
    require(payload["chip_count"] > 0, "Studio event timeline did not render event chips")
    require(payload["status"] == "policy.proposed_action", "Studio event inspector did not select policy stream")
    require('"stream_id": "policy.proposed_action"' in payload["preview"], "Studio event inspector preview missing policy stream id")
    require('"authority": "proposed_only"' in payload["preview"], "Studio event inspector preview missing policy authority")
    require("policy.proposed_action" in payload["summary"], "Studio event inspector summary missing policy stream")
    require('"kind":' in payload["after_chip_preview"], "Studio event chip click did not show an event envelope")
    require(payload["scroll_width"] <= payload["window_width"], "Studio event inspector introduced horizontal page overflow")


def check_studio_dataset_report(cdp: Any, session_id: str) -> None:
    expression = """
      (() => {
        document.body.classList.remove('capture-mode');
        window.romiCapture.seekToSeconds(15.2);
        window.romiCapture.setMode('dataset');
        const report = window.romiCapture.datasetReport();
        const markdown = window.romiCapture.datasetReportMarkdown();
        return JSON.stringify({
          report,
          markdown,
          export_button_present: Boolean(document.querySelector('[data-export-dataset-report]')),
          preview: document.querySelector('.dataset-report-preview')?.textContent || '',
          scroll_width: document.documentElement.scrollWidth,
          window_width: window.innerWidth,
        });
      })();
    """
    result = cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
    )
    payload = json.loads(result["result"]["value"])
    report = payload["report"]
    require(report["report_kind"] == "romi.browser_dataset_report", "Studio dataset report kind mismatch")
    require(report["clock_domain"] == "sim_time", "Studio dataset report clock domain mismatch")
    require(report["samples"] > 0, "Studio dataset report missing samples")
    require(report["observation_window"]["available_streams"] >= 6, "Studio dataset report observation window incomplete")
    require(report["policy"]["authority"] == "proposed_only", "Studio dataset report policy authority mismatch")
    require(report["policy"]["actuator_authority"] == "none", "Studio dataset report actuator authority mismatch")
    require(report["stream_counts"]["robot.camera.rgb"] > 0, "Studio dataset report missing RGB count")
    require(report["stream_counts"]["policy.proposed_action"] > 0, "Studio dataset report missing policy count")
    require(payload["export_button_present"] is True, "Studio dataset report export button missing")
    require("RoMi Dataset Report" in payload["markdown"], "Studio dataset report markdown missing title")
    require("proposed_only" in payload["markdown"], "Studio dataset report markdown missing policy authority")
    require("robot.camera.rgb" in payload["preview"], "Studio dataset report preview missing stream counts")
    require(payload["scroll_width"] <= payload["window_width"], "Studio dataset report introduced horizontal page overflow")


def check_studio_policy_observation_window(cdp: Any, session_id: str) -> None:
    expression = """
      (() => {
        document.body.classList.remove('capture-mode');
        window.romiCapture.seekToSeconds(11.0);
        window.romiCapture.setMode('policy');
        const policy = window.romiCapture.latestEvent('policy.proposed_action');
        const observationWindow = policy?.payload_summary?.observation_window || [];
        const firstInput = document.querySelector('.policy-window-row[data-inspect-stream]');
        if (firstInput) {
          firstInput.click();
        }
        return JSON.stringify({
          observation_window: observationWindow,
          input_status: policy?.payload_summary?.input_status || {},
          window_text: document.querySelector('.policy-window')?.textContent || '',
          row_count: document.querySelectorAll('.policy-window-row[data-inspect-stream]').length,
          selected_event: document.getElementById('eventInspectorStatus').textContent,
          scroll_width: document.documentElement.scrollWidth,
          window_width: window.innerWidth,
        });
      })();
    """
    result = cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
    )
    payload = json.loads(result["result"]["value"])
    observation_window = payload["observation_window"]
    require(len(observation_window) == 6, "Studio policy observation window count mismatch")
    require(payload["input_status"].get("required") == 6, "Studio policy input_status required count mismatch")
    require(payload["input_status"].get("fresh", 0) >= 5, "Studio policy observation window should be mostly fresh")
    require(payload["row_count"] >= 3, "Studio policy observation window did not render rows")
    require("observation window" in payload["window_text"], "Studio policy observation window heading missing")
    require("camera.rgb" in payload["window_text"], "Studio policy observation window missing RGB input")
    require(payload["selected_event"] in {entry["stream_id"] for entry in observation_window}, "Studio policy observation row did not inspect an input event")
    require(payload["scroll_width"] <= payload["window_width"], "Studio policy observation window introduced horizontal page overflow")


def check_studio_policy_compare(cdp: Any, session_id: str) -> None:
    expression = """
      (() => {
        document.body.classList.remove('capture-mode');
        window.romiCapture.seekToSeconds(11.8);
        window.romiCapture.setMode('compare');
        const report = window.romiCapture.policyCompareReport();
        return JSON.stringify({
          report,
          active_tab: document.querySelector('.mode-tab.active')?.dataset.mode,
          compare_text: document.getElementById('modeView').textContent,
          card_count: document.querySelectorAll('.compare-card').length,
          diff_count: document.querySelectorAll('.diff-row').length,
          changed_count: document.querySelectorAll('.diff-row.changed').length,
          scroll_width: document.documentElement.scrollWidth,
          window_width: window.innerWidth,
        });
      })();
    """
    result = cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
    )
    payload = json.loads(result["result"]["value"])
    report = payload["report"]
    policies = report["policies"]
    policy_ids = {policy["policy_id"] for policy in policies}
    require(payload["active_tab"] == "compare", "Studio policy compare tab did not activate")
    require(report["report_kind"] == "romi.counterfactual_policy_compare", "Studio policy compare report kind mismatch")
    require(report["clock_domain"] == "sim_time", "Studio policy compare clock domain mismatch")
    require(report["observation_window"]["required_inputs"] == 6, "Studio policy compare required input count mismatch")
    require(report["observation_window"]["fresh_inputs"] >= 5, "Studio policy compare should use mostly fresh inputs")
    require(len(policies) == 2, "Studio policy compare should render two policies")
    require(policy_ids == {"mock_policy_v1", "mock_policy_v2_guarded"}, "Studio policy compare policy ids mismatch")
    require(all(policy["authority"] == "proposed_only" for policy in policies), "Studio policy compare authority mismatch")
    require(all(policy["actuator_authority"] == "none" for policy in policies), "Studio policy compare actuator authority mismatch")
    require(all(policy["command_stream_emitted"] is False for policy in policies), "Studio policy compare command stream boundary mismatch")
    require(report["safety_boundary"]["command_stream_emitted"] is False, "Studio policy compare safety boundary should not emit commands")
    require(len(report["diffs"]) >= 3, "Studio policy compare diff count mismatch")
    require(payload["card_count"] == 2, "Studio policy compare card count mismatch")
    require(payload["diff_count"] >= 3, "Studio policy compare UI diff rows missing")
    require(payload["changed_count"] >= 1, "Studio policy compare UI should show at least one changed action")
    require("mock_policy_v1" in payload["compare_text"], "Studio policy compare UI missing baseline policy")
    require("mock_policy_v2_guarded" in payload["compare_text"], "Studio policy compare UI missing guarded policy")
    require("not_emitted" in payload["compare_text"], "Studio policy compare UI missing command stream boundary")
    require("->" in payload["compare_text"], "Studio policy compare UI missing action diff arrow")
    require(payload["scroll_width"] <= payload["window_width"], "Studio policy compare introduced horizontal page overflow")


def check_studio_safety_authority(cdp: Any, session_id: str) -> None:
    expression = """
      (() => {
        document.body.classList.remove('capture-mode');
        window.romiCapture.seekToSeconds(13.6);
        window.romiCapture.setMode('safety');
        const report = window.romiCapture.safetyReport();
        return JSON.stringify({
          report,
          safety_text: document.getElementById('modeView').textContent,
          active_tab: document.querySelector('.mode-tab.active')?.dataset.mode,
          scroll_width: document.documentElement.scrollWidth,
          window_width: window.innerWidth,
        });
      })();
    """
    result = cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
    )
    payload = json.loads(result["result"]["value"])
    report = payload["report"]
    require(payload["active_tab"] == "safety", "Studio safety tab did not activate")
    require(report["report_kind"] == "romi.safety_authority_report", "Studio safety report kind mismatch")
    require(report["policy_authority"] == "proposed_only", "Studio safety policy authority mismatch")
    require(report["actuator_authority"] == "none", "Studio safety actuator authority mismatch")
    require(report["command_stream_emitted"] is False, "Studio safety command stream should not be emitted")
    require(report["promotion_required"] == "external_supervisor", "Studio safety promotion boundary mismatch")
    require(report["policy_samples"] > 0, "Studio safety report missing policy samples")
    require(all(action["blocked"] is True for action in report["proposed_actions"]), "Studio safety report must block proposed actions")
    require("not_emitted" in payload["safety_text"], "Studio safety UI missing command stream state")
    require("proposal_not_actuator_authority" in payload["safety_text"], "Studio safety UI missing blocked reason")
    require(payload["scroll_width"] <= payload["window_width"], "Studio safety view introduced horizontal page overflow")


def check_studio_runtime_graph(cdp: Any, session_id: str) -> None:
    expression = """
      (() => {
        document.body.classList.remove('capture-mode');
        window.romiCapture.seekToSeconds(13.2);
        window.romiCapture.selectGraphNode('policy');
        const policyDetail = document.getElementById('graphDetail').textContent;
        const selectedPolicy = document.querySelector('#graphPolicy.selected button')?.getAttribute('aria-pressed');
        const policyOutput = document.querySelector('#graphDetail [data-inspect-stream="policy.proposed_action"]');
        if (policyOutput) {
          policyOutput.click();
        }
        const selectedEvent = document.getElementById('eventInspectorStatus').textContent;
        window.romiCapture.selectGraphNode('report');
        const reportDetail = document.getElementById('graphDetail').textContent;
        return JSON.stringify({
          policy_detail: policyDetail,
          selected_policy: selectedPolicy,
          selected_event: selectedEvent,
          report_detail: reportDetail,
          graph_buttons: document.querySelectorAll('[data-graph-node]').length,
          scroll_width: document.documentElement.scrollWidth,
          window_width: window.innerWidth,
        });
      })();
    """
    result = cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
    )
    payload = json.loads(result["result"]["value"])
    require(payload["graph_buttons"] == 5, "Studio runtime graph node count mismatch")
    require(payload["selected_policy"] == "true", "Studio runtime graph did not select policy node")
    require("policy.proposed_action" in payload["policy_detail"], "Studio runtime graph policy output missing")
    require("inputs fresh" in payload["policy_detail"], "Studio runtime graph policy freshness missing")
    require("observation window" in payload["policy_detail"], "Studio runtime graph policy connection missing")
    require(payload["selected_event"] == "policy.proposed_action", "Studio runtime graph output did not inspect policy event")
    require("dataset report" in payload["report_detail"], "Studio runtime graph report node detail missing")
    require("episode + policy" in payload["report_detail"], "Studio runtime graph dataset connection missing")
    require(payload["scroll_width"] <= payload["window_width"], "Studio runtime graph introduced horizontal page overflow")


def check_browser_native_contract(repo_root: Path, chrome_bin: str, contract: dict[str, Any]) -> None:
    helpers = load_capture_helpers(repo_root)

    with tempfile.TemporaryDirectory(prefix="romi-native-contract-") as tmp:
        native_events = run_native_source(repo_root, Path(tmp) / "native-events.jsonl")

    cdp = None
    server = None
    chrome = None
    chrome_profile = None
    try:
        cdp, session_id, server, chrome, chrome_profile = start_browser(repo_root, chrome_bin, helpers)
        snapshot_times = contract["browser_native_compare"]["snapshot_times_sec"]
        snapshots = {sim_time_sec: browser_snapshot(cdp, session_id, sim_time_sec, contract) for sim_time_sec in snapshot_times}

        for sim_time_sec, snapshot in snapshots.items():
            event_time_ns = int(sim_time_sec * 1_000_000_000)
            for stream_id in required_stream_ids(contract):
                native_event = latest_stream_at_or_before(native_events, stream_id, event_time_ns)
                browser_event = snapshot[stream_id]
                check_common_event_contract(browser_event, native_event, stream_id, contract)
                check_stream_payload(browser_event, native_event, stream_id, contract)

        policy_snapshot = max(snapshots)
        check_policy_event(snapshots[policy_snapshot][contract["policy"]["stream_id"]], contract)
        check_studio_seek_controls(cdp, session_id)
        check_studio_event_inspector(cdp, session_id)
        check_studio_dataset_report(cdp, session_id)
        check_studio_policy_observation_window(cdp, session_id)
        check_studio_policy_compare(cdp, session_id)
        check_studio_safety_authority(cdp, session_id)
        check_studio_runtime_graph(cdp, session_id)
        print(
            json.dumps(
                {
                    "contract_id": contract["contract_id"],
                    "required_streams": len(required_stream_ids(contract)),
                    "snapshots": list(snapshots),
                    "policy_authority": contract["policy"]["authority"],
                    "source_systems": ["romi_2d_sim", "romi_native_sim"],
                },
                sort_keys=True,
            )
        )
    finally:
        if cdp is not None:
            cdp.close()
        if chrome is not None:
            terminate(chrome)
        if server is not None:
            terminate(server)
        if chrome_profile is not None:
            chrome_profile.cleanup()


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_chrome = (
        shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or "google-chrome"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--contract", type=Path, default=default_contract_path(repo_root))
    parser.add_argument("--chrome-bin", default=default_chrome)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    check_browser_native_contract(args.repo_root.resolve(), args.chrome_bin, load_json(args.contract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
