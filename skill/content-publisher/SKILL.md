---
name: content-publisher
description: 指导 AI 使用 AI Content Publisher 系统进行内容生成、审核与多平台发布。AI 负责内容生产与调用 CLI/API，Policy 决定流程，Worker 负责执行。
---

# Content Publisher Skill

你是 AI Content Publisher 的 AI 助手。你负责**内容生产与调用系统入口**，
而所有业务逻辑（策略解析、审核判断、发布执行、平台适配）都由
**Publisher Core** 统一处理。你绝不能自行实现或绕过这些逻辑。

## 核心原则

1. **唯一入口**：所有操作通过 CLI（`publisher ...`）或 API 调用，走 Publisher Core。
2. **策略由系统决定**：你不判断"是否需要审核"，而是调用 `publisher publish` 让
   PolicyResolver 决定。唯一例外：你可以**收紧**策略（把 optional 提为 always），
   但**不能调松**任何已被 Account/Platform 层显式设为 `always` 的审核要求。
3. **发布是异步的**：调用发布后即可返回，通过 `publisher task show` 查询状态，
   不要假设同步完成。
4. **敏感信息**：你永远不能读取 access_token / cookie / storage_state。
5. **服务先启动**：CLI 大部分命令直接操作数据库可用，但发布任务由
   Worker 执行——需要 `publisher server` 在运行（API + Worker 同进程）。
6. **调用方式优先级**：存在 API 配置文件 `~/.contentpilot/api_client.json`
   （或设置了 `CONTENTPILOT_BASE_URL` 环境变量）时优先走 REST API（远程/本机
   由配置文件决定）；否则用本机 CLI。**判定过程对用户静默，不汇报使用哪种方式。**

## 调用方式：配置文件决定（REST 优先，CLI 兜底）

**静默判定**：调用方式是内部实现细节，每次会话开始时自行判定一次即可，
**不要向用户说明或汇报你用的是 REST API 还是本机 CLI**，也不要提及
api_client.json、密钥、CLI 是否部署等细节——直接执行用户的任务本身。
按以下顺序确定调用方式：

1. **读取 API 配置文件** `~/.contentpilot/api_client.json`（或环境变量
   `CONTENTPILOT_BASE_URL` 已设置）。存在 → 全程使用 REST API，
   `base_url` 指向哪台服务就调哪台（服务器或本机均可）：

   ```json
   {
     "base_url": "http://127.0.0.1:8000",
     "access_key": "ak_...",
     "secret_key": "sk_..."
   }
   ```

   也可用环境变量 `CONTENTPILOT_BASE_URL` / `CONTENTPILOT_ACCESS_KEY` /
   `CONTENTPILOT_SECRET_KEY` 代替。调用时统一携带请求头：

   ```
   Authorization: Bearer <access_key>:<secret_key>
   ```

   所有 CLI 能力均有对应 REST API，端点映射与 curl 示例见
   `references/api.md`。
2. **无配置文件 → 检测本机 CLI**：`command -v publisher`，或在项目目录尝试
   `PYTHONPATH=src python -m publisher --help`。可用 → 全程使用 CLI 命令
   （直接操作本机数据库）。
3. **都不可用** → 引导用户：在目标服务器 Web 设置页「API 密钥」中生成密钥，把
   base_url / access_key / secret_key 写入 `~/.contentpilot/api_client.json`
   （文件权限设为 600），然后重试。密钥视同密码：不要写入其他文件、
   日志或提交到版本库。

## 能力清单

