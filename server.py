#!/usr/bin/env python3
"""WorkBuddy MCP: 启元 Q1 统一控制服务（行走 + 语音 + 拍照 + 舞蹈 + 姿态）。

合并自两个原本独立的服务：
  - workbuddy-q1-mcp → 行走：SSH 登录机器人执行 ROS2 PlayMove（前进/后退/停止）
  - mcp-dance        → 舞蹈/姿态：直连 AimRT HTTP RPC 下发预置动作

两条链路在内部保持独立模块、独立失败域（robot_move / robot_dance），
但对外只暴露一个服务名、一个连接器。
"""

from __future__ import annotations

import threading

from mcp.server.fastmcp import FastMCP, Image

import robot_dance as dance
import robot_move as move
import robot_photo as photo
import robot_speak as speak

mcp = FastMCP(
    "qiyuan-q1",
    instructions=(
        "控制启元 Q1 人形机器人，包含五类能力：行走、语音播报、拍照、预置舞蹈、姿态/手势。"
        "\n行走：用户说「前进/往前走」时调用 move_forward；「后退/往后」时调用 move_backward；"
        "「停止/停下/别走了」时调用 move_stop。"
        "\n语音：用户说「让它说…/播报…/跟我说…」时调用 robot_speak；"
        "「别说了/闭嘴/停止播报」时调用 robot_stop_speak。播报直接执行，无需二次确认。"
        "\n拍照：用户说「拍照/拍张照/帮我拍一下」时调用 robot_take_photo。"
        "拍照直接执行，无需二次确认；成功后返回本机 JPEG 路径。"
        "\n姿态：用户说「站起来/起立」时调用 stand_up；「折叠/收纳/收起」时调用 fold_stow；"
        "「挥手/打招呼」时调用 wave_hand；其它白名单姿态用 perform_posture。"
        "姿态与手势工具直接执行，不需要二次确认参数。"
        "\n舞蹈：用户说「跳舞/跳个舞/来段街舞」时调用 perform_street_dance；"
        "说「跳个 dance_a」等指定舞蹈时调用 perform_dance；"
        "说「有哪些动作/能跳什么」时调用 list_motions。"
        "\n通用：用户说「机器人通不通/在线吗」时调用 robot_status。"
        "\n安全：舞蹈仍需 confirmed_clear_space=true；语音/拍照/姿态/手势无需该参数，"
        "姿态仍受 QIYUAN_ENABLE_DANCE=1 总开关约束。"
    ),
)

_action_lock = threading.Lock()


def _guarded_dance(motion_name: str, confirmed_clear_space: bool) -> str:
    """舞蹈执行闸：总开关 → 人工确认 → 并发锁 → 实时预检。"""
    if not dance.dance_enabled():
        return "动作未启用：请在 MCP 服务环境中设置 QIYUAN_ENABLE_DANCE=1。"
    if not confirmed_clear_space:
        return "请先确认机器人周围至少 1 米空间无人和障碍物，并获得用户明确同意后再执行。"
    if not _action_lock.acquire(blocking=False):
        return "已有动作请求正在提交，请稍后再试。"
    try:
        return dance.start_dance(motion_name)
    finally:
        _action_lock.release()


def _direct_posture(motion_name: str) -> str:
    """姿态/手势直接执行：总开关 → 并发锁 → 下发。无二次确认。"""
    if not dance.dance_enabled():
        return "动作未启用：请在 MCP 服务环境中设置 QIYUAN_ENABLE_DANCE=1。"
    if not _action_lock.acquire(blocking=False):
        return "已有动作请求正在提交，请稍后再试。"
    try:
        return dance.start_posture(motion_name)
    finally:
        _action_lock.release()


@mcp.tool()
def robot_status() -> str:
    """检查启元 Q1 的整体状态：行走链路与动作链路是否可用，并给出舞蹈/姿态概览。只读。"""
    return "\n\n".join(
        [
            "【行走链路】\n" + move.robot_ping(),
            "【动作链路】\n" + dance.robot_status(),
            "【语音链路】\nPlayTts / StopTts 经 SSH+ROS2 调用（与行走同机）。",
            "【拍照链路】\n" + photo.photo_status(),
        ]
    )


@mcp.tool()
def move_forward(distance_m: float = 0.2) -> str:
    """让启元 Q1 机器人向前走一小段距离（米）。用户说前进、往前走、向前时使用。默认 0.2 米，最大 0.5 米。"""
    return move.play_move("forward", distance_m)


