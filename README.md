# ContentPilot

AI 驱动的内容创作与多平台发布系统。AI 生成内容，人工审核把关，发布到多个平台（博客园、掘金、小红书等），全程可追踪。

## 架构

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy (SQLite) |
| 前端 | Vue 3 + Naive UI（`web/` 目录） |
| 浏览器自动化 | Playwright Chromium（平台发布、扫码登录） |
| CLI | Typer（命令名 `publisher`） |

> **安全提示（务必阅读）**
>
> 1. **鉴权**：默认部署仅监听 `127.0.0.1`。如需暴露到局域网/公网，必须先修改 `PUBLISHER_ADMIN_USERNAME` / `PUBLISHER_ADMIN_PASSWORD` / `PUBLISHER_SESSION_SECRET`，并为 API 配置访问令牌，否则任何人都可以操作你的发布账号。
> 2. **平台合规**：使用浏览器自动化在小红书、知乎等平台发布可能违反目标平台的服务条款，存在触发风控甚至封号的风险，尤其在 `review=never + publish=automatic` 全自动模式下。请自行评估并承担风险；系统已内置最小发布间隔与账号冷却（见配置表），建议保持开启。

核心概念：

- **文章 (Article)** — 内容主体，带版本历史
- **账号 (Account)** — 平台发布账号，凭据 Fernet 加密存储
- **发布任务 (PublishTask)** — 状态机：`pending → waiting_review → queued → processing → success / failed / waiting_auth / waiting_manual / timeout`
- **策略 (Policy)** — 审核模式与发布模式，按 平台 / 账号 / 文章 / 任务 级联覆盖
- **Worker** — 后台轮询执行任务，同进程随 server 启动

## 快速开始（本机）

```bash
# 安装（Python 3.11+）
pip install .

# 启动服务（API :8000，同进程启动发布 Worker）
publisher server

# Web 管理台（开发模式）
cd web && npm install && npm run dev
# 访问 http://localhost:5173 ，默认账号 admin / admin
```

## CLI 命令参考

所有命令通过 `publisher` 调用，列表类命令支持 `--json` 输出。

### 服务

```bash
publisher server [--host 127.0.0.1] [--port 8000]
```

启动 Web API，并在同进程后台运行发布 Worker。

### 文章

```bash
publisher article create --title "标题" --content "正文" [--summary "摘要"] [--source manual]
publisher article list [--json]
publisher article show <article_id> [--json]
publisher article update <article_id> [--title ...] [--content ...] [--summary ...] [--status draft|ready|archived]
```

注意：内容变更后，已有版本的审核记录不再对新版本生效，需重新送审（§35）。

### AI

```bash
publisher ai generate "<提示词>"            # 生成内容
publisher ai revise "<内容>" "<修改指令>"    # 修改内容
publisher ai adapt "<内容>" <platform>      # 适配平台风格（juejin / xiaohongshu / ...）
```

需要配置 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY` 环境变量。

### 策略

```bash
# 查询某作用域组合最终解析出的审核/发布策略（只读）
publisher policy resolve [--platform <平台名>] [--account-id N] [--article-id N] [--task-id N] [--json]

# 设置某层覆盖；未配置 = 继承上级
publisher policy set <global|platform|account|article|task> [scope_id] \
  [--review always|optional|never] [--publish automatic|manual|scheduled|disabled] \
  [--floor]        # 仅 platform/account 层：不可被下游调松的下限
publisher policy set <scope> [scope_id] --clear   # 删除该层配置，恢复跟随上级
```

### 发布

```bash
# 为文章创建发布任务；platform 缺省为全部已配平台
publisher publish <article_id> [platform] [--review | --no-review] [--json]
```

`--review` / `--no-review` 覆盖该次任务的审核策略。

### 任务

```bash
publisher task list [status] [--json]
publisher task show <task_id> [--json]
publisher task retry <task_id>    # 重试失败任务
publisher task resume <task_id>   # 恢复暂停任务
publisher task cancel <task_id>   # 取消任务
```

### 审核

```bash
publisher review list [--json]
publisher review approve <review_id> [--comment "备注"]
publisher review reject  <review_id> [--comment "备注"]
```

### 账号

```bash
publisher account list [--json]

