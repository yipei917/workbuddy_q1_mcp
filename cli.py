#!/usr/bin/env python3
"""本地命令行测试：不依赖 WorkBuddy。同时覆盖行走与舞蹈两类能力。"""

from __future__ import annotations

import argparse
import sys

import robot_dance as dance
import robot_move as move


def main() -> int:
    parser = argparse.ArgumentParser(
        description="启元 Q1 统一控制（行走：SSH + PlayMove / 舞蹈：AimRT HTTP RPC）"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="检查两条链路连通性与动作概览")

    p_fwd = sub.add_parser("forward", help="前进")
    p_fwd.add_argument("--distance", type=float, default=0.2)
    p_back = sub.add_parser("backward", help="后退")
    p_back.add_argument("--distance", type=float, default=0.2)
    sub.add_parser("stop", help="停止行走")

    p_speak = sub.add_parser("speak", help="语音播报（直接执行）")
    p_speak.add_argument("text", help="要说的话")
    sub.add_parser("stop-speak", help="停止播报")

    p_photo = sub.add_parser("photo", help="拍照并拉回本机（直接执行）")
    p_photo.add_argument(
        "--camera",
        default="",
        help="相机 ID，默认 head_monocular_centra",
    )

    sub.add_parser("list", help="列出机器人全部动作")

    p_check = sub.add_parser("check", help="检查某个舞蹈是否可用")
    p_check.add_argument("motion_name", choices=dance.DANCE_WHITELIST)

    p_dance = sub.add_parser("dance", help="执行舞蹈")
    p_dance.add_argument("motion_name", choices=dance.DANCE_WHITELIST)
    p_dance.add_argument("--yes", action="store_true", help="确认周围至少 1 米内无人无障碍")

    sub.add_parser("stand", help="站起来（直接执行）")
    sub.add_parser("fold", help="折叠/收纳（直接执行）")
    p_posture = sub.add_parser("posture", help="执行姿态/手势（直接执行）")
    p_posture.add_argument(
        "motion_name",
        help="stand_up / action_stow / wave_hand / ...",
    )
    p_check_p = sub.add_parser("check-posture", help="检查姿态/手势是否可执行")
    p_check_p.add_argument("motion_name")

    args = parser.parse_args()

    if args.cmd == "status":
        import robot_photo as photo

        print("【行走链路】")
        print(move.robot_ping())
        print("【动作链路】")
        print(dance.robot_status())
        print("【拍照链路】")
        print(photo.photo_status())
    elif args.cmd == "forward":
        print(move.play_move("forward", args.distance))
    elif args.cmd == "backward":
        print(move.play_move("backward", args.distance))
    elif args.cmd == "stop":
        print(move.play_move("stop"))
    elif args.cmd == "speak":
        import robot_speak as voice

        print(voice.robot_speak(args.text))
    elif args.cmd == "stop-speak":
        import robot_speak as voice

        print(voice.robot_stop_speak())
    elif args.cmd == "photo":
        import robot_photo as photo

        print(photo.robot_take_photo(args.camera))
    elif args.cmd == "list":
        print(dance.list_motions())
    elif args.cmd == "check":
        print(dance.check_dance(args.motion_name))
    elif args.cmd == "check-posture":
        print(dance.check_posture(args.motion_name))
    elif args.cmd == "stand":
        print(dance.start_posture("stand_up"))
    elif args.cmd == "fold":
        print(dance.start_posture("action_stow"))
    elif args.cmd == "posture":
        print(dance.start_posture(args.motion_name))
    elif args.cmd == "dance":
        if not args.yes:
            print("拒绝执行：请加 --yes 确认机器人周围至少 1 米空间无人和障碍物。")
            return 2
        if not dance.dance_enabled():
            print("拒绝执行：请先设置 QIYUAN_ENABLE_DANCE=1。")
            return 2
        print(dance.start_dance(args.motion_name))
    else:
        parser.error(f"unknown command: {args.cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
