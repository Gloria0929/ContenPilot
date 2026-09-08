# ContentPilot

AI 驱动的内容创作与多平台发布系统。AI 生成内容，人工审核把关，发布到多个平台，全程可追踪。

Web、CLI、AI Agent Skill 三种使用方式共享同一套 Publisher Core：策略解析、审核流转、任务调度、平台适配全部由 Core 统一处理。

## 架构

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2 (SQLite, WAL) |
| 前端 | Vue 3 + TypeScript + Element Plus + md-editor-v3（`web/` 目录） |
| 浏览器自动化 | Playwright Chromium（平台发布、扫码登录、人工接管） |
| CLI | Typer（命令名 `publisher`） |
| AI Provider | Anthropic / OpenAI 兼容（OpenAI / OpenRouter / Ollama 等） |

### 平台支持

| 平台 | 模式 | 账号接入 | 发布方式 |
|---|---|---|---|
| 博客园 (cnblogs) | api | `publisher account add cnblogs --username ... --token ...`（MetaWeblog 令牌，Fernet 加密存储） | 官方 MetaWeblog XML-RPC |
| 掘金 (juejin) | browser | `publisher browser login juejin`（保存 storage_state） | Playwright 驱动浏览器 |
| CSDN (csdn) | browser | `publisher browser login csdn` | Playwright 驱动浏览器 |
| 思否 (segmentfault) | browser | `publisher browser login segmentfault` | Playwright 驱动浏览器 |
| FreeBuf (freebuf) | browser | `publisher browser login freebuf`（投稿后需平台审核） | Playwright 驱动浏览器 |
| 百家号 (baijiahao) | browser | `publisher browser login baijiahao` | Playwright 驱动浏览器 |
| 企鹅号 (qiehao) | browser | `publisher browser login qiehao`（发布后分发腾讯网/腾讯新闻等渠道） | Playwright 驱动浏览器 |
| 51CTO (51cto) | browser | `publisher browser login 51cto` | Playwright 驱动浏览器 |
| 腾讯云开发者社区 (tencent_cloud) | browser | `publisher browser login tencent_cloud` | Playwright 驱动浏览器 |

新增平台基于 Adapter 扩展（`src/publisher/platforms/`），不修改 Core 代码；浏览器平台的页面操作放在 `src/publisher/browser/scripts/`。

> **安全提示（务必阅读）**
>
> 1. **鉴权**：默认部署仅监听 `127.0.0.1`。如需暴露到局域网/公网，必须先修改 `PUBLISHER_ADMIN_USERNAME` / `PUBLISHER_ADMIN_PASSWORD` / `PUBLISHER_SESSION_SECRET`，否则任何人都可以操作你的发布账号。账号凭据的加密密钥自动生成于 `data/secret.key`（权限 600），**该文件丢失后已存凭据将无法解密**，请妥善备份；也可通过 `PUBLISHER_ENCRYPTION_KEY` 显式指定。
> 2. **平台合规**：使用浏览器自动化在掘金、CSDN、百家号等平台发布可能违反目标平台的服务条款，存在触发风控甚至封号的风险，尤其在 `review=never + publish=automatic` 全自动模式下。请自行评估并承担风险；系统已内置最小发布间隔与账号冷却（见配置表），建议保持开启。

核心概念：

- **文章 (Article)** — 内容主体（draft / ready / archived），按平台生成独立 **版本 (ArticleVersion)**，审核与发布始终绑定具体版本
- **账号 (Account)** — 平台发布账号；API 平台凭据 Fernet 加密存储，浏览器平台保存 storage_state 登录态
- **发布任务 (PublishTask)** — 一篇文章 × 一个平台 × 一个账号 = 一个任务，互不影响；状态机：
  `pending → waiting_review → queued → processing → success / failed / blocked / waiting_auth / waiting_manual / timeout / cancelled`
  - `waiting_auth`：登录态缺失/失效，需 `browser login` 后 `task resume`
  - `waiting_manual`：验证码/风控/内容安全命中，需人工处理后 `task resume`
  - `blocked`：已点击发布但无法确认结果，禁止自动重试，防止重复发布
- **策略 (Policy)** — 审核模式（always / optional / never）与发布模式（automatic / manual / scheduled / disabled），按 global → platform → account → article → task 级联覆盖；platform/account 层可设 `--floor` 下限，下游不可调松
- **Worker** — 后台轮询执行任务，同进程随 server 启动；处理重试、超时、账号浏览器互斥锁
- **内容安全兜底** — 独立于审核策略的违禁词检测，命中转 `waiting_manual`；可在 Web 设置页关闭，自定义词库放 `~/.contentpilot/data/banned_words.json`

