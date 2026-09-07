# REST API 调用手册

存在 `~/.contentpilot/api_client.json`（或设置了 `CONTENTPILOT_BASE_URL`
环境变量）时，通过 REST API 完成全部操作，`base_url` 指向哪台服务就调
哪台（服务器或本机均可）。密钥来自 `~/.contentpilot/api_client.json`
（或环境变量 `CONTENTPILOT_BASE_URL` / `CONTENTPILOT_ACCESS_KEY` /
`CONTENTPILOT_SECRET_KEY`），在目标服务器 Web 设置页「API 密钥」中生成。

## 鉴权

所有请求（除登录外）携带请求头：

```
Authorization: Bearer <access_key>:<secret_key>
```

下文示例统一假设已设置：

```bash
AUTH="Authorization: Bearer ${ACCESS_KEY}:${SECRET_KEY}"
```

返回 401 = 密钥无效或已吊销；403 = 权限不足（如 review_override 需要
allow_override_review 权限位的密钥）。

## 端点映射（CLI → REST API）

base_url 形如 `http://127.0.0.1:8000`，所有路径加 `/api` 前缀。

### 文章

| CLI | REST API |
|---|---|
| `article create --title T --content C` | `POST /api/articles` `{"title": "T", "content": "C", "summary": "", "source": "manual"}` |
| `article list` | `GET /api/articles` |
| `article show <id>` | `GET /api/articles/{id}` |
| `article update <id> --status ready` | `PATCH /api/articles/{id}` `{"status": "ready"}` |
| （删除） | `DELETE /api/articles/{id}` |
| 版本列表 | `GET /api/articles/{id}/versions` |

### 发布与任务

| CLI | REST API |
|---|---|
| `publish <article_id> [platform] [-a key]` | `POST /api/publish` `{"article_id": 1, "platforms": ["juejin"], "account_ids": {"juejin": 3}}` |
| `task list` | `GET /api/tasks?status=processing` |
| `task show <id>` | `GET /api/tasks/{id}`（等价 `GET /api/publish/{id}`） |
| 任务日志 | `GET /api/tasks/{id}/logs` |
| `task retry <id>` | `POST /api/tasks/{id}/retry` |
| `task resume <id>` | `POST /api/tasks/{id}/resume` |
| `task cancel <id>` | `POST /api/tasks/{id}/cancel` |
| （删除终态任务） | `DELETE /api/tasks/{id}` |

`POST /api/publish` 请求体字段：

- `article_id`（必填）：文章必须已处于 `ready` 状态
- `platforms`（必填）：平台名数组，如 `["juejin", "csdn"]`
- `account_ids`（可选）：`{平台名: 账号id}`，浏览器平台多账号时指定
- `review_override` / `publish_override`（可选）：策略覆盖，收紧可用，
  调松需要密钥带 `allow_override_review` 权限，否则 403

### 审核

| CLI | REST API |
|---|---|
| `review list` | `GET /api/reviews` |
| `review approve <id>` | `POST /api/reviews/{id}/approve` `{"comment": ""}` |
| `review reject <id>` | `POST /api/reviews/{id}/reject` `{"comment": "原因"}` |

### 账号

| CLI | REST API |
|---|---|
| `account list` | `GET /api/accounts` |
| `account add <platform> --key K --name N` | `POST /api/accounts` `{"key": "K", "platform": "juejin", "name": "N"}` |
| `account disable <key|id>` | `PATCH /api/accounts/{id}` `{"status": "disabled"}` |
| `account enable <key|id>` | `PATCH /api/accounts/{id}` `{"status": "active"}` |

API 平台（如 cnblogs）的凭据通过 `credentials` 对象传入
（`{"username": "...", "token": "..."}`，cnblogs 另需 `blog_name`，
服务端加密存储）。浏览器平台的登录（storage_state）必须在服务器本机
完成，REST API 不提供。

### 策略

| CLI | REST API |
|---|---|
| `policy resolve --platform P --article-id N` | `GET /api/policies/resolve?platform_id=1&article_id=12` |
| `policy set <scope> [id] --review always` | `POST /api/policies` `{"scope_type": "account", "scope_id": 3, "review_mode": "always", "publish_mode": "automatic", "is_floor": false}` |
| `policy set <scope> [id] --clear` | `POST /api/policies`，对应 mode 传 `null` 即删除该层覆盖 |
| 读取某层覆盖 | `GET /api/policies?scope_type=article&scope_id=12` |

`POST /api/policies` 的 `scope_type` 取值 global / platform / account /
article / task；`--floor` 对应 `is_floor: true`（仅 platform/account 层且
review_mode=always）。

### 其他

| 用途 | REST API |
|---|---|
| 平台列表 | `GET /api/platforms` |
| 浏览器会话状态 | `GET /api/browser/sessions` |
| 发布日志（全局） | `GET /api/logs?level=error&limit=200` |
| 密钥校验（whoami） | `GET /api/auth/whoami` |

## curl 示例

```bash
# 1. 创建文章并置为 ready
curl -s -X POST "$BASE_URL/api/articles" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"title": "标题", "content": "正文", "source": "manual"}'
# → {"id": 1, ...}
curl -s -X PATCH "$BASE_URL/api/articles/1" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"status": "ready"}'

# 2. 创建发布任务（异步）
curl -s -X POST "$BASE_URL/api/publish" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"article_id": 1, "platforms": ["juejin"]}'
# → [{task_id, status: "pending", ...}]

# 3. 轮询任务状态直到终态（success/failed/cancelled/timeout）
curl -s "$BASE_URL/api/tasks/1" -H "$AUTH"

# 4. 待审核任务 → 通过
curl -s -X POST "$BASE_URL/api/reviews/1/approve" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"comment": ""}'

# 5. 失败任务重试
curl -s -X POST "$BASE_URL/api/tasks/1/retry" -H "$AUTH"
```

## 注意事项

- **异步语义**：`POST /api/publish` 立即返回任务对象，发布由 Worker
  执行；用 `GET /api/tasks/{id}` 轮询，不要假设同步完成。
- **AI 生成**：`publisher ai generate/revise/adapt` 没有对应 REST 端点，
  无 CLI 环境下由 AI 自行完成内容生产，再落库为文章。
- **浏览器登录**：`browser login` 必须在服务器本机（或容器 noVNC）完成，
  REST API 兜底时遇到 `waiting_auth` 任务，引导用户在服务器端登录后
  调 `POST /api/tasks/{id}/resume`。
- **任务状态语义与处置**：与 CLI 完全一致，见主文档「任务生命周期与
  状态语义」。
