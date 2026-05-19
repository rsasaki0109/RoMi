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

const state = {
  running: false,
  lastFrameMs: 0,
  elapsedSec: 0,
  durationSec: 16,
  sampleIndex: 0,
  events: [],
  streamCounts: Object.fromEntries(streams.map((stream) => [stream, 0])),
  trace: [],
  objectHeld: false,
  objectPlaced: false,
};

const colors = {
  bg: "#10181e",
  grid: "#20303a",
  field: "#132028",
  cyan: "#38d9ef",
  green: "#8bd450",
  amber: "#ffbf6b",
  purple: "#b7a2ff",
  rose: "#f58aa5",
  text: "#edf5f8",
  muted: "#94a9b5",
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

function robotPose(progress) {
  const nav = ease(clamp(progress / 0.58));
  const x = lerp(140, 625, nav);
  const y = 392 - 120 * Math.sin(nav * Math.PI);
  const yaw = lerp(-0.05, -0.65, nav);
  return { x, y, yaw };
}

function armReach(progress) {
  return ease(clamp((progress - 0.56) / 0.22));
}

function placeReach(progress) {
  return ease(clamp((progress - 0.78) / 0.14));
}

function currentStage(progress) {
  if (progress < 0.05) return "initialize";
  if (progress < 0.58) return "navigate";
  if (progress < 0.72) return "reach";
  if (progress < 0.80) return "grasp";
  if (progress < 0.92) return "place";
  return "report";
}

function worldToRomi(pose) {
  return {
    x: (pose.x - 140) / 300,
    y: (392 - pose.y) / 300,
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
    source_system: "romi_turtlesim_demo",
    source_topic: null,
    source_message_type: sourceMessageType,
    event_time_ns: Math.round(state.elapsedSec * 1_000_000_000),
    clock_domain: "sim_time",
    frame_id: frameId,
    payload_summary: payloadSummary,
    metadata: {
      source: "turtlesim_demo",
      sample_index: state.streamCounts[streamId],
    },
  };
}

function emitEvents(progress) {
  const pose = robotPose(progress);
  const worldPose = worldToRomi(pose);
  const reach = armReach(progress);
  const placed = progress > 0.88;
  const holding = progress > 0.70 && !placed;

  const events = [
    createEvent("robot.camera.rgb", {
      width: 160,
      height: 90,
      encoding: "rgb8",
      target_visible: !placed,
      object_state: placed ? "placed" : holding ? "held" : "on_table",
    }, "camera_color_optical_frame", "rgb_image", "romi.robotics.ImageSummary"),
    createEvent("robot.camera.depth", {
      width: 160,
      height: 90,
      encoding: "16UC1",
      target_depth_mm: holding ? 410 : 620,
    }, "camera_depth_optical_frame", "depth_image", "romi.robotics.ImageSummary"),
    createEvent("robot.camera.info", {
      width: 160,
      height: 90,
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
      linear: { x: progress < 0.58 ? 0.35 : 0, y: 0, z: 0 },
      angular: { x: 0, y: 0, z: progress < 0.58 ? -0.15 : 0 },
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
    }, "map->odom", "transform_tree", "romi.robotics.TransformTreeSummary"),
  ];

  if (state.sampleIndex % 12 === 0) {
    events.push(createEvent("task.goal", {
      position: { x: 1.6, y: 0, z: 0 },
      orientation: { x: 0, y: 0, z: 0, w: 1 },
      target_object: "orange_cube",
    }, "map", "task_goal", "romi.robotics.PoseGoalSummary"));
  }

  if (state.sampleIndex % 18 === 0 || progress > 0.68) {
    events.push(createEvent("policy.proposed_action", {
      policy_id: "mock_nav_manip_policy",
      proposed_actions: [
        { target: "base", action_type: "hold_or_navigate", authority: "proposed_only" },
        { target: "end_effector", action_type: holding ? "carry_object" : "reach_target", authority: "proposed_only" },
        { target: "gripper", action_type: holding ? "hold_closed" : "prepare_grasp", authority: "proposed_only" },
      ],
      inference_latency_ms: 1.4 + 0.5 * Math.sin(progress * Math.PI * 2),
      metadata: { authority: "proposed_only" },
    }, "base_link", "command", "romi.ml.PolicyProposedAction"));
  }

  if (state.sampleIndex % 24 === 0) {
    state.streamCounts["runtime.diagnostics"] += 1;
    events.push({
      schema_version: "0.1.0",
      schema_id: "romi.core.diagnostic_event/0.1.0",
      kind: "diagnostic_event",
      event_id: `turtlesim_runtime_${state.streamCounts["runtime.diagnostics"]}`,
      time: { event_time_ns: Math.round(state.elapsedSec * 1_000_000_000), clock_domain: "sim_time" },
      severity: "info",
      source: "romi_turtlesim_demo",
      category: "runtime",
      message: "Simulator emitted synchronized navigation/manipulation step.",
      attributes: { stage: currentStage(progress), stream_count: streams.length },
    });
  }

  state.events.push(...events);
  state.sampleIndex += 1;
  state.trace.push({ x: pose.x, y: pose.y });
  if (state.trace.length > 260) state.trace.shift();
}

function drawGrid() {
  ctx.fillStyle = colors.field;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = colors.grid;
  ctx.lineWidth = 1;
  for (let x = 0; x < canvas.width; x += 32) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += 32) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }
}

