#!/usr/bin/env bash
# 一键：检查 SSH →（可选）用密码装公钥 → pip → 写 WorkBuddy mcp.json → cli status
# 用法：
#   export ROBOT_HOST=192.168.x.x
#   export ROBOT_PASSWORD='***'    # 仅当尚未免密时需要；不要写入文件
#   ./scripts/bootstrap_workbuddy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROBOT_HOST="${ROBOT_HOST:-}"
ROBOT_USER="${ROBOT_USER:-run}"
ROBOT_PASSWORD="${ROBOT_PASSWORD:-}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_q1}"
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
PIP_TRUST="${PIP_TRUST:-pypi.tuna.tsinghua.edu.cn}"

die() { echo "错误: $*" >&2; exit 1; }

[ -n "$ROBOT_HOST" ] || die "请设置 ROBOT_HOST（机器人局域网 IP）"

echo "==> 1. 检查 SSH 客户端"
if ! command -v ssh >/dev/null 2>&1 || ! command -v ssh-keygen >/dev/null 2>&1; then
  echo "未找到 ssh / ssh-keygen，尝试安装 openssh-client…"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y openssh-client
  elif command -v brew >/dev/null 2>&1; then
    brew install openssh || true
  else
    die "请先手动安装 OpenSSH 客户端后再运行"
  fi
fi
command -v ssh >/dev/null || die "仍无 ssh"
ssh -V

echo "==> 2. 准备本机密钥: $SSH_KEY"
mkdir -p "$(dirname "$SSH_KEY")"
if [ ! -f "$SSH_KEY" ]; then
  ssh-keygen -t ed25519 -f "$SSH_KEY" -N "" -C "qiyuan-q1-mcp"
fi

echo "==> 3. 确保可免密登录 ${ROBOT_USER}@${ROBOT_HOST}"
if ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout=8 "${ROBOT_USER}@${ROBOT_HOST}" 'echo ok' 2>/dev/null | grep -qx ok; then
  echo "已免密，跳过密码装公钥"
else
  [ -n "$ROBOT_PASSWORD" ] || die "尚未免密，请设置 ROBOT_PASSWORD 后重试（或手动 ssh-copy-id）"
  if ! command -v sshpass >/dev/null 2>&1; then
    echo "未找到 sshpass，尝试安装…"
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get install -y sshpass
    elif command -v brew >/dev/null 2>&1; then
      brew install hudochenkov/sshpass/sshpass || die "请安装 sshpass 后重试"
    else
      die "请安装 sshpass，或手动: ssh-copy-id -i ${SSH_KEY}.pub ${ROBOT_USER}@${ROBOT_HOST}"
    fi
  fi
  sshpass -p "$ROBOT_PASSWORD" ssh-copy-id \
    -i "${SSH_KEY}.pub" \
    -o StrictHostKeyChecking=accept-new \
    "${ROBOT_USER}@${ROBOT_HOST}"
  ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=no \
    -o ConnectTimeout=8 "${ROBOT_USER}@${ROBOT_HOST}" 'hostname' \
    || die "装公钥后仍无法免密登录"
fi

echo "==> 4. 安装 Python 依赖"
command -v python3 >/dev/null || die "需要 python3"
python3 -m pip install -r "$ROOT/requirements.txt" \
  -i "$PIP_INDEX" --trusted-host "$PIP_TRUST"
python3 -c "import mcp; print('mcp ok')"

echo "==> 5. 合并写入 ~/.workbuddy/mcp.json"
python3 "$ROOT/scripts/write_workbuddy_mcp.py" \
  --repo-dir "$ROOT" \
  --python "$(command -v python3)" \
  --host "$ROBOT_HOST" \
  --user "$ROBOT_USER" \
  --ssh-key "$SSH_KEY"

echo "==> 6. cli.py status"
export QIYUAN_ROBOT_HOST="$ROBOT_HOST"
export QIYUAN_ROBOT_USER="$ROBOT_USER"
export QIYUAN_ROBOT_SSH_KEY="$SSH_KEY"
export QIYUAN_ROBOT_RPC_PORT=50091
export QIYUAN_ENABLE_DANCE=1
python3 "$ROOT/cli.py" status

echo
echo "完成。请在 WorkBuddy 中重载 MCP，连接器名 qiyuan-q1。"
echo "勿将 ROBOT_PASSWORD 写入磁盘或提交 Git。"
