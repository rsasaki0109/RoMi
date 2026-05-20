"use strict";

const canvas = document.getElementById("simCanvas");
const ctx = canvas.getContext("2d");

const stageValue = document.getElementById("stageValue");
const clockValue = document.getElementById("clockValue");
const policyValue = document.getElementById("policyValue");
const streamList = document.getElementById("streamList");
const eventLog = document.getElementById("eventLog");

const startButton = document.getElementById("startButton");
const pauseButton = document.getElementById("pauseButton");
const resetButton = document.getElementById("resetButton");
const exportButton = document.getElementById("exportButton");

const graphNodes = {
  source: document.getElementById("graphSource"),
  record: document.getElementById("graphRecord"),
  replay: document.getElementById("graphReplay"),
  policy: document.getElementById("graphPolicy"),
  report: document.getElementById("graphReport"),
};

const streams = [
  "robot.camera.rgb",
  "robot.camera.depth",
  "robot.camera.info",
  "robot.joints.state",
  "robot.base.odom",
  "robot.frames.tf",
  "task.goal",
  "policy.proposed_action",
  "runtime.diagnostics",
];

const colors = {
  grid: "#20303a",
  field: "#132028",
  cyan: "#38d9ef",
  green: "#8bd450",
  amber: "#ffbf6b",
  rose: "#f58aa5",
  text: "#edf5f8",
  muted: "#94a9b5",
};