function drawWorkspace(progress) {
  ctx.fillStyle = "#263923";
  ctx.strokeStyle = colors.green;
  roundRect(650, 240, 215, 160, 10, true, true);
  ctx.fillStyle = colors.green;
  ctx.font = "14px sans-serif";
  ctx.fillText("manipulation zone", 670, 266);

  ctx.fillStyle = "#33462f";
  ctx.strokeStyle = "#b2f07b";
  roundRect(724, 310, 88, 56, 8, true, true);
  ctx.fillStyle = colors.text;
  ctx.font = "12px sans-serif";
  ctx.fillText("place bin", 744, 342);

  const placed = progress > 0.88;
  if (!placed) {
    const object = objectPosition(progress);
    ctx.fillStyle = colors.amber;
    ctx.strokeStyle = "#ffe3b6";
    roundRect(object.x - 13, object.y - 13, 26, 26, 5, true, true);
  }
}

function objectPosition(progress) {
  const pose = robotPose(progress);
  const reach = armReach(progress);
  const place = placeReach(progress);
  const table = { x: 712, y: 292 };
  const carried = { x: pose.x + 72, y: pose.y - 34 };
  const bin = { x: 768, y: 320 };
  if (progress < 0.72) return table;
  if (progress < 0.86) {
    return {
      x: lerp(table.x, carried.x, reach),
      y: lerp(table.y, carried.y, reach),
    };
  }
  return {
    x: lerp(carried.x, bin.x, place),
    y: lerp(carried.y, bin.y, place),
  };
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
  const reach = armReach(progress);
  const holding = progress > 0.70 && progress < 0.88;

  ctx.save();
  ctx.translate(pose.x, pose.y);
  ctx.rotate(pose.yaw);
  ctx.fillStyle = "#1e323a";
  ctx.strokeStyle = colors.cyan;
  ctx.lineWidth = 3;
  roundRect(-34, -23, 68, 46, 12, true, true);

  ctx.fillStyle = colors.cyan;
  ctx.beginPath();
  ctx.moveTo(28, 0);
  ctx.lineTo(10, -10);
  ctx.lineTo(10, 10);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = colors.text;
  ctx.font = "12px sans-serif";
  ctx.fillText("RoMi", -16, 4);
  ctx.restore();

  const shoulder = { x: pose.x + 28, y: pose.y - 9 };
  const elbow = { x: lerp(shoulder.x + 42, 694, reach), y: lerp(shoulder.y - 28, 278, reach) };
  const wrist = { x: lerp(elbow.x + 38, 722, reach), y: lerp(elbow.y - 10, 288, reach) };
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
  roundRect(24, 22, 360, 86, 8, true, true);
  ctx.fillStyle = colors.text;
  ctx.font = "20px sans-serif";
  ctx.fillText("turtlesim-style RoMi source", 44, 55);
  ctx.fillStyle = colors.muted;
  ctx.font = "13px sans-serif";
  ctx.fillText("navigation + manipulation, ROS2-free", 44, 80);
  ctx.fillText(`stage: ${currentStage(progress)}`, 44, 100);
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
  const progress = clamp(state.elapsedSec / state.durationSec);
  drawGrid();
  drawWorkspace(progress);
  drawTrace();
  drawRobot(progress);
  drawHud(progress);
  updateInspector(progress);
}

function updateInspector(progress) {
  stageValue.textContent = currentStage(progress);
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

  const recent = state.events.slice(-6).map((event) => `${event.kind} ${event.stream_id || event.event_id}`);
  eventLog.textContent = recent.join("\n");
}

function tick(frameMs) {
  if (!state.lastFrameMs) state.lastFrameMs = frameMs;
  const deltaSec = Math.min(0.05, (frameMs - state.lastFrameMs) / 1000);
  state.lastFrameMs = frameMs;

  if (state.running) {
    state.elapsedSec = Math.min(state.durationSec, state.elapsedSec + deltaSec);
    if (state.sampleIndex === 0 || state.elapsedSec * 12 >= state.sampleIndex) {
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
  link.download = "romi-turtlesim-demo-events.jsonl";
  link.click();
  URL.revokeObjectURL(url);
}

startButton.addEventListener("click", () => {
  if (state.elapsedSec >= state.durationSec) reset();
  state.running = true;
});
pauseButton.addEventListener("click", () => {
  state.running = false;
});
resetButton.addEventListener("click", reset);
exportButton.addEventListener("click", exportJsonl);

reset();
window.requestAnimationFrame(tick);