## 快速开始（本机）

```bash
# 安装（Python 3.11+）
pip install .
# 开发安装（含 pytest 等测试依赖）
pip install -e ".[dev]"

# 启动服务（API :8000，同进程启动发布 Worker）
publisher server

# Web 管理台（开发模式）
cd web && npm install && npm run dev
# 访问 http://localhost:5173 ，默认账号 admin / admin
# /api 代理到 127.0.0.1:8000
```

若本地存在 `web/dist`（`npm run build` 产物），后端会自动托管前端，直接访问 `http://127.0.0.1:8000` 即可，无需单独起 dev server。

## CLI 命令参考

所有命令通过 `publisher` 调用，列表/详情类命令支持 `--json` 输出。CLI 输入错误时只显示错误信息，不展示 traceback。

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

注意：文章需处于 `ready` 状态才能创建发布任务（`article update <id> --status ready`）。内容变更后会生成新版本，已有版本的审核记录不再对新版本生效，需重新送审（Web 审核页可一键「刷新到最新版本重新审核」）。

### AI

```bash
publisher ai generate "<提示词>"            # 生成内容
publisher ai revise "<内容>" "<修改指令>"    # 修改内容
publisher ai adapt "<内容>" <platform>      # 适配平台风格（juejin / xiaohongshu / ...）
```

AI 能力仅通过 CLI 提供（Web 界面不含 AI 写作功能）。Provider 通过环境变量配置：

| 变量 | 说明 |
|---|---|
| `PUBLISHER_AI_PROVIDER` | `anthropic`（默认）/ `openai` / `openai_compat` / `ollama` / `openrouter` |
| `ANTHROPIC_API_KEY` | Anthropic 密钥（provider=anthropic 时必需） |
| `OPENAI_API_KEY` | OpenAI 兼容密钥（其余 provider 时必需） |
| `PUBLISHER_AI_BASE_URL` | OpenAI 兼容端点，默认 `https://api.openai.com/v1`（Ollama/OpenRouter 改这里） |
| `PUBLISHER_AI_MODEL` | 模型名，默认 `claude-sonnet-5` / `gpt-4o-mini` |

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
# 为文章创建发布任务；platform 需显式指定（多平台发布用 Web 发布页或多次调用）
publisher publish <article_id> <platform> [--account <账号key或id>] [--review | --no-review] [--json]
```

- `--account`：账号 key 或数字 id；省略时若该平台只有一个账号则自动绑定
- `--review` / `--no-review`：覆盖该次任务的审核策略（受 floor 下限约束）
- 浏览器平台需先完成 `browser login`，否则任务进入 `waiting_auth`

### 任务

```bash
publisher task list [status] [--json]
publisher task show <task_id> [--json]
publisher task retry <task_id>    # 重试 failed/blocked/timeout 任务
publisher task resume <task_id>   # 放行：waiting_manual→queued、pending→queued、timeout→waiting_manual
publisher task cancel <task_id>   # 取消任务
```

仅终态任务（success/failed/cancelled/timeout）可删除（Web 任务页或 `DELETE /api/tasks/{id}`）。

### 审核

```bash
publisher review list [--json]            # 待审核列表
publisher review approve <review_id> [--comment "备注"]
publisher review reject  <review_id> [--comment "备注"]
```

### 账号

```bash
publisher account list [--json]

# 添加账号（用于官方 API 平台，如博客园）
publisher account add cnblogs [key] --name "名称" \
  --username <用户名> --token <MetaWeblog访问令牌> [--blog-name <博客名>]