const state = {
  scenario: null,
  running: false,
  ready: false,
  error: null,
  lastFrameMs: 0,
  elapsedSec: 0,
  durationSec: 0,
  rateHz: 12,
  diagnosticEvery: 6,
  sampleIndex: 0,
  events: [],
  streamCounts: Object.fromEntries(streams.map((stream) => [stream, 0])),
  trace: [],
};

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function ease(value) {
  const t = clamp(value);
  return t * t * (3 - 2 * t);
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function pair(value, fallback) {
  if (Array.isArray(value) && value.length >= 2) {
    return [Number(value[0]), Number(value[1])];
  }
  return fallback;
}

function scenarioTiming() {
  return state.scenario?.timing || {};
}

function robotConfig() {
  return state.scenario?.robot || {};
}

function armConfig() {
  return state.scenario?.arm || {};
}

function workspaceConfig() {
  return state.scenario?.workspace || {};
}

function visualConfig() {
  return state.scenario?.visual || {};
}

function cameraConfig() {
  return state.scenario?.camera || {};
}

function robotPose(progress) {
  const robot = robotConfig();
  const timing = scenarioTiming();
  const [startX, startY] = pair(robot.start_px, [140, 392]);
  const [goalX, goalY] = pair(robot.goal_px, [625, 392]);
  const navEnd = Number(timing.nav_end ?? 0.58);
  const nav = ease(navEnd > 0 ? progress / navEnd : progress);
  const x = lerp(startX, goalX, nav);
  const y = lerp(startY, goalY, nav) - Number(robot.path_arc_height_px ?? 120) * Math.sin(nav * Math.PI);
  const yaw = lerp(Number(robot.yaw_start_rad ?? -0.05), Number(robot.yaw_goal_rad ?? -0.65), nav);
  return { x, y, yaw };
}

function armReach(progress) {
  const timing = scenarioTiming();
  const start = Number(timing.reach_start ?? 0.56);
  const end = Number(timing.reach_end ?? 0.72);
  return ease(end > start ? (progress - start) / (end - start) : progress);
}

function placeReach(progress) {
  const timing = scenarioTiming();
  const start = Number(timing.place_start ?? 0.78);
  const end = Number(timing.place_end ?? 0.92);
  return ease(end > start ? (progress - start) / (end - start) : progress);
}

function currentStage(progress) {
  const stages = Array.isArray(scenarioTiming().stages) ? scenarioTiming().stages : [];
  for (const stage of stages) {
    if (Number(stage.start) <= progress && progress < Number(stage.end)) {
      return String(stage.name || "unknown");
    }
  }
  return "report";
}

function objectState(progress) {
  const timing = scenarioTiming();
  if (progress >= Number(timing.placed_after ?? 0.88)) return "placed";
  if (progress >= Number(timing.grasp_start ?? 0.70)) return "held";
  return "on_table";
}

function objectPosition(progress) {
  const workspace = workspaceConfig();
  const arm = armConfig();
  const [tableX, tableY] = pair(workspace.object_start_px, [712, 292]);
  const [binX, binY] = pair(workspace.bin_px, [768, 320]);
  const pose = robotPose(progress);
  const [carryX, carryY] = pair(arm.tool_carry_offset_px, [72, -34]);
  const carried = { x: pose.x + carryX, y: pose.y + carryY };
  const stateName = objectState(progress);

  if (stateName === "on_table") return { x: tableX, y: tableY };
  if (stateName === "held") {
    const reach = armReach(progress);
    return { x: lerp(tableX, carried.x, reach), y: lerp(tableY, carried.y, reach) };
  }

  const place = placeReach(progress);
  return { x: lerp(carried.x, binX, place), y: lerp(carried.y, binY, place) };
}

function worldToRomi(pose) {
  const world = state.scenario?.world || {};
  const [originX, originY] = pair(world.origin_px, [140, 392]);
  const scale = Number(world.scale_px_per_m ?? 300);
  return {
    x: (pose.x - originX) / scale,
    y: (originY - pose.y) / scale,
    z: 0,
  };
}

function createEvent(streamId, payloadSummary, frameId, semanticType, sourceMessageType) {
  state.streamCounts[streamId] += 1;
  return {
    schema_version: "0.1.0",
    schema_id: streamId === "policy.proposed_action" ? "romi.ml.policy_io/0.1.0" : "romi.robotics.stream_metadata/0.1.0",
    kind: "stream_sample",
    stream_id: streamId,
    semantic_type: semanticType,
    source_system: "romi_2d_sim",
    source_topic: null,
    source_message_type: sourceMessageType,
    event_time_ns: Math.round(state.elapsedSec * 1_000_000_000),
    clock_domain: "sim_time",
    frame_id: frameId,
    payload_summary: payloadSummary,
    metadata: {
      source: "romi_2d_sim",
      scenario_id: state.scenario?.scenario_id,
      sample_index: state.streamCounts[streamId],
    },
  };
}

function emitEvents(progress) {
  const pose = robotPose(progress);
  const worldPose = worldToRomi(pose);
  const reach = armReach(progress);
  const stage = currentStage(progress);
  const object = objectPosition(progress);
  const objectStatus = objectState(progress);
  const holding = objectStatus === "held";
  const camera = cameraConfig();
  const cameraWidth = Number(camera.width ?? 160);
  const cameraHeight = Number(camera.height ?? 90);
  const visual = visualConfig();
  const objectCameraX = Math.round(clamp(object.x / Number(visual.canvas_width ?? 960)) * cameraWidth);
  const objectCameraY = Math.round(clamp(object.y / Number(visual.canvas_height ?? 620)) * cameraHeight);

  const events = [
    createEvent("robot.camera.rgb", {
      width: cameraWidth,
      height: cameraHeight,
      encoding: "rgb8",
      synthetic_scene: {
        target_centroid_px: { x: objectCameraX, y: objectCameraY },
        target_visible: objectStatus !== "placed",
        object_state: objectStatus,
      },
    }, "camera_color_optical_frame", "rgb_image", "romi.robotics.ImageSummary"),
    createEvent("robot.camera.depth", {
      width: cameraWidth,
      height: cameraHeight,
      encoding: "16UC1",
      synthetic_scene: {
        target_depth_mm: Number(camera[holding ? "held_depth_mm" : "target_depth_mm"] ?? 620),
        object_state: objectStatus,
      },
    }, "camera_depth_optical_frame", "depth_image", "romi.robotics.ImageSummary"),
    createEvent("robot.camera.info", {
      width: cameraWidth,
      height: cameraHeight,
      distortion_model: "plumb_bob",
      k_len: 9,
      p_len: 12,
    }, "camera_color_optical_frame", "camera_info", "romi.robotics.CameraInfoSummary"),
    createEvent("robot.joints.state", {
      joint_count: 6,
      joint_names_sample: ["shoulder_pan", "shoulder_lift", "elbow", "wrist", "gripper_left", "gripper_right"],
      position_sample: [-0.22 * reach, -0.52 * reach, 0.82 * reach, -0.34 * reach, holding ? 0.0 : 0.04, holding ? 0.0 : 0.04],
      position_count: 6,
    }, "base_link", "joint_state", "romi.robotics.JointStateSummary"),
    createEvent("robot.base.odom", {
      child_frame_id: "base_link",
      position: worldPose,
      orientation: { x: 0, y: 0, z: Math.sin(pose.yaw / 2), w: Math.cos(pose.yaw / 2) },
      linear: { x: stage === "navigate" ? 0.35 : 0, y: 0, z: 0 },
      angular: { x: 0, y: 0, z: stage === "navigate" ? -0.15 : 0 },
      stage,
    }, "odom", "odometry", "romi.robotics.OdometrySummary"),
    createEvent("robot.frames.tf", {
      transform_count: 6,
      frames_sample: [
        { parent_frame_id: "map", child_frame_id: "odom" },
        { parent_frame_id: "odom", child_frame_id: "base_link" },
        { parent_frame_id: "base_link", child_frame_id: "camera_color_optical_frame" },
        { parent_frame_id: "base_link", child_frame_id: "camera_depth_optical_frame" },
        { parent_frame_id: "base_link", child_frame_id: "arm_base_link" },
        { parent_frame_id: "arm_base_link", child_frame_id: "tool0" },
      ],
      synthetic_object_position: worldToRomi(object),
    }, "map->odom", "transform_tree", "romi.robotics.TransformTreeSummary"),
  ];

  if (state.sampleIndex % Math.max(1, Math.round(state.rateHz)) === 0) {
    const goal = state.scenario?.goal || {};
    events.push(createEvent("task.goal", {
      position: goal.position_m || { x: 1.6, y: 0, z: 0 },
      orientation: goal.orientation || { x: 0, y: 0, z: 0, w: 1 },
      target_object: workspaceConfig().target_object || "orange_cube",
      scenario_id: state.scenario?.scenario_id,
    }, goal.frame_id || "map", "task_goal", "romi.robotics.PoseGoalSummary"));
  }

  if (state.sampleIndex % Math.max(1, Math.round(state.rateHz * 1.5)) === 0 || progress > 0.68) {
    events.push(createEvent("policy.proposed_action", {
      policy_id: "mock_nav_manip_policy",
      proposed_actions: [
        { target: "base", action_type: stage === "navigate" ? "navigate_to_goal" : "hold_position", authority: "proposed_only" },
        { target: "end_effector", action_type: holding ? "carry_object" : "reach_target", authority: "proposed_only" },
        { target: "gripper", action_type: holding ? "hold_closed" : "prepare_grasp", authority: "proposed_only" },
      ],
      inference_latency_ms: 1.4 + 0.5 * Math.sin(progress * Math.PI * 2),
      metadata: { authority: "proposed_only", scenario_id: state.scenario?.scenario_id },
    }, "base_link", "command", "romi.ml.PolicyProposedAction"));
  }

  if (state.sampleIndex % state.diagnosticEvery === 0) {
    state.streamCounts["runtime.diagnostics"] += 1;
    events.push({
      schema_version: "0.1.0",
      schema_id: "romi.core.diagnostic_event/0.1.0",
      kind: "diagnostic_event",
      event_id: `romi_2d_sim_runtime_${state.streamCounts["runtime.diagnostics"]}`,
      time: { event_time_ns: Math.round(state.elapsedSec * 1_000_000_000), clock_domain: "sim_time" },
      severity: "info",
      source: "romi_2d_sim",
      category: "runtime",
      message: "Simulator emitted synchronized navigation/manipulation step.",
      attributes: {
        scenario_id: state.scenario?.scenario_id,
        stage,
        stream_count: streams.length,
      },
    });
  }

  state.events.push(...events);
  state.sampleIndex += 1;
  state.trace.push({ x: pose.x, y: pose.y });
  if (state.trace.length > 260) state.trace.shift();
}

function drawGrid() {
  const visual = visualConfig();
  const grid = Number(visual.grid_px ?? 32);
  ctx.fillStyle = colors.field;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = colors.grid;
  ctx.lineWidth = 1;
  for (let x = 0; x < canvas.width; x += grid) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += grid) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }
}

