"use strict";

const canvas = document.getElementById("simCanvas");
const ctx = canvas.getContext("2d");
const urlParams = new URLSearchParams(window.location.search);
const captureMode = urlParams.get("capture") === "readme";

if (captureMode) {
  document.body.classList.add("capture-mode");
}

const stageValue = document.getElementById("stageValue");
const clockValue = document.getElementById("clockValue");
const policyValue = document.getElementById("policyValue");
const streamList = document.getElementById("streamList");
const eventLog = document.getElementById("eventLog");
const eventInspectorStatus = document.getElementById("eventInspectorStatus");
const eventTimeline = document.getElementById("eventTimeline");
const eventSummary = document.getElementById("eventSummary");
const modeStatus = document.getElementById("modeStatus");
const modeView = document.getElementById("modeView");
const modeButtons = Array.from(document.querySelectorAll(".mode-tab"));
const seekControl = document.getElementById("seekControl");
const seekValue = document.getElementById("seekValue");
const graphDetail = document.getElementById("graphDetail");

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

const policyInputStreams = [
  "robot.camera.rgb",
  "robot.camera.depth",
  "robot.joints.state",
  "robot.base.odom",
  "robot.frames.tf",
  "task.goal",
];

const graphNodeDefinitions = [
  {
    id: "source",
    label: "native simulator",
    role: "source",
    inputs: ["scenario.json"],
    outputs: ["robot.camera.rgb", "robot.camera.depth", "robot.camera.info", "robot.joints.state", "robot.base.odom", "robot.frames.tf", "task.goal", "runtime.diagnostics"],
  },
  {
    id: "record",
    label: "episode recorder",
    role: "log/dataset plane",
    inputs: ["robot.*", "task.goal", "runtime.diagnostics"],
    outputs: ["episode.jsonl", "episode_metadata"],
  },
  {
    id: "replay",
    label: "replay source",
    role: "replay plane",
    inputs: ["episode.jsonl"],
    outputs: ["robot.*", "task.goal", "runtime.diagnostics"],
  },
  {
    id: "policy",
    label: "mock policy",
    role: "policy runtime",
    inputs: policyInputStreams,
    outputs: ["policy.proposed_action"],
  },
  {
    id: "report",
    label: "dataset report",
    role: "dataset/report plane",
    inputs: ["episode.jsonl", "policy.proposed_action"],
    outputs: ["dataset-report.md", "observation_window"],
  },
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
  mode: "live",
  selectedEventIndex: null,
  selectedGraphNode: "source",
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

function displayMode(progress) {
  if (!captureMode) return state.mode;
  if (progress < 0.34) return "live";
  if (progress < 0.58) return "replay";
  if (progress < 0.82) return "policy";
  if (progress < 0.92) return "safety";
  return "dataset";
}

function setMode(mode) {
  state.mode = mode;
  render();
}

function seekToSeconds(elapsedSec, mode = "replay") {
  if (!state.ready || state.error) return;
  if (!captureMode && mode) state.mode = mode;
  seekCapture(elapsedSec);
}

function selectEventIndex(index) {
  if (index < 0 || index >= state.events.length) return;
  state.selectedEventIndex = index;
  render();
}

function selectLatestStreamEvent(streamId) {
  const index = latestEventIndex(streamId);
  if (index >= 0) selectEventIndex(index);
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
  const isPolicy = streamId === "policy.proposed_action";
  return {
    schema_version: "0.1.0",
    schema_id: isPolicy ? "romi.ml.policy_io/0.1.0" : "romi.robotics.stream_metadata/0.1.0",
    kind: "stream_sample",
    stream_id: streamId,
    semantic_type: semanticType,
    source_system: "romi_2d_sim",
    source_topic: null,
    source_message_type: sourceMessageType,
    event_time_ns: Math.round(state.elapsedSec * 1_000_000_000),
    source_emit_wall_time_ns: Date.now() * 1_000_000,
    clock_domain: "sim_time",
    frame_id: frameId,
    payload_summary: payloadSummary,
    metadata: {
      source: "romi_2d_sim",
      scenario_id: state.scenario?.scenario_id,
      robot_morphology: robotConfig().morphology,
      sample_index: state.streamCounts[streamId],
      authority: isPolicy ? "proposed_only" : "observation_only",
    },
  };
}

function latestEventFrom(events, streamId) {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event.stream_id === streamId || (streamId === "runtime.diagnostics" && event.kind === "diagnostic_event")) {
      return event;
    }
  }
  return null;
}

