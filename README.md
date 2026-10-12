# 用 WorkBuddy 控制启元 Q1

本仓库是一份可独立使用的 **MCP 控车包**。  
**人**可以按下面步骤自己安装；**Agent**拿到本仓库地址、机器人 IP 和 SSH 密码后，也应**按相同步骤直接执行**，不要只口头解释。

控制发生在**你的电脑**上：WorkBuddy 拉起本目录的 `server.py`，再经 SSH 或 HTTP 打到机器人。机器人麦克风唤醒 / 出厂语音**不参与**这条链路。

```text
你（或 Agent）
  ↓
WorkBuddy（已登录）
  ↓  stdio（~/.workbuddy/mcp.json）
本目录 server.py（连接器名 qiyuan-q1）
  ├─ 行走、说话、拍照 → SSH → run@机器人IP → ROS2
  └─ 站起、折叠、挥手、跳舞 → HTTP → 机器人IP:50091
```

---

## 给 Agent 的一句话任务（可直接粘贴）

```text
请克隆本仓库并严格按 README.md 从「安装」做到「验收」：
1) 检查并安装 SSH 客户端（及 sshpass，若需要用密码写入公钥）；
2) 用我提供的机器人 IP、用户（默认 run）、SSH 密码完成本机密钥并写入机器人 authorized_keys；
3) 安装 Python 依赖；
4) 合并写入 ~/.workbuddy/mcp.json 的 qiyuan-q1（不要整文件覆盖其它连接器）；
5) 运行 python3 cli.py status，四段链路都正常后再用自然语言/工具控车。
密码和私钥不要写入仓库、不要写进 mcp.json、不要提交 Git。
电脑与机器人须在同一局域网。
机器人 IP：<填写>
SSH 用户：run
SSH 密码：<填写，仅本次使用>
```

---

## 前提

| 项目 | 要求 |
|---|---|
| 网络 | 电脑与机器人**同一局域网** |
| WorkBuddy | 已安装并已登录 |
| Python | 3.10+，`python3` 可用 |
| SSH | 最终须**密钥免密**登录 `run@机器人IP`（可用密码由 Agent/人一次性配好） |
| 行走脚本 | 机器人上存在可执行文件 `/home/run/bin/q1_play_move.sh` |
| 动作端口 | 本机可访问 `机器人IP:50091` |

行走 / 说话 / 拍照走 SSH；站起 / 折叠 / 挥手 / 跳舞走 `50091`。两条链路失败互不影响。

**安全约定**

- 仓库内**不得**存放 SSH 密码、私钥、API Key。
- 密码仅用于把公钥装到机器人；成功后只用密钥。
- 舞蹈工具必须确认周围清空；不得擅自把 `confirmed_clear_space` 写死为 true。

---

## 安装（人机共用，请按序执行）

下列命令里请把变量换成真实值：

```bash
export REPO_DIR="$HOME/qiyuan-q1-mcp"          # 克隆后的本仓库目录
export ROBOT_HOST="192.168.x.x"                # 机器人局域网 IP
export ROBOT_USER="run"
export ROBOT_PASSWORD="***"                    # 仅本次使用，勿写入文件仓库
export SSH_KEY="$HOME/.ssh/id_ed25519_q1"      # 建议专用密钥
```

### 0. 获取代码

```bash
git clone <本仓库 Git 地址> "$REPO_DIR"
cd "$REPO_DIR"
```

若已是本目录，则 `REPO_DIR` 设为当前路径即可。

### 1. 检查并安装 SSH

先检查客户端：

```bash
command -v ssh
command -v ssh-keygen
```

没有则安装（按系统选一条）：

```bash
# Debian / Ubuntu / 同类
sudo apt-get update
sudo apt-get install -y openssh-client

# 若下面要用密码自动写入公钥，再装 sshpass
sudo apt-get install -y sshpass
```

```bash
# macOS（一般自带 ssh；sshpass 可选）
brew install openssh    # 通常不必
brew install hudochenkov/sshpass/sshpass   # 若需要密码非交互拷公钥
```

再确认：

```bash
ssh -V
command -v sshpass || echo "未安装 sshpass：可用手动 ssh-copy-id，或先安装后再继续"
```

### 2. 完成本机密钥，并写入机器人

若密钥不存在则生成（无密码短语，便于 Agent 非交互）：

```bash
if [ ! -f "$SSH_KEY" ]; then
  ssh-keygen -t ed25519 -f "$SSH_KEY" -N "" -C "qiyuan-q1-mcp"
fi
```

用密码把公钥装到机器人（优先）：

```bash
sshpass -p "$ROBOT_PASSWORD" ssh-copy-id \
  -i "${SSH_KEY}.pub" \
  -o StrictHostKeyChecking=accept-new \
  "${ROBOT_USER}@${ROBOT_HOST}"
```