function drawWorkspace(progress) {
  const workspace = workspaceConfig();
  const zone = workspace.zone_px || { x: 650, y: 240, width: 215, height: 160 };
  ctx.fillStyle = "#263923";
  ctx.strokeStyle = colors.green;
  roundRect(zone.x, zone.y, zone.width, zone.height, 10, true, true);
  ctx.fillStyle = colors.green;
  ctx.font = "14px sans-serif";
  ctx.fillText("manipulation zone", zone.x + 20, zone.y + 26);

  const [binX, binY] = pair(workspace.bin_px, [768, 320]);
  ctx.fillStyle = "#33462f";
  ctx.strokeStyle = "#b2f07b";
  roundRect(binX - 44, binY - 10, 88, 56, 8, true, true);
  ctx.fillStyle = colors.text;
  ctx.font = "12px sans-serif";
  ctx.fillText("place bin", binX - 24, binY + 22);

  if (objectState(progress) !== "placed") {
    const object = objectPosition(progress);
    ctx.fillStyle = colors.amber;
    ctx.strokeStyle = "#ffe3b6";
    roundRect(object.x - 13, object.y - 13, 26, 26, 5, true, true);
  }
}

function drawTrace() {
  if (state.trace.length < 2) return;
  ctx.strokeStyle = "#5b7282";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(state.trace[0].x, state.trace[0].y);
  for (const point of state.trace.slice(1)) {
    ctx.lineTo(point.x, point.y);
  }
  ctx.stroke();
}