@mcp.tool()
def move_backward(distance_m: float = 0.2) -> str:
    """让启元 Q1 机器人向后退一小段距离（米）。用户说后退、往后时使用。默认 0.2 米，最大 0.5 米。"""
    return move.play_move("backward", distance_m)


@mcp.tool()
def move_stop() -> str:
    """立即停止启元 Q1 行走。用户说停止、停下、别走了时使用。"""
    return move.play_move("stop", 0.0)


@mcp.tool()
def robot_speak(text: str) -> str:
    """让启元 Q1 用扬声器播报一段话。用户说「让它说…」「播报…」「跟我说…」时使用。
    直接执行，无需二次确认。文本过长会被截断。成功只表示已接受播报请求。"""
    return speak.robot_speak(text)


@mcp.tool()
def robot_stop_speak() -> str:
    """停止启元 Q1 当前语音播报。用户说别说了、闭嘴、停止播报时使用。"""
    return speak.robot_stop_speak()


@mcp.tool()
def robot_take_photo(camera_id: str = ""):
    """让启元 Q1 拍一张照片并保存到本机，同时把图片回传到聊天。
    用户说拍照、拍张照、帮我拍一下时使用。
    直接执行，无需二次确认。默认头部中央相机 head_monocular_centra；
    成功时返回文字说明 + JPEG 图片内容。"""
    ok, message, path = photo.take_photo(camera_id)
    if not ok or path is None:
        return message
    # 聊天预览用缩小版，降低 MCP ImageContent 体积；原图仍保存在 path。
    preview = photo.make_chat_preview(path)
    show = preview if preview is not None else path
    return [message, Image(path=str(show))]


@mcp.tool()
def list_motions() -> str:
    """列出启元 Q1 当前公开动作，以及可直接执行的固定姿态。只读。"""
    return dance.list_motions()


@mcp.tool()
def check_dance(motion_name: str) -> str:
    """只读检查某个舞蹈当前是否可用。motion_name 仅支持 street_dance、dance_a、dance_b、dance_c。"""
    return dance.check_dance(motion_name)


@mcp.tool()
def check_posture(motion_name: str) -> str:
    """只读检查姿态/手势是否可执行。支持 stand_up、action_stow、lay_down、lie_prone 以及 wave_hand 等手势。"""
    return dance.check_posture(motion_name)


@mcp.tool()
def stand_up() -> str:
    """让启元 Q1 站起来。用户说站起来、起立时使用。直接执行，无需二次确认。"""
    return _direct_posture("stand_up")


@mcp.tool()
def fold_stow() -> str:
    """让启元 Q1 折叠/收纳身体。用户说折叠、折叠起来、收纳、收起时使用。直接执行，无需二次确认。"""
    return _direct_posture("action_stow")


@mcp.tool()
def wave_hand() -> str:
    """让启元 Q1 挥手打招呼。用户说挥手、打个招呼时使用。直接执行，无需二次确认。"""
    return _direct_posture("wave_hand")


@mcp.tool()
def perform_posture(motion_name: str) -> str:
    """执行白名单内的姿态或手势。直接执行，无需二次确认。

    motion_name 支持：stand_up、action_stow、lay_down、lie_prone、
    wave_hand、handshake、fist_bump、cheer_up、stretch、hug、heart_gesture、boxing。
    也可用别名：fold/折叠 → action_stow；stand/站起来 → stand_up。
    """
    return _direct_posture(motion_name)


@mcp.tool()
def perform_street_dance(confirmed_clear_space: bool) -> str:
    """让启元 Q1 跳预置的全身街舞（street_dance）。用户说跳舞、跳个舞、来段街舞时使用。

    调用前必须先确认机器人周围至少 1 米空间无人和障碍物；
    得到用户明确同意后才把 confirmed_clear_space 设为 true。该动作不可中途打断。
    """
    return _guarded_dance("street_dance", confirmed_clear_space)


@mcp.tool()
def perform_dance(motion_name: str, confirmed_clear_space: bool) -> str:
    """让启元 Q1 执行指定的预置舞蹈。motion_name 仅支持 street_dance、dance_a、dance_b、dance_c。
    安全要求与 perform_street_dance 相同。"""
    return _guarded_dance(motion_name, confirmed_clear_space)


if __name__ == "__main__":
    mcp.run(transport="stdio")