没有 `sshpass` 时，人可以交互执行：

```bash
ssh-copy-id -i "${SSH_KEY}.pub" "${ROBOT_USER}@${ROBOT_HOST}"
```

验证**免密**（不应再要密码）：

```bash
ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=no \
  "${ROBOT_USER}@${ROBOT_HOST}" 'hostname; test -x /home/run/bin/q1_play_move.sh && echo helper=ok'
```

看到主机名且 `helper=ok` 再继续。`BatchMode=yes` 仍要密码 → 公钥未生效，回到本步。

### 3. 安装 Python 依赖

```bash
cd "$REPO_DIR"
python3 -m pip install -r requirements.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --trusted-host pypi.tuna.tsinghua.edu.cn
```

可选（聊天里显示拍照缩略图）：

```bash
python3 -m pip install pillow \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --trusted-host pypi.tuna.tsinghua.edu.cn
```

记下解释器绝对路径，写入 MCP 时必须用它：

```bash
command -v python3
python3 -c "import mcp; print('mcp ok')"
```

### 4. 写入 WorkBuddy MCP 配置

连接器名：`qiyuan-q1`。配置文件：`~/.workbuddy/mcp.json`。

1. 复制示例：`mcp.json.example`
2. 把其中三处改成真实值：
   - `command`：上一步 `command -v python3` 的绝对路径
   - `args` 与 `cwd`：本仓库（`$REPO_DIR`）的绝对路径，`args` 指向 `server.py`
   - `QIYUAN_ROBOT_HOST`：机器人 IP
   - `QIYUAN_ROBOT_SSH_KEY`：私钥**绝对路径**（不要写 `.pub`）
   - 保持 `QIYUAN_ENABLE_DANCE` 为 `"1"`（需要站起/折叠/舞时）
3. **合并**进 `~/.workbuddy/mcp.json`：若文件里已有其它 `mcpServers`，只增加或覆盖 `qiyuan-q1`，**不要整文件覆盖**导致其它连接器丢失。

示例片段（路径请换成你的）：

```json
{
  "mcpServers": {
    "qiyuan-q1": {
      "command": "/usr/bin/python3",
      "args": ["/home/你/qiyuan-q1-mcp/server.py"],
      "cwd": "/home/你/qiyuan-q1-mcp",
      "env": {
        "QIYUAN_ROBOT_HOST": "192.168.x.x",
        "QIYUAN_ROBOT_USER": "run",
        "QIYUAN_ROBOT_SSH_KEY": "/home/你/.ssh/id_ed25519_q1",
        "QIYUAN_ROBOT_RPC_PORT": "50091",
        "QIYUAN_ENABLE_DANCE": "1"
      },
      "disabled": false
    }
  }
}
```

也可用仓库脚本一键合并（推荐 Agent 使用）：

```bash
cd "$REPO_DIR"
python3 scripts/write_workbuddy_mcp.py \
  --repo-dir "$REPO_DIR" \
  --python "$(command -v python3)" \
  --host "$ROBOT_HOST" \
  --user "$ROBOT_USER" \
  --ssh-key "$SSH_KEY"
```

然后在 WorkBuddy 里**重载 MCP**。连接器名应为 `qiyuan-q1`。

### 5. 命令行自检（验收）

```bash
cd "$REPO_DIR"
export QIYUAN_ROBOT_HOST="$ROBOT_HOST"
export QIYUAN_ROBOT_USER="$ROBOT_USER"
export QIYUAN_ROBOT_SSH_KEY="$SSH_KEY"
export QIYUAN_ROBOT_RPC_PORT=50091
export QIYUAN_ENABLE_DANCE=1

python3 cli.py status
```

`status` 中行走、语音、拍照、动作四段都有正常返回后，再驱动真机：

```bash
python3 cli.py speak "你好，我是启元Q1"
python3 cli.py photo
python3 cli.py forward --distance 0.2
python3 cli.py stop
python3 cli.py stand
python3 cli.py fold
```

跳舞须加 `--yes`（表示已确认周围至少 1 米无人和障碍物）：

```bash
python3 cli.py dance street_dance --yes
```

---

## 控制（安装通过后）

### 在 WorkBuddy 对话里

先让它调用 `robot_status`。通过后再说自然语言，例如：

- 「向前走一点」「停下」
- 「跟我说你好」
- 「拍张照」
- 「站起来」「折叠」「挥手」
- 「跳个舞」→ 应先向你确认周围已清空，再调用舞蹈工具

IP 变了：只改 `mcp.json` 里 `QIYUAN_ROBOT_HOST`，再重载 MCP。

### 工具一览