# 添加账号（凭据加密存储，用于官方 API 平台如博客园）
publisher account add <platform> [key] --name "名称" \
  --username <用户名> --token <访问令牌> [--blog-name <博客名>]
```

### 浏览器登录（保存平台登录态）

```bash
publisher browser login <platform> [--account <账号key>] [--timeout 300]
```

打开可见浏览器完成登录并保存 `storage_state`。本机直接弹出 Chromium 窗口；容器环境通过 noVNC（`:6080`）操作。该平台只有一个账号时可省略 `--account`，没有账号会自动创建。

### 登录态

```bash
publisher auth login     # CLI 会话登录
publisher auth logout
publisher auth whoami
```

## Docker 部署

镜像内置 Xvfb + x11vnc + noVNC + Playwright Chromium，一条命令拉起全部服务。

```bash
docker compose up -d --build
```

端口：

| 端口 | 用途 |
|---|---|
| 8000 | Web API |
| 6080 | noVNC（浏览器人工接管，如扫码登录） |

数据卷（宿主机持久化）：

| 挂载 | 用途 |
|---|---|
| `./data` | SQLite 数据库 |
| `./uploads` | 上传文件 |
| `./logs` | 日志 |

### 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `PUBLISHER_ADMIN_USERNAME` | `admin` | Web 登录用户名 |
| `PUBLISHER_ADMIN_PASSWORD` | `admin` | Web 登录密码，生产必须修改 |
| `PUBLISHER_SESSION_SECRET` | `change-me-session-secret` | 会话签名密钥，生产必须修改 |
| `HEADLESS` | `true` | `false` 时启用 Xvfb 虚拟显示，可经 noVNC 可视化接管 |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | 空 | AI 生成能力 |

### 可视化人工接管

任务进入 `waiting_auth` / `waiting_manual` 状态时需要人工介入（扫码、验证码等）：

```bash
# docker-compose.yml 中设置 HEADLESS=false 后
docker compose up -d
# 浏览器打开 http://<host>:6080 即可看到并操作容器内的浏览器
```

### 常用运维

```bash
docker compose logs -f publisher     # 跟踪日志
docker compose restart publisher     # 重启（注意：session 为内存态，重启后需重新登录）
docker compose down                  # 停止（数据保留在 ./data）
```

## 配置

配置优先级：环境变量 > `.env` 文件 > 默认值。所有配置项加 `PUBLISHER_` 前缀，常用项：

| 配置 | 默认 | 说明 |
|---|---|---|
| `PUBLISHER_DATA_DIR` | `./data` | 数据目录（含 SQLite） |
| `PUBLISHER_DATABASE_URL` | 空（用 SQLite） | 自定义数据库连接串 |
| `PUBLISHER_HOST` / `PUBLISHER_PORT` | `127.0.0.1` / `8000` | 监听地址 |
| `PUBLISHER_SESSION_MAX_AGE` | `604800` | 会话有效期（秒） |
| `PUBLISHER_MIN_PUBLISH_INTERVAL_SECONDS` | `300` | 同账号最小发布间隔 |
| `PUBLISHER_MAX_CONSECUTIVE_BLOCKED` | `3` | 连续风控次数阈值，达到后进入冷却 |
| `PUBLISHER_COOLDOWN_SECONDS` | `3600` | 账号冷却时长（秒） |
| `PUBLISHER_WAITING_AUTH_TIMEOUT` | `86400` | 等待授权超时（秒） |

## Web 前端开发

```bash
cd web
npm install
npm run dev    # http://localhost:5173 ，/api 代理到 127.0.0.1:8000
npm run build  # 产出 dist/
```

页面：Dashboard（任务统计）、文章管理、内容审核、发布任务、账号管理。