function drawRobot(progress) {
  const pose = robotPose(progress);
  const robot = robotConfig();
  const arm = armConfig();
  const reach = armReach(progress);
  const holding = objectState(progress) === "held";
  const [baseW, baseH] = pair(robot.base_size_px, [68, 46]);

  ctx.save();
  ctx.translate(pose.x, pose.y);
  ctx.rotate(pose.yaw);
  ctx.fillStyle = "#1e323a";
  ctx.strokeStyle = colors.cyan;
  ctx.lineWidth = 3;
  roundRect(-baseW / 2, -baseH / 2, baseW, baseH, 12, true, true);

  ctx.fillStyle = colors.cyan;
  ctx.beginPath();
  ctx.moveTo(baseW / 2 - 6, 0);
  ctx.lineTo(10, -10);
  ctx.lineTo(10, 10);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = colors.text;
  ctx.font = "12px sans-serif";
  ctx.fillText(robot.label || "RoMi", -16, 4);
  ctx.restore();

  const [shoulderX, shoulderY] = pair(robot.shoulder_offset_px, [28, -9]);
  const shoulder = { x: pose.x + shoulderX, y: pose.y + shoulderY };
  const [homeElbowX, homeElbowY] = pair(arm.home_elbow_offset_px, [42, -28]);
  const [homeWristX, homeWristY] = pair(arm.home_wrist_offset_px, [80, -38]);
  const [targetElbowX, targetElbowY] = pair(arm.target_elbow_px, [694, 278]);
  const [targetWristX, targetWristY] = pair(arm.target_wrist_px, [722, 288]);
  const elbow = { x: lerp(shoulder.x + homeElbowX, targetElbowX, reach), y: lerp(shoulder.y + homeElbowY, targetElbowY, reach) };
  const wrist = { x: lerp(shoulder.x + homeWristX, targetWristX, reach), y: lerp(shoulder.y + homeWristY, targetWristY, reach) };
  const tool = holding ? objectPosition(progress) : { x: wrist.x + 18, y: wrist.y };

  ctx.strokeStyle = colors.amber;
  ctx.lineWidth = 8;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(shoulder.x, shoulder.y);
  ctx.lineTo(elbow.x, elbow.y);
  ctx.lineTo(wrist.x, wrist.y);
  ctx.lineTo(tool.x, tool.y);
  ctx.stroke();

  for (const point of [shoulder, elbow, wrist]) {
    ctx.fillStyle = "#ffe0a6";
    ctx.beginPath();
    ctx.arc(point.x, point.y, 7, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.fillStyle = colors.rose;
  ctx.font = "13px sans-serif";
  if (progress > 0.62) ctx.fillText("policy.proposed_action", 602, 218);
}

function drawHud(progress) {
  ctx.fillStyle = "rgba(13, 18, 22, 0.82)";
  ctx.strokeStyle = "#2f4554";
  roundRect(24, 22, 408, 92, 8, true, true);
  ctx.fillStyle = colors.text;
  ctx.font = "20px sans-serif";
  ctx.fillText("RoMi 2D sim source", 44, 55);
  ctx.fillStyle = colors.muted;
  ctx.font = "13px sans-serif";
  ctx.fillText(`${state.scenario?.scenario_id || "scenario"} / ROS2-free`, 44, 80);
  ctx.fillText(`stage: ${currentStage(progress)}`, 44, 100);
}

function drawLoadError() {
  ctx.fillStyle = colors.field;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = colors.text;
  ctx.font = "22px sans-serif";
  ctx.fillText("Scenario load failed", 42, 72);
  ctx.fillStyle = colors.muted;
  ctx.font = "14px sans-serif";
  ctx.fillText("Start the static server from examples/navigation_manipulation_demo and open /romi_2d_sim/.", 42, 102);
  ctx.fillText(String(state.error || ""), 42, 132);
}

function roundRect(x, y, width, height, radius, fill, stroke) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + width, y, x + width, y + height, radius);
  ctx.arcTo(x + width, y + height, x, y + height, radius);
  ctx.arcTo(x, y + height, x, y, radius);
  ctx.arcTo(x, y, x + width, y, radius);
  ctx.closePath();
  if (fill) ctx.fill();
  if (stroke) ctx.stroke();
}