| 工具 | 作用 | 是否驱动机器人 | 二次确认 |
|---|---|---|---|
| `robot_status` | 检查行走、语音、拍照、动作 | 否 | — |
| `move_forward` | 前进，默认 0.2 米 | 是 | 否 |
| `move_backward` | 后退，默认 0.2 米 | 是 | 否 |
| `move_stop` | 停止行走 | 是 | 否 |
| `robot_speak` | 播报 | 是 | 否 |
| `robot_stop_speak` | 停止播报 | 是 | 否 |
| `robot_take_photo` | 拍照，JPEG 到本目录 `captures/` | 是 | 否 |
| `list_motions` | 列出可做动作 | 否 | — |
| `check_dance` / `check_posture` | 只读检查 | 否 | — |
| `stand_up` / `fold_stow` / `wave_hand` | 站起 / 折叠 / 挥手 | 是 | 否 |
| `perform_posture` | 白名单姿态或手势 | 是 | 否 |
| `perform_street_dance` / `perform_dance` | 舞蹈 | 是 | 需确认清场 |

行走距离限制在 0.05～0.5 米。机器人返回成功只表示**已接受请求**，不表示动作已做完。

未设置 `QIYUAN_ENABLE_DANCE=1` 时，站起 / 折叠 / 挥手 / 舞蹈会被拒绝。

`perform_posture` 可用名：`stand_up`、`action_stow`、`lay_down`、`lie_prone`、`wave_hand`、`handshake`、`fist_bump`、`cheer_up`、`stretch`、`hug`、`heart_gesture`、`boxing`。别名 `fold`/`折叠`→折叠，`stand`/`站起来`→站起。

固定姿态 ID：站起 `3045`，折叠 `3057`，躺下 `3044`，趴下 `3060`。部分手势 ID 会实时向机器人查询。

### 可选环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| `QIYUAN_ROBOT_HOST` | `192.168.0.181` | 机器人 IP |
| `QIYUAN_ROBOT_USER` | `run` | SSH 用户 |
| `QIYUAN_ROBOT_SSH_KEY` | `~/.ssh/id_ed25519_q1` | SSH 私钥 |
| `QIYUAN_ROBOT_RPC_PORT` | `50091` | 动作 RPC 端口 |
| `QIYUAN_ENABLE_DANCE` | 未设置 | 设为 `1` 才允许姿态/手势/舞蹈 |
| `QIYUAN_PHOTO_CAMERA_ID` | `head_monocular_centra` | 默认相机 |
| `QIYUAN_PHOTO_DIR` | 本目录 `captures/` | 照片目录 |

---

## 过程说明（控车怎么走通）

1. 你在 WorkBuddy 里说自然语言（或 Agent 调工具）。
2. 模型根据 `server.py` 里的工具说明选择工具（如 `move_forward`）。
3. WorkBuddy 通过 stdio 调用本机 MCP 进程。
4. MCP 按工具类型：
   - 行走：SSH 执行 `/home/run/bin/q1_play_move.sh`（ROS2 PlayMove）
   - 说话：SSH 上 `ros2 service call … PlayTts`
   - 拍照：SSH 调用 CaptureJpeg，再 SCP 拉回本机
   - 姿态/舞蹈：本机 HTTP POST `http://IP:50091/rpc/...`（不登录 SSH）
5. 结果文本（拍照还可带图）回到对话。

---

## 常见问题

- **WorkBuddy 看不到工具**：`command` 指向的 Python 能 `import mcp`；路径为绝对路径；已重载 MCP。
- **SSH 命令不存在**：回到「检查并安装 SSH」。
- **免密失败**：检查公钥是否在机器人 `~/.ssh/authorized_keys`，私钥路径是否与 `QIYUAN_ROBOT_SSH_KEY` 一致。
- **行走失败、说话拍照正常**：检查 `/home/run/bin/q1_play_move.sh`。
- **站起/折叠失败、行走正常**：检查本机到 `IP:50091`，以及 `QIYUAN_ENABLE_DANCE=1`。
- **换电脑**：需重新克隆、配密钥、写该电脑上的 `mcp.json`。

---

## 仓库内相关文件

| 路径 | 作用 |
|---|---|
| `server.py` | MCP 入口（连接器 `qiyuan-q1`） |
| `cli.py` | 命令行自检与控车 |
| `robot_move.py` / `robot_speak.py` / `robot_photo.py` / `robot_dance.py` | 四条能力实现 |
| `mcp.json.example` | WorkBuddy 配置模板 |
| `scripts/write_workbuddy_mcp.py` | 合并写入 `~/.workbuddy/mcp.json` |
| `scripts/bootstrap_workbuddy.sh` | 可选：检查 SSH、装依赖、写配置、跑 status（密码用环境变量传入） |