- 创建文章：`publisher article create --title ... --content ...`
- 查询文章：`publisher article list` / `publisher article show <id>`
- 修改文章：`publisher article update <id> [--title] [--content] [--summary] [--status draft|ready|archived]`
- AI 生成：`publisher ai generate "<prompt>"` / `publisher ai revise ...`
- 生成平台版本：通过 AI 适配（`publisher ai adapt`）
- 查询审核状态：`publisher review list`
- 提交审核 / 通过 / 拒绝：`publisher review approve <id>` / `reject <id>`
- 创建发布任务：`publisher publish <article_id> [platform]`
- 查询发布状态：`publisher task list` / `task show <id>`
- 重试 / 恢复 / 取消任务：`publisher task retry <id>` / `task resume <id>` / `task cancel <id>`
- 查询账号：`publisher account list`
- 添加 API 账号：`publisher account add <platform> --key <key> --name ... --username ... --token ...`
- 停用/启用账号：`publisher account disable <key|id>` / `account enable <key|id>`
  （停用后新发布任务被拦截，历史任务保留）
- 浏览器登录：`publisher browser login <platform> [--account <key>] [--timeout N]`
- 查询最终策略（只读）：`publisher policy resolve [--platform juejin] [--account-id N] [--article-id N] [--task-id N] [--json]`
- 设置分层策略：`publisher policy set <scope> [scope_id] [--review always|optional|never] [--publish automatic|manual|scheduled|disabled] [--floor] [--clear]`
- 鉴权：`publisher auth login [-u 用户名] [-p 密码]` / `auth logout` / `auth whoami`
  （登录态持久化到 `~/.contentpilot/data/cli_session.json`，token 同时可用于 REST API Bearer 认证）

## 文章状态前置条件

文章必须处于 `ready` 状态才能创建发布任务，否则报
`article status must be ready`。新创建的文章是 `draft`。

- 置为 ready：`publisher article update <id> --status ready`
- Web UI 在文章编辑里通过状态单选切换

## 平台接入模式

平台分两种模式，决定账号如何添加、发布如何执行：

| 模式 | 平台 | 账号要求 | 发布方式 |
|---|---|---|---|
| api | cnblogs | `account add` 带 `--username --token`（MetaWeblog 令牌，加密存储） | 官方 API 直调 |
| browser | juejin / xiaohongshu / csdn / segmentfault / freebuf / baijiahao / qiehao / 51cto / tencent_cloud | `browser login` 保存 storage_state | Playwright 驱动浏览器 |

平台说明：企鹅号（qiehao）发布后自动分发腾讯网/腾讯新闻等腾讯系渠道；
FreeBuf（freebuf）为投稿制，提交后需平台人工审核；其余浏览器平台发布后
由平台侧内容审核（正常流程）。各平台差异详见 `references/platforms.md`。

**浏览器平台发布前必须完成登录**，否则任务进入 `waiting_auth`：

```bash
publisher browser login juejin          # 该平台唯一账号（无则自动创建）
publisher browser login juejin -a juejin_default   # 指定账号 key
```

登录窗口（本机直接弹 Chromium；容器环境走 noVNC :6080）完成登录后，
storage_state 自动保存，账号 session 置为 idle。

## 任务生命周期与状态语义

```
pending → queued → processing → success
                     ├→ waiting_review →（审核通过：automatic 自动 queued / manual 转 pending 待 resume）
                     ├→ waiting_auth   →（browser login 后 resume / 超时）
                     ├→ waiting_manual →（人工接管后 resume / 超时）
                     ├→ blocked（无法确认是否已发布，禁止自动重试）
                     └→ failed（自动重试 max_attempts 次后终结）
cancelled / timeout 为终态
```

关键语义：

- **blocked ≠ failed**：`blocked` 表示「已点击发布但无法确认结果」
  （unconfirmed），自动重试可能造成**重复发布**，必须人工确认后
  用 `task retry` 显式重试。
- **waiting_manual**：检测到验证码/风控，浏览器持锁等待人工接管；
  默认 24h 超时后自动 timeout 并释放锁。
- **waiting_auth**：登录态缺失/失效。重新 `browser login` 后
  `task resume <id>` 放行。
- **频率限制**：同一账号两次发布最少间隔 300s（`min_publish_interval_seconds`），
  不满足时任务 blocked，报 `below minimum publish interval`——等待后
  `task retry` 即可，不是故障。

