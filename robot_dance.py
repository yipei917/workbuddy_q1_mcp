#!/usr/bin/env python3
"""动作链路：通过 AimRT HTTP RPC 调用启元 Q1 机器人的动作接口（不依赖 SSH）。

合并自 mcp-dance/robot_control.py，逻辑保持不变。
环境变量统一用 QIYUAN_ 前缀，对外函数返回中文可读字符串，便于直接作为 MCP 工具的输出。
"""

from __future__ import annotations

import http.client
import json
import os
from typing import Any, Callable

RPC_PATH = "/rpc/interface.ProductionTesterSrv/Call"
SERVICE_PREFIX = "/aimdk_5Fmsgs/srv/"
SUCCESS_CODE = 1000
MAX_RESPONSE_BYTES = 1_000_000

DEFAULT_HOST = os.environ.get("QIYUAN_ROBOT_HOST", "192.168.0.181")
DEFAULT_PORT = int(os.environ.get("QIYUAN_ROBOT_RPC_PORT", "50091"))
DEFAULT_TIMEOUT = float(os.environ.get("QIYUAN_ROBOT_RPC_TIMEOUT", "8"))

ACTION_TYPE_MOTION = 2
DANCE_WHITELIST: tuple[str, ...] = ("street_dance", "dance_a", "dance_b", "dance_c")

# 姿态/手势：部分不在 GetMotionList 里（如站起/折叠），用原生 skills.json 的 motion id。
POSTURE_FIXED_IDS: dict[str, int] = {
    "stand_up": 3045,  # 站起来
    "action_stow": 3057,  # 折叠 / tuck
    "lay_down": 3044,  # 躺下
    "lie_prone": 3060,  # 趴下
}
GESTURE_WHITELIST: tuple[str, ...] = (
    "wave_hand",
    "handshake",
    "fist_bump",
    "cheer_up",
    "stretch",
    "hug",
    "heart_gesture",
    "boxing",
)
POSTURE_ALIASES: dict[str, str] = {
    "fold": "action_stow",
    "fold_stow": "action_stow",
    "stow": "action_stow",
    "tuck": "action_stow",
    "折叠": "action_stow",
    "折叠起来": "action_stow",
    "收纳": "action_stow",
    "stand": "stand_up",
    "standup": "stand_up",
    "站起": "stand_up",
    "站起来": "stand_up",
    "wave": "wave_hand",
    "wave_hands": "wave_hand",
    "挥手": "wave_hand",
    "shake_hands": "handshake",
    "握手": "handshake",
}

_connection_factory: Callable[..., Any] = http.client.HTTPConnection


class RobotApiError(RuntimeError):
    """机器人连接、协议或业务请求失败。"""


def dance_enabled() -> bool:
    """动作总开关。只有显式设为 1 才允许触发动作；只读查询不受影响。"""
    return os.environ.get(
        "QIYUAN_ENABLE_DANCE", os.environ.get("ROBOT_ENABLE_DANCE", "")
    ) == "1"