# key 缺省为 cnblogs_<用户名>；--username 与 --token 必须同时提供，凭据加密存储
```

### 浏览器登录（保存平台登录态）

```bash
publisher browser login <platform> [--account <账号key>] [--timeout 300]
```

打开可见浏览器完成登录并保存 `storage_state`。本机直接弹出 Chromium 窗口；容器环境通过 noVNC（`:6080`）操作。该平台只有一个账号时可省略 `--account`，没有账号会自动创建。

### CLI 鉴权

```bash
publisher auth login [-u admin] [-p 密码]   # 未提供 -p 时交互式隐藏输入
publisher auth whoami
publisher auth logout
```

登录后 API Key 持久化到 `~/.contentpilot/data/cli_session.json`（权限 600，仅当前用户可读），跨进程生效；重复 login 自动删除旧 key。该凭证同时可用于 REST API：`Authorization: Bearer ak_...:sk_...`。logout 会同时删除数据库中的 key 并删除本地文件。

### API 密钥（Access Key / Secret Key）

Web 设置页「API 密钥」可生成密钥对，供外部程序（AI Skill、脚本等）调用 REST API：

- **Access Key**（`ak_...`）：明文标识，可在列表中查看
- **Secret Key**（`sk_...`）：仅在生成时显示一次，服务端只存哈希
- 调用时组合为 Bearer 凭证：`Authorization: Bearer <access_key>:<secret_key>`
- 支持按密钥授予「允许跳过审核」（`--no-review`）权限；删除密钥立即生效

推荐将密钥写入客户端配置文件 `~/.contentpilot/api_client.json`（权限 600）：

```json
{
  "base_url": "http://127.0.0.1:8000",
  "access_key": "ak_...",
  "secret_key": "sk_..."
}
```

配置了该文件（或 `CONTENTPILOT_BASE_URL` / `CONTENTPILOT_ACCESS_KEY` / `CONTENTPILOT_SECRET_KEY` 环境变量）的机器上，`publisher` CLI 与 AI Skill 都会自动优先通过此 REST 接口远程操作 `base_url` 指向的服务（远程/本机均可）；未配置时 CLI 直连本机数据库。

## REST API 概览

所有接口挂载在 `/api` 前缀下（除登录外均需鉴权：HttpOnly Cookie 会话 或 `Authorization: Bearer <access_key>:<secret_key>`）：

| 分组 | 端点 |
|---|---|
| 鉴权 | `POST /auth/login`、`POST /auth/logout`、`GET /auth/whoami`、`GET|POST /auth/api_keys`、`DELETE /auth/api_keys/{id}` |
| 文章 | `GET|POST /articles`、`GET|PATCH|DELETE /articles/{id}`、`GET /articles/{id}/versions` |
| 策略 | `GET|POST /policies`、`GET /policies/resolve` |
| 审核 | `GET /reviews`、`POST /reviews/{id}/approve|reject|refresh` |
| 发布 | `POST /publish`、`GET /publish/{id}` |
| 任务 | `GET /tasks`、`GET /tasks/{id}`、`GET /tasks/{id}/logs`、`POST /tasks/{id}/retry|resume|cancel`、`DELETE /tasks/{id}` |
| 账号 | `GET|POST /accounts`、`GET|PATCH|DELETE /accounts/{id}` |
| 平台 | `GET /platforms`（含模式与能力） |
| 会话 | `GET /browser/sessions`（登录态与账号锁状态） |
| 设置 | `GET|POST /settings`（内容安全开关等运行时设置） |
| 日志 | `GET /logs`（可按 task_id/level 过滤，metadata 已脱敏） |
| 事件 | `GET /events`（SSE：task.created / task.status / task.timeout / task.review_stale） |

## Docker 部署

镜像内置前端构建产物 + Xvfb + x11vnc + noVNC + Playwright Chromium，直接访问 `http://<host>:8000` 即 Web 管理台，无需另起前端。

### 首次部署

```bash
git clone <本仓库> && cd ContentPilot

# 构建镜像并后台启动（首次构建需拉取基础镜像 + npm/pip 依赖，耗时较长）
docker compose up -d --build

# 确认服务就绪（看到 "Starting API on :8000" 即启动完成）
docker compose ps
docker compose logs -f publisher
```

浏览器访问 `http://localhost:8000`，默认账号 `admin / admin`；人工接管（扫码/验证码）入口在 `http://localhost:6080`。

### 启用 AI 生成能力

`docker-compose.yml` 通过 `${ANTHROPIC_API_KEY:-}` 读取宿主机环境变量，两种方式任选：

```bash
# 方式一：项目根目录建 .env 文件（compose 自动读取，长期推荐）
cat > .env <<'EOF'
ANTHROPIC_API_KEY=sk-ant-xxxx
# OPENAI_API_KEY=sk-xxxx          # 用 OpenAI 兼容 Provider 时
# PUBLISHER_AI_PROVIDER=anthropic  # anthropic / openai / ollama / openrouter
EOF
docker compose up -d

# 方式二：单次临时传入
ANTHROPIC_API_KEY=sk-ant-xxxx docker compose up -d
```

### 修改管理员密码与会话密钥

`docker-compose.yml` 中默认值仅适合本机体验。生产环境建议新建 `docker-compose.override.yml`（compose 自动合并、无需改动原文件）：

```yaml
services:
  publisher:
    environment:
      - PUBLISHER_ADMIN_USERNAME=admin
      - PUBLISHER_ADMIN_PASSWORD=<你的强密码>
      - PUBLISHER_SESSION_SECRET=<随机长字符串>
```

