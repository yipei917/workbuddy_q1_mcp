#!/usr/bin/env python3
"""Merge qiyuan-q1 into ~/.workbuddy/mcp.json without wiping other servers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True, help="Absolute path to this MCP repo")
    parser.add_argument("--python", required=True, help="Absolute path to python3 used by WorkBuddy")
    parser.add_argument("--host", required=True, help="Robot LAN IP")
    parser.add_argument("--user", default="run", help="SSH user")
    parser.add_argument("--ssh-key", required=True, help="Absolute path to SSH private key")
    parser.add_argument("--rpc-port", default="50091")
    parser.add_argument("--enable-dance", default="1")
    parser.add_argument(
        "--mcp-json",
        default=str(Path.home() / ".workbuddy" / "mcp.json"),
        help="WorkBuddy MCP config path",
    )
    args = parser.parse_args()

    repo = Path(args.repo_dir).expanduser().resolve()
    server = repo / "server.py"
    py = Path(args.python).expanduser().resolve()
    key = Path(args.ssh_key).expanduser().resolve()
    mcp_path = Path(args.mcp_json).expanduser()

    if not server.is_file():
        raise SystemExit(f"找不到 server.py: {server}")
    if not py.is_file():
        raise SystemExit(f"找不到 Python: {py}")
    if not key.is_file():
        raise SystemExit(f"找不到 SSH 私钥: {key}")

    entry = {
        "command": str(py),
        "args": [str(server)],
        "cwd": str(repo),
        "env": {
            "QIYUAN_ROBOT_HOST": str(args.host).strip(),
            "QIYUAN_ROBOT_USER": str(args.user).strip() or "run",
            "QIYUAN_ROBOT_SSH_KEY": str(key),
            "QIYUAN_ROBOT_RPC_PORT": str(args.rpc_port).strip() or "50091",
            "QIYUAN_ENABLE_DANCE": str(args.enable_dance).strip() or "1",
        },
        "disabled": False,
    }

    mcp_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"mcpServers": {}}
    if mcp_path.is_file():
        try:
            loaded = json.loads(mcp_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError as exc:
            raise SystemExit(f"现有 mcp.json 不是合法 JSON: {mcp_path}: {exc}") from exc

    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
        data["mcpServers"] = servers
    servers["qiyuan-q1"] = entry

    tmp = mcp_path.with_suffix(mcp_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, mcp_path)
    try:
        os.chmod(mcp_path, 0o600)
    except OSError:
        pass

    print(f"已合并 qiyuan-q1 → {mcp_path}")
    print(f"  python: {py}")
    print(f"  server: {server}")
    print(f"  host:   {args.host}")
    print(f"  key:    {key}")
    print("请在 WorkBuddy 中重载 MCP。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
