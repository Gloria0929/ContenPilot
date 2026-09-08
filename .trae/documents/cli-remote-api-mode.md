# CLI 远程模式：存在 api_client.json 时优先走 REST API

## Context

用户采用「服务器 Docker 部署一套 + 远程调用」的架构。目前 CLI 命令（[src/publisher/cli/__init__.py](file:///Users/fuhao/AIProjects/ContentPilot/src/publisher/cli/__init__.py)）全部直连本地数据库，远程用户只能靠 curl / AI Skill 手拼 HTTP 请求，失去了 `publisher task list` 的命令行便利。

目标：与 Skill 的路由规则对齐——存在 `~/.contentpilot/api_client.json`（或 `CONTENTPILOT_BASE_URL` / `CONTENTPILOT_ACCESS_KEY` / `CONTENTPILOT_SECRET_KEY` 环境变量）时，CLI 命令自动翻译为 REST API 调用；无配置时维持本地数据库模式不变。

## 方案总览

新增 `src/publisher/cli/remote.py`（远程客户端 + 配置加载 + 各命令的远程执行函数），在 `cli/__init__.py` 每个可路由命令的函数体开头加一个分支。`httpx` 已是依赖（pyproject.toml L18），无需新增包。

## 1. 新模块 `src/publisher/cli/remote.py`

**配置加载**（环境变量 > 配置文件）：
- 环境变量 `CONTENTPILOT_BASE_URL` / `CONTENTPILOT_ACCESS_KEY` / `CONTENTPILOT_SECRET_KEY`
- 文件 `~/.contentpilot/api_client.json`：`{base_url, access_key, secret_key}`
- `remote_client()` 返回 `RemoteClient | None`：三项齐全 → 返回客户端；**文件存在但缺字段/损坏 → 打印红色错误并退出**（不静默回落本地——用户预期远程，静默写本地库会造成脑裂）；文件不存在且无环境变量 → `None`（本地模式）

**RemoteClient**：
- `request(method, path, *, params=None, json_body=None) -> Any`：统一加 `/api` 前缀、`Authorization: Bearer ak:sk` 头，返回解析后的 JSON
- 错误统一抛 `RemoteError`（仅消息，符合「CLI 只显示错误信息」的项目约定）：
  - 连接失败 → `无法连接到 {base_url}：服务是否在运行？`
  - 401 → `API Key 无效或已吊销，请在 Web 设置页重新生成并更新 api_client.json`
  - 403/400/404 → 取 FastAPI 响应体 `detail` 字段原样显示
- 复用 `api/deps.py` 的 Bearer 格式（`ak:sk` 拼接，见 [deps.py:19-25](file:///Users/fuhao/AIProjects/ContentPilot/src/publisher/api/deps.py#L19-L25)）

## 2. 各命令的远程路由（映射依据 [api.md](file:///Users/fuhao/AIProjects/ContentPilot/skill/content-publisher/references/api.md)）

在 `cli/__init__.py` 每个命令函数体开头添加统一模式：

```python
if (c := remote_client()):
    _remote_article_list(c, json_=json_)
    return
```

远程执行函数放在 `remote.py`，输出格式与本地模式保持一致（表格 / 简洁行 / `--json`）。

| CLI 命令 | REST 调用 | 备注 |
|---|---|---|
| `article create` | `POST /api/articles` | body: title/content/summary/source |
| `article list` | `GET /api/articles` | 表格列 id/title/status 不变（响应含额外 aggregate_status，--json 时原样输出） |
| `article show` | `GET /api/articles/{id}` | 404 → `article N not found` |
| `article update` | `PATCH /api/articles/{id}` | 只传提供的字段（exclude_unset 语义） |
| `publish` | `POST /api/publish` | 见下方「publish 远程解析」 |
| `task list` | `GET /api/tasks?status=` | 字段名与本地一致 |
| `task show` | `GET /api/tasks/{id}` | |
| `task retry/resume/cancel` | `POST /api/tasks/{id}/retry\|resume\|cancel` | |
| `review list` | `GET /api/reviews` | 保持 `#id task=... version=...` 行格式（响应含 article_title 等增强字段，--json 原样输出） |
| `review approve/reject` | `POST /api/reviews/{id}/approve\|reject` | body `{"comment": ...}` |
| `account list` | `GET /api/accounts` | |
| `account add` | `POST /api/accounts` | credentials 组装逻辑（username+token+cnblogs blog_name）与本地一致 |
| `account disable/enable` | `GET /api/accounts` → 解析 key/id → `PATCH /api/accounts/{id}` | body `{"status": "disabled"/"active"}` |
| `policy resolve` | `GET /api/policies/resolve` | platform 名 → 先 `GET /api/platforms` 查 id |
| `policy set` | `POST /api/policies` | scope/scope_id/review_mode/publish_mode/is_floor 映射 |
| `auth whoami` | `GET /api/auth/whoami` | 远程模式下校验远程密钥，输出用户名 |

**publish 远程解析**（复刻本地逻辑 cli/__init__.py:394-443，但数据来自 REST）：
- 平台校验：`GET /api/platforms`
- `--account key|id` → `GET /api/accounts` 在客户端解析出 id 及其 platform（未指定平台时用账号所属平台）
- 单平台未指定账号 → 该平台唯一账号时自动绑定 account_ids
- `--review` → `review_override="always"`；`--no-review` → `"never"`（服务端校验密钥 `allow_override_review` 权限位，403 时显示服务端错误信息）
- 返回任务列表，按本地相同格式逐行打印

## 3. 保持本地（不路由）的命令

- `server`：启动服务本身，天然本地
- `ai generate/revise/adapt`：不碰数据库（纯 AI 调用），无需改动
- `browser login`：必须在本机跑真实浏览器（风控场景），且无 storage_state 上传端点——保持本地行为，但远程模式下附加一行提示：「远程模式：登录态保存在本机，需将 storage_state 同步到服务器 data 目录」
- `auth login/logout`：管理本地模式凭证；远程模式下打印提示「远程模式使用 api_client.json 密钥，请在 Web 设置页管理」

## 4. 既有代码的小改动

- `cli/__init__.py` 的 `_to_dict()`（L51）：增加 `isinstance(obj, dict)` 直接返回的分支，使远程 JSON 响应能走 `_print_json`
- 在 `main()`（L837-846）增加 `except RemoteError` 分支统一打印 `[red]消息[/red]` + exit(1)，各命令不必重复捕获

## 5. 文档同步

- [README.md](file:///Users/fuhao/AIProjects/ContentPilot/README.md)（L176-201 鉴权章节、L408 调用策略）：明确「CLI 存在 api_client.json 时自动走 REST，远程/本地由配置决定」，消除此前「CLI 始终本地」的歧义表述
- [skill/content-publisher/SKILL.md](file:///Users/fuhao/AIProjects/ContentPilot/skill/content-publisher/SKILL.md) / `references/api.md`：路由描述不变（CLI 行为与 Skill 约定一致了），可在注意事项中补一句 CLI 同样支持该路由

## 验证

1. 本机起服务：`PYTHONPATH=src python -m publisher server`，Web 设置页生成 API 密钥
2. 写 `~/.contentpilot/api_client.json`（base_url 指向 `http://127.0.0.1:8000`，权限 600）
3. 逐条验证远程路由：`publisher article create --title t --content c` → `article list` → `article show 1` → `article update 1 --status ready` → `publish 1 juejin` → `task list` / `task show` → `review list` / `approve` → `account list/add/disable/enable` → `policy resolve/set` → `auth whoami`
4. 验证 `--json` 输出与非 JSON 表格输出与本地模式观感一致
5. 错误路径：错误密钥（401）、停服务（连接失败）、不存在的 id（404）、`--no-review` 无权限密钥（403）——确认只显示简洁错误信息，无 traceback
6. 删除（或改名）api_client.json → 确认回落本地模式（原行为不变）；文件存在但缺 secret_key → 确认报错退出而非回落
7. `PYTHONPATH=src pytest`（现有测试不回归）