```bash
docker compose up -d        # 配置变更后自动重建容器
```

### 容器内使用 CLI

镜像内已安装 `publisher` 命令，直接在容器中执行（操作的是 `/data` 卷里的数据库）：

```bash
# 第一个 publisher 是服务名，第二个是 CLI 命令
docker compose exec publisher publisher article list
docker compose exec publisher publisher task list --json

# 浏览器平台登录：弹出窗口渲染在容器内，通过 noVNC(:6080) 完成扫码/登录
docker compose exec publisher publisher browser login juejin
docker compose exec publisher publisher browser login csdn -a csdn_default
```

端口：

| 端口 | 用途 |
|---|---|
| 8000 | Web API + Web 管理台 |
| 6080 | noVNC（浏览器人工接管，如扫码登录） |

数据卷（宿主机持久化）：

| 挂载 | 用途 |
|---|---|
| `./data` | SQLite 数据库、浏览器登录态、CLI token |
| `./uploads` | 上传文件 |
| `./logs` | 日志与诊断信息（截图 / Trace） |

> 注意：容器内通过 `PUBLISHER_DATA_DIR=/data` 等 ENV 固定路径，与本机部署的
> `~/.contentpilot/` 相互独立——本机 CLI 与容器 Worker 不会共享同一个 SQLite
> 文件（避免并发访问导致 disk I/O error）。

### 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `PUBLISHER_ADMIN_USERNAME` | `admin` | Web 登录用户名 |
| `PUBLISHER_ADMIN_PASSWORD` | `admin` | Web 登录密码，生产必须修改 |
| `PUBLISHER_SESSION_SECRET` | `change-me-session-secret` | 会话签名密钥，生产必须修改 |
| `HEADLESS` | 镜像内 `true`；compose 默认 `false` | `false` 时入口脚本启动 Xvfb 虚拟显示 |
| `PUBLISHER_HEADLESS` | `true` | `false` 时 Playwright 以有头模式运行，发布过程可在 noVNC 中可视化接管（需与 `HEADLESS=false` 同时开启） |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | 空 | AI 生成能力（配合 `PUBLISHER_AI_PROVIDER`） |

### 可视化人工接管

`docker-compose.yml` 默认已设置 `HEADLESS=false`（自动启动 Xvfb 虚拟显示）。任务进入 `waiting_auth` / `waiting_manual` 状态需要人工介入（扫码、验证码等）时：

```bash
# 浏览器打开 http://localhost:6080 即可看到并操作容器内的浏览器
# 完成登录/验证后，放行任务：
docker compose exec publisher publisher task resume <task_id>
```

若不需要可视化（纯无头、更省资源），在 `docker-compose.override.yml` 中加 `HEADLESS=true` 后重建。

### 升级与重新构建

```bash
git pull                            # 拉取最新代码
docker compose up -d --build        # 重新构建镜像并滚动替换容器
```

### 停止与数据备份

```bash
docker compose stop                 # 暂停（容器保留）
docker compose down                 # 停止并移除容器（./data 数据保留）

# 备份（SQLite + 浏览器登录态 + 上传文件都在宿主机挂载目录）
tar czf contentpilot_backup_$(date +%Y%m%d).tgz data uploads
```

### 常用运维

```bash
docker compose logs -f publisher     # 跟踪日志
docker compose logs --tail 100 publisher   # 查看最近 100 行
docker compose restart publisher    # 重启（注意：session 为内存态，重启后需重新登录）
```

Worker 启动时会自动把遗留的 `processing` 孤儿任务复位回 `queued`，进程重启不会让任务卡死。

## 配置

配置优先级：环境变量 > `.env` 文件 > 默认值。所有配置项加 `PUBLISHER_` 前缀：