function render() {
  if (state.error) {
    drawLoadError();
    updateInspector(0);
    return;
  }
  if (!state.ready) return;
  const progress = clamp(state.elapsedSec / state.durationSec);
  drawGrid();
  drawWorkspace(progress);
  drawTrace();
  drawRobot(progress);
  drawHud(progress);
  updateInspector(progress);
}

function updateInspector(progress) {
  stageValue.textContent = state.error ? "scenario_error" : currentStage(progress);
  clockValue.textContent = `${state.elapsedSec.toFixed(2)}s`;
  policyValue.textContent = state.streamCounts["policy.proposed_action"] > 0 ? "proposing" : "waiting";

  const maxCount = Math.max(1, ...Object.values(state.streamCounts));
  streamList.innerHTML = "";
  for (const stream of streams) {
    const row = document.createElement("div");
    row.className = "stream-row";
    const label = document.createElement("span");
    label.textContent = stream.replace("robot.", "").replace("policy.", "policy.");
    const bar = document.createElement("div");
    bar.className = "bar";
    const fill = document.createElement("span");
    fill.style.width = `${(state.streamCounts[stream] / maxCount) * 100}%`;
    bar.appendChild(fill);
    const count = document.createElement("span");
    count.textContent = String(state.streamCounts[stream]);
    row.append(label, bar, count);
    streamList.appendChild(row);
  }

  graphNodes.source.classList.toggle("active", progress >= 0.01);
  graphNodes.record.classList.toggle("active", state.events.length > 0);
  graphNodes.replay.classList.toggle("active", progress > 0.42);
  graphNodes.policy.classList.toggle("active", state.streamCounts["policy.proposed_action"] > 0);
  graphNodes.report.classList.toggle("active", progress > 0.9);

  const recent = state.error
    ? [`error ${state.error}`]
    : state.events.slice(-6).map((event) => `${event.kind} ${event.stream_id || event.event_id}`);
  eventLog.textContent = recent.join("\n");
}

function tick(frameMs) {
  if (!state.lastFrameMs) state.lastFrameMs = frameMs;
  const deltaSec = Math.min(0.05, (frameMs - state.lastFrameMs) / 1000);
  state.lastFrameMs = frameMs;

  if (state.ready && state.running) {
    state.elapsedSec = Math.min(state.durationSec, state.elapsedSec + deltaSec);
    if (state.sampleIndex === 0 || state.elapsedSec * state.rateHz >= state.sampleIndex) {
      emitEvents(clamp(state.elapsedSec / state.durationSec));
    }
    if (state.elapsedSec >= state.durationSec) {
      state.running = false;
    }
  }

  render();
  window.requestAnimationFrame(tick);
}

function reset() {
  state.running = false;
  state.lastFrameMs = 0;
  state.elapsedSec = 0;
  state.sampleIndex = 0;
  state.events = [];
  state.streamCounts = Object.fromEntries(streams.map((stream) => [stream, 0]));
  state.trace = [];
  render();
}

function exportJsonl() {
  const blob = new Blob([state.events.map((event) => JSON.stringify(event)).join("\n") + "\n"], {
    type: "application/x-ndjson",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${state.scenario?.scenario_id || "romi-2d-sim"}-events.jsonl`;
  link.click();
  URL.revokeObjectURL(url);
}

async function loadScenario() {
  const response = await fetch("../scenario.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`scenario.json HTTP ${response.status}`);
  }
  const scenario = await response.json();
  state.scenario = scenario;
  state.durationSec = Number(scenario.timing?.duration_sec ?? 16);
  state.rateHz = Number(scenario.timing?.rate_hz ?? 12);
  state.diagnosticEvery = Math.max(1, Math.round(state.rateHz * Number(scenario.timing?.diagnostics_period_sec ?? 0.5)));
  canvas.width = Number(scenario.visual?.canvas_width ?? 960);
  canvas.height = Number(scenario.visual?.canvas_height ?? 620);
  state.ready = true;
}

startButton.addEventListener("click", () => {
  if (!state.ready) return;
  if (state.elapsedSec >= state.durationSec) reset();
  state.running = true;
});
pauseButton.addEventListener("click", () => {
  state.running = false;
});
resetButton.addEventListener("click", reset);
exportButton.addEventListener("click", exportJsonl);

loadScenario()
  .then(reset)
  .catch((error) => {
    state.error = error.message;
    render();
  });
window.requestAnimationFrame(tick);
