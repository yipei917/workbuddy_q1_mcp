#!/usr/bin/env python3
"""行走链路：SSH 登录 Q1，调用 ROS2 PlayMove 服务。

合并自 workbuddy-q1-mcp/robot_control.py，逻辑保持不变。
"""

from __future__ import annotations

import os
import subprocess
from typing import Literal

Direction = Literal[
    "forward",
    "backward",
    "left",
    "right",
    "turn_left",
    "turn_right",
    "stop",
]

DIRECTION_CODE: dict[str, int] = {
    "forward": 0,
    "backward": 1,
    "left": 2,
    "right": 3,
    "turn_left": 4,
    "turn_right": 5,
    "stop": 255,
}

DEFAULT_HOST = os.environ.get("QIYUAN_ROBOT_HOST", "192.168.0.181")
DEFAULT_USER = os.environ.get("QIYUAN_ROBOT_USER", "run")
DEFAULT_KEY = os.environ.get(
    "QIYUAN_ROBOT_SSH_KEY",
    os.path.expanduser("~/.ssh/id_ed25519_q1"),
)
DEFAULT_TIMEOUT = float(os.environ.get("QIYUAN_ROBOT_SSH_TIMEOUT", "40"))
REMOTE_HELPER = os.environ.get("QIYUAN_PLAY_MOVE_SCRIPT", "/home/run/bin/q1_play_move.sh")


def _ssh_base() -> list[str]:
    return [
        "ssh",
        "-i",
        DEFAULT_KEY,
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={int(min(DEFAULT_TIMEOUT, 10))}",
        f"{DEFAULT_USER}@{DEFAULT_HOST}",
    ]


def ssh_run(remote_command: str, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    timeout = DEFAULT_TIMEOUT if timeout is None else timeout
    return subprocess.run(
        [*_ssh_base(), remote_command],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def robot_ping() -> str:
    result = ssh_run(
        "hostname; test -x /home/run/bin/q1_play_move.sh && echo helper=ok; "
        "bash -c 'source /opt/ros/humble/setup.bash; source /robot/software/app_proxy/setup.bash; "
        "ros2 service list' | grep -E 'PlayMove|SetMcAction' | head -5",
        timeout=25,
    )
    if result.returncode != 0:
        return f"SSH/机器人检查失败:\n{result.stderr or result.stdout}"
    return f"机器人可达 ({DEFAULT_USER}@{DEFAULT_HOST})\n{result.stdout.strip()}"


def play_move(direction: Direction, distance_m: float = 0.2) -> str:
    if direction not in DIRECTION_CODE:
        return f"不支持的方向: {direction}"
    code = DIRECTION_CODE[direction]
    if direction == "stop":
        distance_m = 0.0
    else:
        distance_m = max(0.05, min(float(distance_m), 0.5))

    result = ssh_run(f"{REMOTE_HELPER} {code} {distance_m}", timeout=35)
    out = ((result.stdout or "") + (result.stderr or "")).strip()
    ok = "success=True" in out.replace(" ", "")
    action = "停止" if direction == "stop" else f"{direction} ~{distance_m}m"
    if ok:
        return f"已下发 PlayMove: {action}\n{out[-800:]}"
    return f"PlayMove 失败 (exit={result.returncode}): {action}\n{out[-1200:]}"