| 配置 | 默认 | 说明 |
|---|---|---|
| `PUBLISHER_DATA_DIR` | `./data` | 数据目录（含 SQLite、浏览器登录态、CLI token） |
| `PUBLISHER_UPLOADS_DIR` / `PUBLISHER_LOGS_DIR` | `./uploads` / `./logs` | 上传 / 日志目录 |
| `PUBLISHER_DATABASE_URL` | 空（用 SQLite） | 自定义数据库连接串 |
| `PUBLISHER_HOST` / `PUBLISHER_PORT` | `127.0.0.1` / `8000` | 监听地址 |
| `PUBLISHER_SESSION_MAX_AGE` | `604800` | 会话有效期（秒） |
| `PUBLISHER_ENCRYPTION_KEY` | 空（自动生成 `~/.contentpilot/data/secret.key`） | 账号凭据加密密钥；显式设置时优先生效，更换后旧凭据需重新录入 |
| `PUBLISHER_WORKER_POLL_INTERVAL` | `1.0` | Worker 轮询间隔（秒） |
| `PUBLISHER_MAX_ATTEMPTS_DEFAULT` | `3` | 任务最大自动重试次数 |
| `PUBLISHER_MIN_PUBLISH_INTERVAL_SECONDS` | `300` | 同账号最小发布间隔 |
| `PUBLISHER_MAX_CONSECUTIVE_BLOCKED` | `3` | 连续风控次数阈值，达到后进入冷却 |
| `PUBLISHER_COOLDOWN_SECONDS` | `3600` | 账号冷却时长（秒） |
| `PUBLISHER_WAITING_AUTH_TIMEOUT` | `86400` | 等待授权超时（秒） |
| `PUBLISHER_WAITING_MANUAL_TIMEOUT` | `86400` | 等待人工接管超时（秒） |
| `PUBLISHER_REVIEW_STALE_DAYS` | `3` | 审核超期提醒阈值（天） |
| `PUBLISHER_CONTENT_SAFETY_ENABLED` | `true` | 内容安全兜底检测（Web 设置页可运行时修改） |
| `PUBLISHER_HEADLESS` | `true` | Playwright 无头模式 |
| `PUBLISHER_BROWSER_LOGIN_TIMEOUT` | `300` | browser login 等待登录完成超时（秒） |
| `PUBLISHER_AI_PROVIDER` / `PUBLISHER_AI_MODEL` / `PUBLISHER_AI_BASE_URL` | 见 AI 章节 | AI Provider 配置 |

## Web 前端开发

```bash
cd web
npm install
npm run dev    # http://localhost:5173 ，/api 代理到 127.0.0.1:8000
npm run build  # 产出 dist/ 并自动部署到 ~/.contentpilot/web_dist（后端优先从该处托管）
```

页面（Element Plus + 中文 locale，任务/日志/审核/平台页通过 SSE `/api/events` 实时刷新）：

- **工作台** — 任务统计总览
- **文章管理** — 创建/编辑（Markdown 编辑器）/删除、状态流转、文章级策略覆盖
- **发布内容** — 选择文章 + 多平台 + 账号，提交前实时预览各平台解析出的审核/发布策略
- **内容审核** — 待审列表（含「版本已过期」标记）、通过/驳回、刷新到最新版本重审
- **发布任务** — 任务状态、任务日志、错误详情（Tooltip）、远程文章链接、重试/恢复/取消/删除
- **账号管理** — 账号增删改、状态（active / auth_expired / cooling / disabled）
- **平台与会话** — 平台模式、浏览器会话与账号锁状态
- **发布日志** — 全量事件日志查询（按任务/级别过滤）
- **设置** — 运行时开关（内容安全兜底检测）、API 密钥管理（生成/删除 Access Key / Secret Key）

## AI Agent Skill

`skill/content-publisher/` 提供给 AI Agent 使用的 Skill（SKILL.md + 参考文档 + 示例）：AI 通过 CLI/API 完成内容生产与发布调度，但不得绕过 Policy Resolver、不得读取任何凭据（token / cookie / storage_state）。

Skill 的调用策略为「配置文件决定」：存在 `~/.contentpilot/api_client.json`（或设置了 `CONTENTPILOT_BASE_URL` / `CONTENTPILOT_ACCESS_KEY` / `CONTENTPILOT_SECRET_KEY` 环境变量）时以 Bearer `ak:sk` 凭证调用 REST API，`base_url` 指向哪台服务就调哪台（服务器或本机均可）；无配置文件时使用本机 `publisher` CLI（直接操作本机数据库）。完整的 CLI ↔ REST 端点映射见 `skill/content-publisher/references/api.md`。详细设计文档见 `docs/`（README.md、TECHNICAL_REQUIREMENTS_V2.2.md）。

`publisher` CLI 遵循同一套路由规则：存在 `api_client.json`（或 `CONTENTPILOT_*` 环境变量，环境变量优先）时，article / publish / task / review / account / policy / auth whoami 等命令自动转发为对 `base_url` 的 REST API 调用，可直接用命令行管理远程服务器部署（`server`、`ai`、`browser login` 始终在本机执行）。无配置时 CLI 直接操作本机数据库；配置文件存在但内容不完整时会直接报错，不会静默回落到本地库。

## 测试

```bash
pip install -e ".[dev]"
pytest    # 覆盖：策略解析、内容安全、浏览器锁、平台适配（掘金/博客园）、API、安全脱敏等
```
