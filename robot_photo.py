#!/usr/bin/env python3
"""拍照链路：SSH 上机器人调用 CaptureJpegImage，再 SCP 拉回本机。"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from datetime import datetime
from pathlib import Path

from robot_move import DEFAULT_HOST, DEFAULT_KEY, DEFAULT_USER, _ssh_base, ssh_run

DEFAULT_CAMERA_ID = os.environ.get("QIYUAN_PHOTO_CAMERA_ID", "head_monocular_centra")
DEFAULT_SERVICE = os.environ.get(
    "QIYUAN_PHOTO_SERVICE",
    "/aima/hal/camera/CaptureJpegImage",
)
DEFAULT_TIMEOUT_MS = int(os.environ.get("QIYUAN_PHOTO_TIMEOUT_MS", "5000"))
PHOTO_DIR = Path(
    os.environ.get(
        "QIYUAN_PHOTO_DIR",
        str(Path(__file__).resolve().parent / "captures"),
    )
).expanduser()
REMOTE_DIR = os.environ.get("QIYUAN_PHOTO_REMOTE_DIR", "/tmp/q1_mcp_photos")

_REMOTE_CAPTURE_PY = r'''
import sys, time
from pathlib import Path
import rclpy
from rclpy.node import Node
from aimdk_msgs.msg import CommonRequest, CommonState
from aimdk_msgs.srv import CaptureJpegImage

out_path = Path(sys.argv[1])
camera_id = sys.argv[2]
service = sys.argv[3]
timeout_ms = int(sys.argv[4])
out_path.parent.mkdir(parents=True, exist_ok=True)

class CaptureClient(Node):
    def __init__(self):
        super().__init__("q1_mcp_capture_jpeg")
        self.cli = self.create_client(CaptureJpegImage, service)

    def capture(self) -> int:
        t0 = time.time()
        while not self.cli.wait_for_service(timeout_sec=1.0):
            if time.time() - t0 > 20:
                print("SERVICE_UNAVAILABLE", flush=True)
                return 2
        req = CaptureJpegImage.Request()
        req.request = CommonRequest()
        req.request.header.stamp = self.get_clock().now().to_msg()
        req.camera_id = camera_id
        req.timeout_ms = timeout_ms
        call_timeout = max(6.0, timeout_ms / 1000.0 + 1.0)
        future = None
        for i in range(3):
            future = self.cli.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=call_timeout)
            if future.done():
                break
            time.sleep(0.2)
        if future is None or not future.done():
            print("CALL_TIMEOUT", flush=True)
            return 3
        resp = future.result()
        if resp is None:
            print("EMPTY_RESPONSE", flush=True)
            return 4
        code = resp.response.header.code
        status = resp.response.status.value
        data = bytes(resp.jpeg.image.data)
        if (code != 0 and status != CommonState.SUCCESS) or not data:
            print(
                f"CAPTURE_FAILED code={code} status={status} "
                f"msg={resp.response.message!r} bytes={len(data)}",
                flush=True,
            )
            return 5
        out_path.write_bytes(data)
        print(
            f"OK bytes={len(data)} width={resp.jpeg.width} height={resp.jpeg.height} "
            f"camera_id={resp.jpeg.camera_id} path={out_path}",
            flush=True,
        )
        return 0

rclpy.init()
node = CaptureClient()
try:
    raise SystemExit(node.capture())
finally:
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
'''


def _scp_from_robot(remote_path: str, local_path: Path) -> subprocess.CompletedProcess[str]:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            "scp",
            "-i",
            DEFAULT_KEY,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            f"{DEFAULT_USER}@{DEFAULT_HOST}:{remote_path}",
            str(local_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _safe_camera_id(camera_id: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_\-]", "", str(camera_id or "").strip())
    return clean or DEFAULT_CAMERA_ID


def robot_take_photo(camera_id: str = "") -> str:
    """抓拍一张 JPEG，拉回本机；成功返回说明文字，失败返回错误。"""
    ok, message, _path = take_photo(camera_id)
    return message if ok else message


def take_photo(camera_id: str = "") -> tuple[bool, str, Path | None]:
    """抓拍一张 JPEG，拉回本机。

    返回 (ok, message, local_path)。成功时 local_path 指向本机 JPEG。
    """
    cam = _safe_camera_id(camera_id or DEFAULT_CAMERA_ID)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_jpg = f"{REMOTE_DIR}/q1_{stamp}.jpg"
    local_jpg = PHOTO_DIR / f"q1_{stamp}.jpg"

    remote_cmd = (
        "source /opt/ros/humble/setup.bash; "
        "source /robot/software/app_proxy/setup.bash; "
        f"mkdir -p {shlex.quote(REMOTE_DIR)}; "
        f"python3 - {shlex.quote(remote_jpg)} {shlex.quote(cam)} "
        f"{shlex.quote(DEFAULT_SERVICE)} {int(DEFAULT_TIMEOUT_MS)}"
    )
    # Feed script on stdin; ssh passes remote_cmd as remote shell command.
    result = subprocess.run(
        [*_ssh_base(), remote_cmd],
        input=_REMOTE_CAPTURE_PY,
        check=False,
        capture_output=True,
        text=True,
        timeout=75,
    )
    out = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0 or "OK bytes=" not in out:
        return False, f"拍照失败（exit={result.returncode}）：\n{out[-1200:]}", None

    pull = _scp_from_robot(remote_jpg, local_jpg)
    if pull.returncode != 0 or not local_jpg.is_file():
        detail = (pull.stderr or pull.stdout or "").strip()
        return (
            False,
            (
                f"拍照成功但拉回本机失败：机器人路径 {remote_jpg}\n"
                f"{detail[-800:]}\n远端输出：{out[-400:]}"
            ),
            None,
        )

    size = local_jpg.stat().st_size
    meta = out.splitlines()[-1] if out else ""
    message = (
        f"已拍照并保存到本机：{local_jpg}\n"
        f"大小={size} 字节；相机={cam}\n"
        f"{meta}"
    )
    return True, message, local_jpg


def make_chat_preview(path: Path, *, max_side: int = 1280, quality: int = 85) -> Path | None:
    """生成用于聊天展示的缩小 JPEG；失败则返回 None（调用方可回退原图）。"""
    try:
        from PIL import Image as PILImage
    except Exception:
        return None
    try:
        src = Path(path)
        if not src.is_file():
            return None
        preview = src.with_name(src.stem + "_preview.jpg")
        with PILImage.open(src) as im:
            im = im.convert("RGB")
            w, h = im.size
            scale = min(1.0, float(max_side) / float(max(w, h)))
            if scale < 1.0:
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
            im.save(preview, format="JPEG", quality=quality, optimize=True)
        return preview
    except Exception:
        return None


def photo_status() -> str:
    """只读：检查拍照服务是否在机器人上可见。"""
    result = ssh_run(
        "bash -c 'source /opt/ros/humble/setup.bash; "
        "source /robot/software/app_proxy/setup.bash; "
        "ros2 service list' | grep -E 'CaptureJpegImage|AuthorizeCamera' | head -10",
        timeout=25,
    )
    if result.returncode != 0:
        return f"拍照链路检查失败：\n{result.stderr or result.stdout}"
    return (
        f"拍照链路可达（默认相机 {DEFAULT_CAMERA_ID}）\n"
        f"本机保存目录：{PHOTO_DIR}\n"
        f"{(result.stdout or '').strip() or '(未列出 CaptureJpegImage，真拍时再确认)'}"
    )