function policyObservationWindow(sourceEvents, eventTimeNs) {
  return policyInputStreams.map((streamId) => {
    const event = latestEventFrom(sourceEvents, streamId);
    const observedTimeNs = Number(event?.event_time_ns ?? event?.time?.event_time_ns ?? 0);
    const ageMs = event ? Math.max(0, (eventTimeNs - observedTimeNs) / 1_000_000) : null;
    const status = event ? (ageMs <= 350 ? "fresh" : "stale") : "missing";
    return {
      stream_id: streamId,
      status,
      age_ms: ageMs === null ? null : Number(ageMs.toFixed(1)),
      frame_id: event?.frame_id || null,
      semantic_type: event?.semantic_type || null,
      sample_index: event?.metadata?.sample_index ?? null,
    };
  });
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
  const eventTimeNs = Math.round(state.elapsedSec * 1_000_000_000);
  const objectCameraX = Math.round(clamp(object.x / Number(visual.canvas_width ?? 960)) * (cameraWidth - 1));
  const objectCameraY = Math.round(clamp(object.y / Number(visual.canvas_height ?? 620)) * (cameraHeight - 1));
  const backgroundDepthStart = Number(camera.background_depth_start_mm ?? 1800);
  const backgroundDepthEnd = Number(camera.background_depth_end_mm ?? 900);

  const events = [
    createEvent("robot.camera.rgb", {
      height: cameraHeight,
      width: cameraWidth,
      encoding: "rgb8",
      is_bigendian: 0,
      step: cameraWidth * 3,
      data_len: cameraHeight * cameraWidth * 3,
      synthetic_scene: {
        target_centroid_px: { x: objectCameraX, y: objectCameraY },
        target_visible: objectStatus !== "placed",
        object_state: objectStatus,
        progress_bar: progress,
      },
    }, "camera_color_optical_frame", "rgb_image", "romi.robotics.ImageSummary"),
    createEvent("robot.camera.depth", {
      height: cameraHeight,
      width: cameraWidth,
      encoding: "16UC1",
      is_bigendian: 0,
      step: cameraWidth * 2,
      data_len: cameraHeight * cameraWidth * 2,
      synthetic_scene: {
        target_centroid_px: { x: objectCameraX, y: objectCameraY },
        target_depth_mm: Number(camera[holding ? "held_depth_mm" : "target_depth_mm"] ?? 620),
        background_depth_mm: Math.round(lerp(backgroundDepthStart, backgroundDepthEnd, ease(progress))),
        object_state: objectStatus,
      },
    }, "camera_depth_optical_frame", "depth_image", "romi.robotics.ImageSummary"),
    createEvent("robot.camera.info", {
      height: cameraHeight,
      width: cameraWidth,
      distortion_model: "plumb_bob",
      d_len: 0,
      k_len: 9,
      p_len: 12,
    }, "camera_color_optical_frame", "camera_info", "romi.robotics.CameraInfoSummary"),
    createEvent("robot.joints.state", {
      joint_count: 7,
      joint_names_sample: ["waist_yaw", "torso_lift", "right_shoulder_pitch", "right_elbow", "right_wrist", "gripper_left", "gripper_right"],
      position_sample: [
        pose.yaw,
        0.08 + 0.02 * Math.sin(progress * Math.PI),
        -0.22 * reach,
        0.82 * reach,
        -0.34 * reach,
        holding ? 0.0 : 0.04,
        holding ? 0.0 : 0.04,
      ],
      position_count: 7,
      velocity_count: 7,
      effort_count: 7,
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
        { parent_frame_id: "map", child_frame_id: "odom", stamp_ns: eventTimeNs },
        { parent_frame_id: "odom", child_frame_id: "base_link", stamp_ns: eventTimeNs },
        { parent_frame_id: "base_link", child_frame_id: "camera_color_optical_frame", stamp_ns: eventTimeNs },
        { parent_frame_id: "base_link", child_frame_id: "camera_depth_optical_frame", stamp_ns: eventTimeNs },
        { parent_frame_id: "base_link", child_frame_id: "arm_base_link", stamp_ns: eventTimeNs },
        { parent_frame_id: "arm_base_link", child_frame_id: "tool0", stamp_ns: eventTimeNs },
      ],
      synthetic_base_translation: worldPose,
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
    const observationWindow = policyObservationWindow([...state.events, ...events], eventTimeNs);
    events.push(createEvent("policy.proposed_action", {
      policy_id: "mock_nav_manip_policy",
      observation_window: observationWindow,
      input_status: {
        fresh: observationWindow.filter((input) => input.status === "fresh").length,
        stale: observationWindow.filter((input) => input.status === "stale").length,
        missing: observationWindow.filter((input) => input.status === "missing").length,
        required: observationWindow.length,
      },
      safety_boundary: {
        policy_authority: "proposed_only",
        actuator_authority: "none",
        command_stream_emitted: false,
        promotion_required: "external_supervisor",
        blocked_reason: "proposal_not_actuator_authority",
      },
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
      time: { event_time_ns: eventTimeNs, clock_domain: "sim_time" },
      severity: "info",
      source: "romi_2d_sim",
      category: "runtime",
      message: "Simulator emitted synchronized navigation/manipulation step.",
      attributes: {
        scenario_id: state.scenario?.scenario_id,
        sample_index: state.sampleIndex + 1,
        progress,
        stage,
        streams: [
          "robot.camera.rgb",
          "robot.camera.depth",
          "robot.camera.info",
          "robot.joints.state",
          "robot.base.odom",
          "robot.frames.tf",
        ],
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
  const [torsoW, torsoH] = pair(robot.torso_size_px, [42, 58]);
  const headRadius = Number(robot.head_radius_px ?? 17);

  ctx.save();
  ctx.translate(pose.x, pose.y);
  ctx.rotate(pose.yaw);

  ctx.fillStyle = "#17262e";
  ctx.strokeStyle = "#5d7280";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(-22, baseH / 2 + 4, 16, 8, 0, 0, Math.PI * 2);
  ctx.ellipse(22, baseH / 2 + 4, 16, 8, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

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

  ctx.fillStyle = "#263841";
  ctx.strokeStyle = colors.cyan;
  roundRect(-torsoW / 2, -baseH / 2 - torsoH + 8, torsoW, torsoH, 10, true, true);

  ctx.fillStyle = "#22313a";
  ctx.strokeStyle = "#b7f5ff";
  ctx.beginPath();
  ctx.arc(0, -baseH / 2 - torsoH - headRadius + 10, headRadius, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = colors.cyan;
  ctx.beginPath();
  ctx.arc(-6, -baseH / 2 - torsoH - headRadius + 7, 2.5, 0, Math.PI * 2);
  ctx.arc(6, -baseH / 2 - torsoH - headRadius + 7, 2.5, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = colors.text;
  ctx.font = "12px sans-serif";
  ctx.fillText(robot.label || "RoMi-H", -19, -baseH / 2 - 14);
  ctx.restore();

  const [shoulderX, shoulderY] = pair(robot.shoulder_offset_px, [28, -9]);
  const shoulder = { x: pose.x + shoulderX, y: pose.y + shoulderY };
  const [leftShoulderX, leftShoulderY] = pair(robot.left_shoulder_offset_px, [-12, -60]);
  const leftShoulder = { x: pose.x + leftShoulderX, y: pose.y + leftShoulderY };
  const [leftHandX, leftHandY] = pair(arm.left_hand_home_offset_px, [-52, -36]);
  const leftHand = { x: pose.x + leftHandX, y: pose.y + leftHandY };
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

  ctx.globalAlpha = 0.9;
  ctx.beginPath();
  ctx.moveTo(leftShoulder.x, leftShoulder.y);
  ctx.lineTo(leftShoulder.x - 22, leftShoulder.y + 28);
  ctx.lineTo(leftHand.x, leftHand.y);
  ctx.stroke();
  ctx.globalAlpha = 1;

  ctx.beginPath();
  ctx.moveTo(shoulder.x, shoulder.y);
  ctx.lineTo(elbow.x, elbow.y);
  ctx.lineTo(wrist.x, wrist.y);
  ctx.lineTo(tool.x, tool.y);
  ctx.stroke();

  for (const point of [leftShoulder, leftHand, shoulder, elbow, wrist]) {
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function stageTimeline(progress) {
  const stages = Array.isArray(scenarioTiming().stages) && scenarioTiming().stages.length
    ? scenarioTiming().stages
    : [
        { name: "init", start: 0, end: 0.08 },
        { name: "navigate", start: 0.08, end: 0.58 },
        { name: "reach", start: 0.58, end: 0.72 },
        { name: "grasp", start: 0.72, end: 0.78 },
        { name: "place", start: 0.78, end: 0.92 },
        { name: "report", start: 0.92, end: 1 },
      ];

  return `<div class="timeline">${stages.map((stage) => {
    const start = Number(stage.start ?? 0);
    const end = Number(stage.end ?? 1);
    const className = progress >= end ? "done" : progress >= start ? "active" : "";
    const seekProgress = clamp(start + 0.01, 0, 1);
    const label = escapeHtml(stage.name || "stage");
    return `<button class="timeline-step ${className}" type="button" data-seek-progress="${seekProgress.toFixed(4)}" aria-label="Seek to ${label}">${label}</button>`;
  }).join("")}</div>`;
}

function eventTimeSec(event) {
  const timeNs = Number(event?.event_time_ns ?? event?.time?.event_time_ns ?? 0);
  return timeNs > 0 ? timeNs / 1_000_000_000 : 0;
}

function streamFreshness(streamId) {
  const event = latestEvent(streamId);
  if (!event) return { status: "missing", label: "missing" };
  const age = Math.max(0, state.elapsedSec - eventTimeSec(event));
  return {
    status: age <= 0.35 ? "fresh" : "stale",
    label: age < 1 ? `${age.toFixed(2)}s` : `${age.toFixed(1)}s`,
  };
}

function renderFreshness(streamIds) {
  return `<div class="freshness-list">${streamIds.map((streamId) => {
    const freshness = streamFreshness(streamId);
    const label = streamId.replace("robot.", "").replace("policy.", "policy.");
    return `<div class="freshness-row ${freshness.status}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(freshness.label)}</strong></div>`;
  }).join("")}</div>`;
}

function renderKeyValues(rows) {
  return `<div class="key-value-list">${rows.map(([label, value]) => (
    `<div class="key-value-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
  )).join("")}</div>`;
}

function graphNodeDefinition(nodeId) {
  return graphNodeDefinitions.find((node) => node.id === nodeId) || graphNodeDefinitions[0];
}

function graphNodeRuntime(nodeId, progress) {
  const policyEvent = latestEvent("policy.proposed_action");
  const policyLatency = Number(policyEvent?.payload_summary?.inference_latency_ms ?? 0);
  const policyInputs = latestPolicyObservationWindow();
  const freshPolicyInputs = policyInputs.filter((input) => input.status === "fresh").length;
  const samplePeriodMs = state.rateHz > 0 ? 1000 / state.rateHz : 0;
  const report = datasetReport();
  const runtime = {
    source: {
      status: progress >= 0.01 || state.events.length > 0 ? "streaming" : "priming",
      latency: samplePeriodMs ? `${samplePeriodMs.toFixed(1)}ms period` : "waiting",
      contract: "observation_only",
      connection: "live sim -> record/replay/policy",
    },
    record: {
      status: state.events.length > 0 ? "recording" : "waiting",
      latency: "append-only",
      contract: `${state.events.length} buffered events`,
      connection: "stream samples -> episode.jsonl",
    },
    replay: {
      status: progress > 0.42 ? "seekable" : state.events.length > 0 ? "buffered" : "waiting",
      latency: "deterministic seek",
      contract: "online/offline symmetry",
      connection: "episode.jsonl -> same graph shape",
    },
    policy: {
      status: policyEvent ? "proposing" : "waiting",
      latency: policyLatency > 0 ? `${policyLatency.toFixed(2)}ms` : "waiting",
      contract: `${freshPolicyInputs}/${policyInputs.length} inputs fresh`,
      connection: "observation window -> policy.proposed_action",
    },
    report: {
      status: report.samples > 0 ? "available" : "waiting",
      latency: "browser-generated",
      contract: `${report.observation_window.available_streams}/${report.observation_window.required_streams} window streams`,
      connection: "episode + policy -> dataset report",
    },
  };
  return runtime[nodeId] || runtime.source;
}

function renderGraphToken(value) {
  const isStream = streams.includes(value);
  const tag = isStream ? "button" : "span";
  const attr = isStream ? ` type="button" data-inspect-stream="${escapeHtml(value)}"` : "";
  return `<${tag} class="graph-token"${attr}>${escapeHtml(value)}</${tag}>`;
}

function renderGraphDetail(progress) {
  if (!graphDetail) return;
  const node = graphNodeDefinition(state.selectedGraphNode);
  const runtime = graphNodeRuntime(node.id, progress);
  graphDetail.innerHTML = `<div class="graph-detail-heading">
      <span>${escapeHtml(node.role)}</span>
      <strong>${escapeHtml(runtime.status)}</strong>
    </div>
    ${renderKeyValues([
      ["latency", runtime.latency],
      ["contract", runtime.contract],
      ["path", runtime.connection],
    ])}
    <div class="graph-io">
      <div>
        <span>inputs</span>
        <div class="graph-token-list">${node.inputs.map(renderGraphToken).join("")}</div>
      </div>
      <div>
        <span>outputs</span>
        <div class="graph-token-list">${node.outputs.map(renderGraphToken).join("")}</div>
      </div>
    </div>
    ${node.id === "policy" ? renderPolicyObservationWindow(6) : ""}`;
}

function selectGraphNode(nodeId) {
  if (!graphNodeDefinitions.some((node) => node.id === nodeId)) return;
  state.selectedGraphNode = nodeId;
  render();
}

function eventName(event) {
  if (event?.stream_id === "robot.camera.rgb") return "RGB";
  if (event?.stream_id === "robot.camera.depth") return "DEP";
  if (event?.stream_id === "robot.camera.info") return "CAM";
  if (event?.stream_id === "robot.joints.state") return "JNT";
  if (event?.stream_id === "robot.base.odom") return "ODM";
  if (event?.stream_id === "robot.frames.tf") return "TF";
  if (event?.stream_id === "task.goal") return "GOAL";
  if (event?.stream_id === "policy.proposed_action") return "POL";
  if (event?.stream_id === "runtime.diagnostics" || event?.kind === "diagnostic_event") return "DIAG";
  return "EVT";
}

function compactEvent(event) {
  if (!event) return null;
  const base = {
    kind: event.kind,
    schema_id: event.schema_id,
    stream_id: event.stream_id,
    event_id: event.event_id,
    semantic_type: event.semantic_type,
    source_system: event.source_system || event.source,
    event_time_ns: event.event_time_ns ?? event.time?.event_time_ns,
    clock_domain: event.clock_domain || event.time?.clock_domain,
    frame_id: event.frame_id,
    payload_summary: event.payload_summary,
    metadata: event.metadata,
    attributes: event.attributes,
  };
  return Object.fromEntries(Object.entries(base).filter(([, value]) => value !== undefined));
}

function latestEventIndex(streamId) {
  for (let index = state.events.length - 1; index >= 0; index -= 1) {
    const event = state.events[index];
    if (!streamId || event.stream_id === streamId || (streamId === "runtime.diagnostics" && event.kind === "diagnostic_event")) {
      return index;
    }
  }
  return -1;
}

function selectedEventEntry() {
  const selected = Number.isInteger(state.selectedEventIndex) ? state.selectedEventIndex : -1;
  const index = selected >= 0 && selected < state.events.length ? selected : latestEventIndex();
  return index >= 0 ? { index, event: state.events[index] } : { index: -1, event: null };
}

function renderEventSummaryCell(label, value) {
  return `<div class="event-summary-cell"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function renderEventInspector() {
  if (!eventTimeline || !eventSummary || !eventLog || !eventInspectorStatus) return;
  const selected = selectedEventEntry();
  const recent = state.events.slice(-14).map((event, offset) => ({
    event,
    index: state.events.length - Math.min(14, state.events.length) + offset,
  }));

  eventTimeline.innerHTML = recent.map(({ event, index }) => {
    const active = index === selected.index ? " active" : "";
    const time = eventTimeSec(event).toFixed(2);
    const name = eventName(event);
    return `<button class="event-chip${active}" type="button" data-event-index="${index}" aria-label="Inspect ${name} at ${time}s"><strong>${escapeHtml(name)}</strong><span>${time}s</span></button>`;
  }).join("");

  if (!selected.event) {
    eventInspectorStatus.textContent = "waiting";
    eventSummary.innerHTML = "";
    eventLog.textContent = "No RoMi events emitted yet.";
    return;
  }

  const stream = selected.event.stream_id || selected.event.event_id || "diagnostic_event";
  eventInspectorStatus.textContent = stream;
  eventSummary.innerHTML = [
    renderEventSummaryCell("kind", selected.event.kind),
    renderEventSummaryCell("stream", stream),
    renderEventSummaryCell("time", `${eventTimeSec(selected.event).toFixed(2)}s`),
    renderEventSummaryCell("frame", selected.event.frame_id || selected.event.attributes?.stage || "n/a"),
  ].join("");
  eventLog.textContent = JSON.stringify(compactEvent(selected.event), null, 2);
}

function renderFrameMini() {
  const tf = latestEvent("robot.frames.tf");
  const frames = Array.isArray(tf?.payload_summary?.frames_sample)
    ? tf.payload_summary.frames_sample.slice(0, 4)
    : [
        { parent_frame_id: "map", child_frame_id: "odom" },
        { parent_frame_id: "odom", child_frame_id: "base_link" },
        { parent_frame_id: "base_link", child_frame_id: "camera" },
        { parent_frame_id: "base_link", child_frame_id: "tool0" },
      ];

  return `<div class="frame-mini">${frames.map((frame) => (
    `<div class="frame-edge"><strong>${escapeHtml(frame.parent_frame_id)}</strong><span>to</span><strong>${escapeHtml(frame.child_frame_id)}</strong></div>`
  )).join("")}</div>`;
}

function renderPolicyActions() {
  const policyEvent = latestEvent("policy.proposed_action");
  const actions = Array.isArray(policyEvent?.payload_summary?.proposed_actions)
    ? policyEvent.payload_summary.proposed_actions
    : [
        { target: "base", action_type: "waiting_for_observation" },
        { target: "end_effector", action_type: "waiting_for_target" },
        { target: "gripper", action_type: "waiting_for_grasp" },
      ];

  return `<div class="policy-list">${actions.map((action) => (
    `<div class="policy-row"><span>${escapeHtml(action.target)}</span><strong>${escapeHtml(action.action_type)}</strong></div>`
  )).join("")}</div>`;
}

function latestPolicyObservationWindow() {
  const policyEvent = latestEvent("policy.proposed_action");
  const payloadWindow = policyEvent?.payload_summary?.observation_window;
  if (Array.isArray(payloadWindow) && payloadWindow.length) {
    return payloadWindow;
  }
  return policyObservationWindow(state.events, Math.round(state.elapsedSec * 1_000_000_000));
}

function renderPolicyObservationWindow(maxRows = 3) {
  const inputs = latestPolicyObservationWindow();
  const rows = inputs.slice(0, maxRows);
  const fresh = inputs.filter((input) => input.status === "fresh").length;
  return `<div class="policy-window">
    <div class="policy-window-heading">
      <span>observation window</span>
      <strong>${fresh}/${inputs.length} fresh</strong>
    </div>
    <div class="policy-window-list">${rows.map((input) => {
      const label = input.stream_id.replace("robot.", "").replace("policy.", "policy.");
      const age = input.age_ms === null || input.age_ms === undefined ? "missing" : `${Number(input.age_ms).toFixed(0)}ms`;
      return `<button class="policy-window-row ${escapeHtml(input.status)}" type="button" data-inspect-stream="${escapeHtml(input.stream_id)}">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(input.status)}</strong>
        <em>${escapeHtml(input.frame_id || age)}</em>
      </button>`;
    }).join("")}</div>
  </div>`;
}

function safetyReport() {
  const policyEvent = latestEvent("policy.proposed_action");
  const payload = policyEvent?.payload_summary || {};
  const actions = Array.isArray(payload.proposed_actions) ? payload.proposed_actions : [];
  const boundary = payload.safety_boundary || {};
  return {
    schema_version: "0.1.0",
    report_kind: "romi.safety_authority_report",
    stage: currentStage(clamp(state.elapsedSec / state.durationSec)),
    clock_domain: "sim_time",
    policy_stream: "policy.proposed_action",
    policy_authority: boundary.policy_authority || "proposed_only",
    actuator_authority: boundary.actuator_authority || "none",
    command_stream_emitted: Boolean(boundary.command_stream_emitted),
    promotion_required: boundary.promotion_required || "external_supervisor",
    blocked_reason: boundary.blocked_reason || "proposal_not_actuator_authority",
    policy_samples: state.streamCounts["policy.proposed_action"] || 0,
    proposed_actions: actions.map((action) => ({
      target: action.target,
      action_type: action.action_type,
      authority: action.authority,
      blocked: true,
      reason: boundary.blocked_reason || "proposal_not_actuator_authority",
    })),
  };
}

function renderSafetyBoundary() {
  const report = safetyReport();
  const actions = report.proposed_actions.length
    ? report.proposed_actions
    : [
        { target: "base", action_type: "waiting_for_policy", reason: "no_policy_sample" },
        { target: "end_effector", action_type: "waiting_for_policy", reason: "no_policy_sample" },
        { target: "gripper", action_type: "waiting_for_policy", reason: "no_policy_sample" },
      ];
  return `${renderKeyValues([
    ["policy stream", report.policy_stream],
    ["policy authority", report.policy_authority],
    ["actuator authority", report.actuator_authority],
    ["command stream", report.command_stream_emitted ? "emitted" : "not_emitted"],
  ])}<div class="safety-boundary">
    <div class="authority-lane">
      <div class="authority-node"><span>proposal</span><strong>${escapeHtml(report.policy_authority)}</strong></div>
      <span class="authority-arrow">blocked</span>
      <div class="authority-node"><span>actuator</span><strong>${escapeHtml(report.actuator_authority)}</strong></div>
    </div>
    <div class="safety-list">${actions.map((action) => (
      `<div class="safety-row"><span>${escapeHtml(action.target)}.${escapeHtml(action.action_type)}</span><strong>${escapeHtml(action.reason)}</strong></div>`
    )).join("")}</div>
  </div>${renderKeyValues([
    ["promotion", report.promotion_required],
    ["samples", report.policy_samples],
  ])}`;
}

function datasetStreamCounts() {
  return Object.fromEntries(streams.map((stream) => [stream, state.streamCounts[stream] || 0]));
}

function datasetObservationWindow() {
  return [...policyInputStreams, "policy.proposed_action"].map((streamId) => {
    const event = latestEvent(streamId);
    const freshness = streamFreshness(streamId);
    return {
      stream_id: streamId,
      present: Boolean(event),
      event_time_sec: event ? Number(eventTimeSec(event).toFixed(3)) : null,
      frame_id: event?.frame_id || null,
      status: freshness.status,
    };
  });
}

function datasetReport() {
  const diagnostics = state.events.filter((event) => event.kind === "diagnostic_event").length;
  const streamCounts = datasetStreamCounts();
  const observationWindow = datasetObservationWindow();
  const availableWindowStreams = observationWindow.filter((stream) => stream.present).length;
  return {
    schema_version: "0.1.0",
    report_kind: "romi.browser_dataset_report",
    episode_id: state.scenario?.scenario_id || "romi_2d_sim_episode",
    scenario_id: state.scenario?.scenario_id || null,
    source_system: "romi_2d_sim",
    clock_domain: "sim_time",
    generated_at_sim_time_sec: Number(state.elapsedSec.toFixed(3)),
    stage: currentStage(clamp(state.elapsedSec / state.durationSec)),
    duration_sec: Number(state.durationSec.toFixed(3)),
    samples: state.events.length,
    stream_counts: streamCounts,
    observation_window: {
      available_streams: availableWindowStreams,
      required_streams: observationWindow.length,
      streams: observationWindow,
    },
    diagnostics: {
      events: diagnostics,
      latest: latestEvent("runtime.diagnostics")?.event_id || null,
    },
    policy: {
      stream_id: "policy.proposed_action",
      samples: streamCounts["policy.proposed_action"] || 0,
      authority: "proposed_only",
      actuator_authority: "none",
    },
    safety: safetyReport(),
    replay: {
      seekable: true,
      buffered_events: state.events.length,
      export_format: "jsonl_prototype",
    },
  };
}

function datasetReportMarkdown() {
  const report = datasetReport();
  const streamRows = Object.entries(report.stream_counts)
    .map(([stream, count]) => `| ${stream} | ${count} |`)
    .join("\n");
  const windowRows = report.observation_window.streams
    .map((stream) => `| ${stream.stream_id} | ${stream.present ? "yes" : "no"} | ${stream.status} | ${stream.frame_id || "n/a"} |`)
    .join("\n");
  return [
    `# RoMi Dataset Report: ${report.episode_id}`,
    "",
    `- source: ${report.source_system}`,
    `- clock: ${report.clock_domain} @ ${report.generated_at_sim_time_sec}s`,
    `- stage: ${report.stage}`,
    `- samples: ${report.samples}`,
    `- policy authority: ${report.policy.authority}`,
    `- actuator authority: ${report.policy.actuator_authority}`,
    "",
    "## Stream Counts",
    "",
    "| stream | samples |",
    "| --- | ---: |",
    streamRows,
    "",
    "## Observation Window",
    "",
    "| stream | present | freshness | frame |",
    "| --- | --- | --- | --- |",
    windowRows,
  ].join("\n");
}

function exportDatasetReport() {
  const blob = new Blob([datasetReportMarkdown() + "\n"], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${state.scenario?.scenario_id || "romi-2d-sim"}-dataset-report.md`;
  link.click();
  URL.revokeObjectURL(url);
}

function renderDatasetGrid() {
  const report = datasetReport();
  const latest = latestEvent();
  const latestStream = latest?.stream_id || latest?.event_id || "none";
  const preview = datasetReportMarkdown().split("\n").slice(0, 18).join("\n");

  return `<div class="dataset-grid">
    <div class="dataset-cell"><span>samples</span><strong>${report.samples}</strong></div>
    <div class="dataset-cell"><span>window streams</span><strong>${report.observation_window.available_streams}/${report.observation_window.required_streams}</strong></div>
    <div class="dataset-cell"><span>policy samples</span><strong>${report.policy.samples}</strong></div>
    <div class="dataset-cell"><span>diagnostics</span><strong>${report.diagnostics.events}</strong></div>
  </div>${renderKeyValues([
    ["episode", report.episode_id],
    ["latest", latestStream],
    ["authority", report.policy.authority],
  ])}<div class="dataset-report">
    <div class="dataset-actions">
      <span>dataset-report.md</span>
      <button class="inline-button" type="button" data-export-dataset-report>Export</button>
    </div>
    <pre class="dataset-report-preview">${escapeHtml(preview)}</pre>
  </div>`;
}

function renderModeView(progress) {
  const mode = displayMode(progress);
  const statusLabels = {
    live: "Live Sim",
    replay: "Replay",
    policy: "Policy",
    safety: "Safety",
    dataset: "Dataset",
  };

  modeStatus.textContent = statusLabels[mode] || "Live Sim";
  for (const button of modeButtons) {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  }

  if (mode === "live") {
    modeView.innerHTML = `${stageTimeline(progress)}${renderFreshness([
      "robot.camera.rgb",
      "robot.camera.depth",
      "robot.joints.state",
      "robot.base.odom",
    ])}`;
    return;
  }

  if (mode === "replay") {
    modeView.innerHTML = `${renderKeyValues([
      ["clock domain", "sim_time"],
      ["buffered events", state.events.length],
      ["replay shape", progress > 0.42 ? "active" : "priming"],
    ])}${renderFrameMini()}`;
    return;
  }

  if (mode === "policy") {
    const policyEvent = latestEvent("policy.proposed_action");
    const latency = Number(policyEvent?.payload_summary?.inference_latency_ms ?? 0);
    modeView.innerHTML = `${renderPolicyActions()}${renderPolicyObservationWindow()}${renderKeyValues([
      ["authority", "proposed_only"],
      ["latency", latency > 0 ? `${latency.toFixed(2)}ms` : "waiting"],
    ])}`;
    return;
  }

  if (mode === "safety") {
    modeView.innerHTML = renderSafetyBoundary();
    return;
  }

  modeView.innerHTML = renderDatasetGrid();
}

function updateSeekUi(progress) {
  if (!seekControl || !seekValue) return;
  seekControl.value = String(Math.round(clamp(progress) * 1000));
  seekValue.textContent = `${state.elapsedSec.toFixed(2)}s`;
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
    const row = document.createElement("button");
    row.className = "stream-row";
    row.type = "button";
    row.dataset.inspectStream = stream;
    row.setAttribute("aria-label", `Inspect latest ${stream} event`);
    row.classList.toggle("active", selectedEventEntry().event?.stream_id === stream);
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
  for (const [nodeId, node] of Object.entries(graphNodes)) {
    const selected = nodeId === state.selectedGraphNode;
    node.classList.toggle("selected", selected);
    node.querySelector("button")?.setAttribute("aria-pressed", selected ? "true" : "false");
  }

  renderModeView(progress);
  updateSeekUi(progress);
  renderGraphDetail(progress);
  renderEventInspector();
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
  state.selectedEventIndex = null;
  render();
}

function seekCapture(elapsedSec) {
  if (!state.ready || state.error) {
    return { ready: false, error: state.error || "scenario_not_ready" };
  }

  const targetSec = clamp(Number(elapsedSec) || 0, 0, state.durationSec);
  if (targetSec < state.elapsedSec || state.running) reset();
  state.running = false;

  while (state.sampleIndex === 0 || state.sampleIndex / state.rateHz <= targetSec) {
    state.elapsedSec = Math.min(state.durationSec, state.sampleIndex / state.rateHz);
    emitEvents(clamp(state.elapsedSec / state.durationSec));
    if (state.elapsedSec >= state.durationSec) break;
  }

  state.elapsedSec = targetSec;
  if (state.selectedEventIndex !== null && state.selectedEventIndex >= state.events.length) {
    state.selectedEventIndex = null;
  }
  render();
  return {
    ready: true,
    elapsed_sec: state.elapsedSec,
    stage: currentStage(clamp(state.elapsedSec / state.durationSec)),
    events: state.events.length,
  };
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

function latestEvent(streamId) {
  for (let index = state.events.length - 1; index >= 0; index -= 1) {
    const event = state.events[index];
    if (!streamId || event.stream_id === streamId) return event;
  }
  return null;
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
for (const button of modeButtons) {
  button.addEventListener("click", () => setMode(button.dataset.mode));
}
streamList.addEventListener("click", (event) => {
  const target = event.target.closest("[data-inspect-stream]");
  if (!target) return;
  selectLatestStreamEvent(target.dataset.inspectStream);
});
document.querySelector(".graph-list")?.addEventListener("click", (event) => {
  const target = event.target.closest("[data-graph-node]");
  if (!target) return;
  selectGraphNode(target.dataset.graphNode);
});
graphDetail?.addEventListener("click", (event) => {
  const target = event.target.closest("[data-inspect-stream]");
  if (!target) return;
  selectLatestStreamEvent(target.dataset.inspectStream);
});
seekControl.addEventListener("input", () => {
  const progress = clamp(Number(seekControl.value) / 1000);
  seekToSeconds(progress * state.durationSec, "replay");
});
modeView.addEventListener("click", (event) => {
  const exportTarget = event.target.closest("[data-export-dataset-report]");
  if (exportTarget) {
    exportDatasetReport();
    return;
  }
  const inspectTarget = event.target.closest("[data-inspect-stream]");
  if (inspectTarget) {
    selectLatestStreamEvent(inspectTarget.dataset.inspectStream);
    return;
  }
  const target = event.target.closest("[data-seek-progress]");
  if (!target) return;
  const progress = clamp(Number(target.dataset.seekProgress));
  seekToSeconds(progress * state.durationSec, "replay");
});
eventTimeline.addEventListener("click", (event) => {
  const target = event.target.closest("[data-event-index]");
  if (!target) return;
  selectEventIndex(Number(target.dataset.eventIndex));
});

window.romiCapture = {
  ready: () => Boolean(state.ready && !state.error),
  error: () => state.error,
  duration: () => state.durationSec,
  seek: seekCapture,
  seekToSeconds,
  setMode,
  datasetReport,
  datasetReportMarkdown,
  safetyReport,
  selectGraphNode,
  selectLatestStreamEvent,
  latestEvent,
};

loadScenario()
  .then(reset)
  .catch((error) => {
    state.error = error.message;
    render();
  });
window.requestAnimationFrame(tick);