def _rpc(service_type: str, data: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
    payload = {
        "service_name": f"{SERVICE_PREFIX}{service_type}",
        "service_type": service_type,
        "data": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    }
    connection = _connection_factory(
        DEFAULT_HOST, DEFAULT_PORT, timeout=DEFAULT_TIMEOUT if timeout is None else timeout
    )
    try:
        connection.request(
            "POST",
            RPC_PATH,
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RobotApiError("机器人响应过大")
        if response.status != 200:
            raise RobotApiError(f"机器人 HTTP 状态 {response.status}")
        envelope = json.loads(raw)
        if not isinstance(envelope, dict):
            raise RobotApiError("机器人返回的 RPC 封装格式不正确")
        if envelope.get("code") != SUCCESS_CODE:
            raise RobotApiError(
                f"机器人 RPC 拒绝请求：code={envelope.get('code')}, "
                f"data={str(envelope.get('data'))[:300]}"
            )
        result = envelope.get("data")
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise RobotApiError("机器人返回的业务数据格式不正确")
        return result
    except (OSError, TimeoutError, http.client.HTTPException, ValueError) as exc:
        raise RobotApiError(f"连接或解析机器人响应失败：{exc}") from exc
    finally:
        connection.close()


def _motion_list() -> list[dict[str, Any]]:
    result = _rpc("GetMotionList", {"motion_type": 0, "motion_list_type": 0})
    motions = result.get("motion_list")
    if not isinstance(motions, list):
        raise RobotApiError("动作列表响应缺少 motion_list")
    return [motion for motion in motions if isinstance(motion, dict)]


def _find_dance(motion_name: str) -> dict[str, Any] | None:
    """在机器人实时动作列表里定位舞蹈。动作 ID 一律以实时列表为准，不硬编码。"""
    for motion in _motion_list():
        if (
            motion.get("motion_name") == motion_name
            and motion.get("action_type") == ACTION_TYPE_MOTION
        ):
            return motion
    return None


def robot_status() -> str:
    """只读检查机器人是否可达，并汇总动作概览。"""
    try:
        motions = _motion_list()
    except RobotApiError as exc:
        return f"机器人不可达（{DEFAULT_HOST}:{DEFAULT_PORT}）：{exc}"
    dances = [
        motion
        for motion in motions
        if motion.get("action_type") == ACTION_TYPE_MOTION
        and motion.get("motion_name") in DANCE_WHITELIST
    ]
    names = "、".join(str(motion.get("motion_name")) for motion in dances) or "无"
    postures = "、".join(POSTURE_FIXED_IDS.keys())
    gestures = "、".join(GESTURE_WHITELIST)
    return "\n".join(
        [
            f"机器人可达：{DEFAULT_HOST}:{DEFAULT_PORT}",
            f"当前动作总数：{len(motions)}",
            f"白名单内舞蹈：{len(dances)} 个（{names}）",
            f"固定姿态：{postures}",
            f"手势白名单：{gestures}",
            f"动作总开关：{'已开启' if dance_enabled() else '未开启（需设置 QIYUAN_ENABLE_DANCE=1）'}",
        ]
    )


def list_motions() -> str:
    """只读列出机器人当前全部动作。"""
    try:
        motions = _motion_list()
    except RobotApiError as exc:
        return f"读取动作列表失败：{exc}"
    if not motions:
        return "机器人当前没有返回任何动作。"
    lines = [f"机器人当前共 {len(motions)} 个动作："]
    for motion in motions:
        name = motion.get("motion_name")
        if name in DANCE_WHITELIST:
            mark = "[舞蹈] "
        elif name in GESTURE_WHITELIST:
            mark = "[手势] "
        else:
            mark = "       "
        lines.append(
            f"{mark}{name} (motion_id={motion.get('motion_id')}, "
            f"action_type={motion.get('action_type')}, "
            f"可打断={motion.get('interruptible')})"
        )
    lines.append(
        "固定姿态（不在公开列表，可直接执行）："
        + "、".join(f"{k}={v}" for k, v in POSTURE_FIXED_IDS.items())
    )
    return "\n".join(lines)


def check_dance(motion_name: str) -> str:
    """只读检查指定舞蹈当前是否可用。"""
    if motion_name not in DANCE_WHITELIST:
        return f"不支持的动作：{motion_name}。允许的动作：{'、'.join(DANCE_WHITELIST)}"
    try:
        motion = _find_dance(motion_name)
    except RobotApiError as exc:
        return f"查询失败：{exc}"
    if motion is None:
        return f"机器人当前动作列表中没有 {motion_name}。"
    return (
        f"{motion_name} 可用：motion_id={motion.get('motion_id')}, "
        f"action_type={motion.get('action_type')}, "
        f"可打断={motion.get('interruptible')}"
    )


def start_dance(motion_name: str) -> str:
    """执行指定舞蹈：先查实时动作列表确认，再用查到的 ID 下发。"""
    if motion_name not in DANCE_WHITELIST:
        return f"拒绝执行：{motion_name} 不在允许列表中（{'、'.join(DANCE_WHITELIST)}）。"
    try:
        motion = _find_dance(motion_name)
        if motion is None:
            return f"机器人当前动作列表中没有 {motion_name}，未下发任何指令。"
        motion_id = motion.get("motion_id")
        result = _rpc(
            "InteractWithId", {"interaction_id": motion_id, "type": ACTION_TYPE_MOTION}
        )
    except RobotApiError as exc:
        return f"执行失败：{exc}"
    state = (result.get("header") or {}).get("status") or {}
    if result.get("success") is not True or state.get("value") != 1:
        return f"机器人未接受 {motion_name}：{str(result)[:500]}"
    return (
        f"已下发 {motion_name}（motion_id={motion_id}）。"
        "此响应只表示机器人已接受请求，不代表动作已经完成。"
    )


def normalize_posture_name(name: str) -> str:
    key = str(name or "").strip()
    if not key:
        return ""
    alias = POSTURE_ALIASES.get(key) or POSTURE_ALIASES.get(key.lower())
    return alias or key


def posture_catalog() -> dict[str, str]:
    """返回姿态/手势名 → 说明。"""
    items = {
        "stand_up": f"站起（固定 motion_id={POSTURE_FIXED_IDS['stand_up']}）",
        "action_stow": f"折叠/收纳（固定 motion_id={POSTURE_FIXED_IDS['action_stow']}）",
        "lay_down": f"躺下（固定 motion_id={POSTURE_FIXED_IDS['lay_down']}）",
        "lie_prone": f"趴下（固定 motion_id={POSTURE_FIXED_IDS['lie_prone']}）",
    }
    for gesture in GESTURE_WHITELIST:
        items[gesture] = f"手势（以实时 GetMotionList 解析 {gesture}）"
    return items


def check_posture(motion_name: str) -> str:
    """只读检查姿态/手势是否可执行。"""
    name = normalize_posture_name(motion_name)
    if name in POSTURE_FIXED_IDS:
        return (
            f"{name} 可执行：使用固定 motion_id={POSTURE_FIXED_IDS[name]} "
            f"（不在公开 GetMotionList 中，与原生 skill 一致）。"
        )
    if name in GESTURE_WHITELIST:
        try:
            motion = _find_named_motion(name)
        except RobotApiError as exc:
            return f"查询失败：{exc}"
        if motion is None:
            return f"机器人当前动作列表中没有 {name}。"
        return (
            f"{name} 可用：motion_id={motion.get('motion_id')}, "
            f"可打断={motion.get('interruptible')}"
        )
    known = "、".join([*POSTURE_FIXED_IDS, *GESTURE_WHITELIST])
    return f"不支持的姿态/手势：{motion_name}。允许：{known}"


def _find_named_motion(motion_name: str) -> dict[str, Any] | None:
    for motion in _motion_list():
        if (
            motion.get("motion_name") == motion_name
            and motion.get("action_type") == ACTION_TYPE_MOTION
        ):
            return motion
    return None


def start_posture(motion_name: str) -> str:
    """直接执行姿态/手势，不做二次确认。"""
    name = normalize_posture_name(motion_name)
    if not name:
        return "拒绝执行：未指定动作名。"
    if not dance_enabled():
        return "动作未启用：请在 MCP 服务环境中设置 QIYUAN_ENABLE_DANCE=1。"

    try:
        if name in POSTURE_FIXED_IDS:
            motion_id = POSTURE_FIXED_IDS[name]
            source = "fixed_native_id"
        elif name in GESTURE_WHITELIST:
            motion = _find_named_motion(name)
            if motion is None:
                return f"机器人当前动作列表中没有 {name}，未下发任何指令。"
            motion_id = motion.get("motion_id")
            source = "live_motion_list"
        else:
            known = "、".join([*POSTURE_FIXED_IDS, *GESTURE_WHITELIST])
            return f"拒绝执行：{motion_name} 不在允许列表中（{known}）。"

        result = _rpc(
            "InteractWithId",
            {"interaction_id": motion_id, "type": ACTION_TYPE_MOTION},
        )
    except RobotApiError as exc:
        return f"执行失败：{exc}"

    state = (result.get("header") or {}).get("status") or {}
    if result.get("success") is not True or state.get("value") != 1:
        return f"机器人未接受 {name}：{str(result)[:500]}"
    return (
        f"已下发 {name}（motion_id={motion_id}, source={source}）。"
        "此响应只表示机器人已接受请求，不代表动作已经完成。"
    )