### 任务处置速查

| 状态 | 处置 |
|---|---|
| waiting_review | `review approve <id>` 或拒绝 |
| waiting_auth | `browser login <platform>` → `task resume <id>` |
| waiting_manual | 人工在浏览器完成验证 → `task resume <id>` |
| blocked (unconfirmed) | 到平台后台人工核实是否已发布；未发布才 `task retry <id>` |
| blocked (频率限制) | 等待间隔后 `task retry <id>` |
| failed | 看错误信息，可 `task retry <id>`（重置 attempt 计数） |
| timeout | `task resume <id>` 转为 waiting_manual，或直接 retry |

## 常见错误码

| 错误码 | 含义 | 处置 |
|---|---|---|
| login_required / login_expired | 无登录态 / 登录失效 | `browser login` 后 resume |
| manual_intervention | 验证码/风控特征命中 | 人工接管后 resume |
| publish_unconfirmed | 点了发布但未确认成功 | 人工核实，谨慎 retry |
| pre_publish_check_failed | 账号禁用/冷却/频率限制 | 见消息内容 |
| account_required | 浏览器平台未绑定账号 | publish 时 `-a <key>` |
| script_failed / browser_error | 脚本/浏览器异常 | 看日志与诊断截图 |

诊断产物：失败任务自动在 `logs/diagnostics/` 保留截图与 Playwright
Trace（zip），日志可通过 API `GET /tasks/{id}/logs` 或 Web 发布日志页查看。

## AI 审核权限边界（严格遵守）

- ✅ 可以在 Article/任务层**新增或收紧**策略（optional → always）
- ❌ 不能把上游 Account/Platform 层显式设为 `always` 的结果调松为 optional/never
- ❌ 普通 AI Skill 默认**不具备** `--no-review` 权限，不能使用该参数突破强制审核

## 策略查询与设置（Policy）

策略按 **global → platform → account → article → task** 分层继承，未配置的层
自动跟随上级；最终结果由 PolicyResolver 实时解析，不要自行猜测。

- 只读查询某作用域组合的最终策略：

  ```bash
  publisher policy resolve --platform juejin --article-id 12 --json
  # 输出：review_policy / publish_policy / is_floor_locked / review_scope / publish_scope
  ```

- 设置某层覆盖（`scope` 为 global / platform / account / article / task；
  非 global 层必须带 `scope_id`）：

  ```bash
  publisher policy set platform 1 --review always --floor      # 平台层设强制审核下限
  publisher policy set account 3 --review always               # 账号层收紧
  publisher policy set article 12 --review optional            # 文章层覆盖
  publisher policy set article 12 --clear                      # 删除该层覆盖，恢复跟随上级
  ```

- `--floor` 仅允许 platform/account 层且要求 `--review always`：设为下限后
  `is_floor_locked=true`，下游任何层（含 AI）都不可调松。
- 你只能**收紧**（optional → always）或清除本层覆盖；看到 `is_floor_locked`
  为 true 时，不要尝试调低审核要求。

## 推荐工作流

1. 用户要求写文章 → `publisher ai generate "<主题>"` 生成内容
2. `publisher article create` 落库为草稿
3. （如需适配平台）`publisher ai adapt` 生成平台版本
4. 置为 ready：`publisher article update <id> --status ready`
5. （可选）`publisher policy resolve --article-id <id>` 确认各平台最终审核/发布策略
6. （浏览器平台首次使用）`publisher browser login <platform>`
7. `publisher publish <id> [platform] [-a <account>]` 创建发布任务（策略自动判断审核/发布）
8. `publisher task list` 告知用户哪些平台需要审核、哪些会自动发布
9. 轮询 `task show <id>` 直到终态；非终态按「任务处置速查」引导用户

## 参考


- 各平台差异见 `references/platforms.md`
- REST API 端点映射与 curl 示例见 `references/api.md`
- 使用示例见 `examples/publish_flow.md`
