#!/usr/bin/env python3
"""语音链路：SSH 登录 Q1，调用 ROS2 PlayTts / StopTtsTraceId。"""

from __future__ import annotations

import os
import shlex
import uuid

from robot_move import ssh_run

MAX_CHARS = int(os.environ.get("QIYUAN_SPEAK_MAX_CHARS", "120"))
DEFAULT_PRIORITY = int(os.environ.get("QIYUAN_SPEAK_PRIORITY", "6"))
DEFAULT_DOMAIN = os.environ.get("QIYUAN_SPEAK_DOMAIN", "workbuddy_mcp")
SETUP = (
    "source /opt/ros/humble/setup.bash; "
    "source /robot/software/app_proxy/setup.bash; "
)


def _trim(text: str) -> str:
    clean = " ".join(str(text or "").strip().split())
    if len(clean) <= MAX_CHARS:
        return clean
    return clean[: max(MAX_CHARS - 1, 1)].rstrip() + "…"


def _yaml_string(value: str) -> str:
    # Match Buddy ros2 adapter quoting for ros2 service call YAML.
    escaped = (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", " ")
    )
    return f'"{escaped}"'


def robot_speak(text: str, *, interrupt: bool = True) -> str:
    """让机器人播报文本。成功只表示已接受请求，不代表播报结束。"""
    spoken = _trim(text)
    if not spoken:
        return "拒绝播报：文本为空。"
    trace_id = f"mcp-speak-{uuid.uuid4().hex[:10]}"
    request = (
        "{header: {header: {stamp: {sec: 0, nanosec: 0}}}, "
        f"tts_req: {{text: {_yaml_string(spoken)}, priority_level: {{value: {DEFAULT_PRIORITY}}}, "
        f"priority_weight: 0, domain: {_yaml_string(DEFAULT_DOMAIN)}, "
        f"trace_id: {_yaml_string(trace_id)}, is_interrupted: {str(bool(interrupt)).lower()}}}}}"
    )
    cmd = (
        SETUP
        + "timeout --kill-after=2s 20s ros2 service call "
        "/aimdk_5Fmsgs/srv/PlayTts aimdk_msgs/srv/PlayTts "
        + shlex.quote(request)
    )
    result = ssh_run(cmd, timeout=35)
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        return f"播报失败（exit={result.returncode}）：\n{out[-800:]}"
    if "is_success=True" not in out and "is_success: true" not in out.lower():
        return f"播报未确认成功：\n{out[-800:]}"
    return f"已下发播报（trace_id={trace_id}）：{spoken}"


def robot_stop_speak(trace_id: str = "") -> str:
    """停止当前 TTS。若提供 trace_id 则停指定会话，否则尝试 StopTts。"""
    tid = str(trace_id or "").strip()
    if tid:
        request = (
            "{header: {header: {stamp: {sec: 0, nanosec: 0}}}, "
            f"trace_id: {_yaml_string(tid)}}}"
        )
        cmd = (
            SETUP
            + "timeout --kill-after=2s 12s ros2 service call "
            "/aimdk_5Fmsgs/srv/StopTtsTraceId aimdk_msgs/srv/StopTtsTraceId "
            + shlex.quote(request)
        )
    else:
        request = "{header: {header: {stamp: {sec: 0, nanosec: 0}}}}"
        cmd = (
            SETUP
            + "timeout --kill-after=2s 12s ros2 service call "
            "/aimdk_5Fmsgs/srv/StopTts aimdk_msgs/srv/StopTts "
            + shlex.quote(request)
        )
    result = ssh_run(cmd, timeout=20)
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        return f"停止播报失败（exit={result.returncode}）：\n{out[-800:]}"
    return "已请求停止播报。"
