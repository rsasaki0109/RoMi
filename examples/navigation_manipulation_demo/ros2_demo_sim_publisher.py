#!/usr/bin/env python3
"""Scripted ROS2 navigation + manipulation demo publisher.

This node publishes a small synthetic mobile-manipulator episode to common ROS2
topics. It is intentionally simple, but the RoMi bridge records its real ROS2
messages and downstream tools consume those RoMi artifacts.
"""

from __future__ import annotations

import argparse
import math
from typing import Sequence

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped, Quaternion, TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image, JointState
from tf2_msgs.msg import TFMessage


def quaternion_from_yaw(yaw: float) -> Quaternion:
    msg = Quaternion()
    msg.z = math.sin(yaw / 2.0)
    msg.w = math.cos(yaw / 2.0)
    return msg


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def lerp(a: float, b: float, value: float) -> float:
    return a + (b - a) * value


class DemoSimPublisher(Node):
    def __init__(self, duration_sec: float, rate_hz: float) -> None:
        super().__init__("romi_demo_sim_publisher")
        self.duration_sec = duration_sec
        self.rate_hz = rate_hz
        self.start_ns = self.get_clock().now().nanoseconds
        self.goal_sent = False
        self.frame_index = 0

        self.rgb_pub = self.create_publisher(Image, "/camera/color/image_raw", 10)
        self.depth_pub = self.create_publisher(Image, "/camera/depth/image_raw", 10)
        self.camera_info_pub = self.create_publisher(CameraInfo, "/camera/color/camera_info", 10)
        self.joint_pub = self.create_publisher(JointState, "/joint_states", 10)
        self.odom_pub = self.create_publisher(Odometry, "/odom", 10)
        self.tf_pub = self.create_publisher(TFMessage, "/tf", 10)
        static_tf_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.static_tf_pub = self.create_publisher(TFMessage, "/tf_static", static_tf_qos)
        self.goal_pub = self.create_publisher(PoseStamped, "/goal_pose", 10)

        self.timer = self.create_timer(1.0 / rate_hz, self.tick)
        self.publish_static_tf()

    def progress(self) -> float:
        elapsed = (self.get_clock().now().nanoseconds - self.start_ns) / 1_000_000_000.0
        return max(0.0, min(1.0, elapsed / self.duration_sec))

    def pose(self, progress: float) -> tuple[float, float, float]:
        p = ease(progress)
        x = lerp(0.0, 1.6, p)
        y = 0.45 * math.sin(p * math.pi)
        yaw = lerp(0.0, -0.72, p)
        return x, y, yaw

    def tick(self) -> None:
        now = self.get_clock().now()
        progress = self.progress()
        x, y, yaw = self.pose(progress)

        self.publish_goal(now)
        self.publish_odom(now, x, y, yaw)
        self.publish_tf(now, x, y, yaw, progress)
        self.publish_joints(now, progress)
        self.publish_camera(now, progress)

        self.frame_index += 1
        if progress >= 1.0:
            self.get_logger().info("Demo simulation complete")
            rclpy.shutdown()

    def publish_goal(self, now: rclpy.time.Time) -> None:
        # Publish periodically so late subscribers still see the task intent.
        if self.frame_index % max(1, int(self.rate_hz)) != 0 and self.goal_sent:
            return
        msg = PoseStamped()
        msg.header.stamp = now.to_msg()
        msg.header.frame_id = "map"
        msg.pose.position.x = 1.6
        msg.pose.position.y = 0.0
        msg.pose.position.z = 0.0
        msg.pose.orientation.w = 1.0
        self.goal_pub.publish(msg)
        self.goal_sent = True

    def publish_odom(self, now: rclpy.time.Time, x: float, y: float, yaw: float) -> None:
        msg = Odometry()
        msg.header.stamp = now.to_msg()
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation = quaternion_from_yaw(yaw)
        msg.twist.twist.linear.x = 0.35 * (1.0 - self.progress())
        msg.twist.twist.angular.z = -0.2
        self.odom_pub.publish(msg)

    def publish_tf(self, now: rclpy.time.Time, x: float, y: float, yaw: float, progress: float) -> None:
        transforms = [
            self.transform(now, "map", "odom", 0.0, 0.0, 0.0, 0.0),
            self.transform(now, "odom", "base_link", x, y, 0.0, yaw),
            self.transform(now, "arm_base_link", "tool0", 0.25 + 0.32 * ease(progress), -0.04, 0.28, -0.35 * ease(progress)),
        ]
        msg = TFMessage()
        msg.transforms = transforms
        self.tf_pub.publish(msg)

    def publish_static_tf(self) -> None:
        now = self.get_clock().now()
        msg = TFMessage()
        msg.transforms = [
            self.transform(now, "base_link", "camera_color_optical_frame", 0.28, 0.0, 0.42, 0.0),
            self.transform(now, "base_link", "camera_depth_optical_frame", 0.28, 0.0, 0.42, 0.0),
            self.transform(now, "base_link", "arm_base_link", 0.22, 0.0, 0.28, 0.0),
        ]
        self.static_tf_pub.publish(msg)

    def transform(
        self,
        now: rclpy.time.Time,
        parent: str,
        child: str,
        x: float,
        y: float,
        z: float,
        yaw: float,
    ) -> TransformStamped:
        transform = TransformStamped()
        transform.header.stamp = now.to_msg()
        transform.header.frame_id = parent
        transform.child_frame_id = child
        transform.transform.translation.x = x
        transform.transform.translation.y = y
        transform.transform.translation.z = z
        transform.transform.rotation = quaternion_from_yaw(yaw)
        return transform

    def publish_joints(self, now: rclpy.time.Time, progress: float) -> None:
        msg = JointState()
        msg.header.stamp = now.to_msg()
        msg.name = ["shoulder_pan", "shoulder_lift", "elbow", "wrist", "gripper_left", "gripper_right"]
        reach = ease(max(0.0, (progress - 0.55) / 0.35))
        msg.position = [
            -0.25 * reach,
            -0.55 * reach,
            0.85 * reach,
            -0.35 * reach,
            0.04 * (1.0 - reach),
            0.04 * (1.0 - reach),
        ]
        msg.velocity = [0.0 for _ in msg.name]
        msg.effort = [0.0 for _ in msg.name]
        self.joint_pub.publish(msg)

    def publish_camera(self, now: rclpy.time.Time, progress: float) -> None:
        height, width = 90, 160
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        rgb[:, :, 0] = 24
        rgb[:, :, 1] = 34
        rgb[:, :, 2] = 42

        target_x = int(112 - 46 * ease(progress))
        target_y = int(48 + 8 * math.sin(progress * math.pi))
        rgb[max(0, target_y - 9) : min(height, target_y + 9), max(0, target_x - 9) : min(width, target_x + 9)] = [255, 184, 107]
        rgb[8:14, 10 : int(10 + 120 * progress)] = [103, 232, 249]

        depth = np.full((height, width), int(1800 - 900 * ease(progress)), dtype=np.uint16)
        depth[max(0, target_y - 11) : min(height, target_y + 11), max(0, target_x - 11) : min(width, target_x + 11)] = 620

        self.rgb_pub.publish(self.image_msg(now, "camera_color_optical_frame", rgb, "rgb8"))
        self.depth_pub.publish(self.image_msg(now, "camera_depth_optical_frame", depth, "16UC1"))
        self.camera_info_pub.publish(self.camera_info(now, width, height))

    def image_msg(self, now: rclpy.time.Time, frame_id: str, array: np.ndarray, encoding: str) -> Image:
        msg = Image()
        msg.header.stamp = now.to_msg()
        msg.header.frame_id = frame_id
        msg.height = int(array.shape[0])
        msg.width = int(array.shape[1])
        msg.encoding = encoding
        msg.is_bigendian = False
        msg.step = int(array.strides[0])
        msg.data = array.tobytes()
        return msg

    def camera_info(self, now: rclpy.time.Time, width: int, height: int) -> CameraInfo:
        msg = CameraInfo()
        msg.header.stamp = now.to_msg()
        msg.header.frame_id = "camera_color_optical_frame"
        msg.width = width
        msg.height = height
        msg.distortion_model = "plumb_bob"
        msg.k = [120.0, 0.0, width / 2.0, 0.0, 120.0, height / 2.0, 0.0, 0.0, 1.0]
        msg.p = [120.0, 0.0, width / 2.0, 0.0, 0.0, 120.0, height / 2.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        return msg


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish a scripted ROS2 navigation + manipulation demo")
    parser.add_argument("--duration-sec", type=float, default=5.5)
    parser.add_argument("--rate-hz", type=float, default=12.0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    rclpy.init()
    node = DemoSimPublisher(duration_sec=args.duration_sec, rate_hz=args.rate_hz)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
