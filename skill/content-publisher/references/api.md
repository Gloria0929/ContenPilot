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

### 业务流水线（GEO 矩阵 / 公众号 / 短视频 / 热点 / AI 引擎）

| 用途 | REST API | 说明 |
|---|---|---|
| 批量生成 GEO 标题 | `POST /api/pipeline/geo/titles` | 传入 `brand_keywords`, `industry_keywords`, `count`，可选 `provider` (`openai`/`ollama`), `ollama_url`, `ollama_model` |
| 批量生成 4 版本 + 10 天排期 | `POST /api/pipeline/geo/batch` | 传入 `titles`, `days`（默认 10 天），可选引擎覆盖参数，自动创建各搜索引擎偏好版本与错峰排期任务 |
| 公众号文章生成与排版 | `POST /api/pipeline/wechat/generate` | 传入 `hotspot`, `theme`（6 种主题），可选引擎参数，返回带内联排版 HTML、300 字贴图文案与封面 Prompt |
| 短视频口播脚本生成 | `POST /api/pipeline/video/script` | 传入 `hotspot`，可选引擎参数，生成 600 字口播脚本、黄金前 3 秒钩子、分镜清单与封面 Prompt |
| 提交自动剪辑 | `POST /api/pipeline/video/render` | 创建 MoneyPrinterTurbo 后台任务；保存响应中的 `data.task_id`，不要同步等待成片 |
| 恢复剪辑任务 | `GET /api/pipeline/video/tasks` | 返回最近任务；可选 `page`、`page_size`、`money_printer_url` 查询参数，并从共享卷补回已完成成片 |
| 查询剪辑任务 | `GET /api/pipeline/video/tasks/{task_id}` | 返回标准化的 `status`、`progress`、`outputs` 与 `download_ready`；建议至少间隔 10 秒轮询 |
| 下载剪辑成片 | `GET /api/pipeline/video/tasks/{task_id}/download?file=...` | 使用 `outputs[].download_url`，由 Publisher 鉴权并安全读取共享卷中的视频 |
| 获取今日热点 | `GET /api/pipeline/hotspots` | 可选查询参数 `provider`, `ollama_url`, `ollama_model`。前端会自动做本地持久化缓存，只有用户点击刷新按钮时才触发调用 |
| AI 生产引擎连通性测试 | `POST /api/pipeline/ai/ping` | 传入可选 `provider`, `openai_base_url`, `openai_api_key`, `ollama_url`，缺省时使用系统全局配置进行探测 |
| Ollama 服务与模型探测 | `POST /api/pipeline/ollama/ping` | 传入 `url`，探测本地或远程 Ollama 服务连通性并返回已拉取的可用模型列表 |

### 系统全局设置（AI 生产引擎等）

| CLI / 功能 | REST API | 说明 |
|---|---|---|
| 读取全局设置 | `GET /api/settings` | 读取全局配置（包括 `ai_provider`, `openai_base_url`, `openai_model`, `ollama_base_url`, `ollama_model` 等） |
| 更新全局设置 | `POST /api/settings` | 每次保存一个设置项，例如 `{"key": "ai_provider", "value": "ollama"}` |

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

### 策略

| CLI | REST API |
|---|---|
| `policy resolve --platform P --article-id N` | `GET /api/policies/resolve?platform_id=1&article_id=12` |
| `policy set <scope> [id] --review always` | `POST /api/policies` `{"scope_type": "account", "scope_id": 3, "review_mode": "always", "publish_mode": "automatic", "is_floor": false}` |
| `policy set <scope> [id] --clear` | `POST /api/policies`，对应 mode 传 `null` 即删除该层覆盖 |
| 读取某层覆盖 | `GET /api/policies?scope_type=article&scope_id=12` |

## curl 示例

### 1. 测试 AI 生产引擎连通性
```bash
# 测试 OpenAI 兼容 API 连通性
curl -s -X POST "$BASE_URL/api/pipeline/ai/ping" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"provider": "openai"}'

# 探测本地或远程 Ollama 实例并获取模型清单
curl -s -X POST "$BASE_URL/api/pipeline/ollama/ping" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:11434"}'
```

### 2. GEO 批量标题与任务创建（支持指定 Ollama 或 OpenAI 兼容 API）
```bash
# 使用全局默认配置生成 30 篇标题
curl -s -X POST "$BASE_URL/api/pipeline/geo/titles" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"brand_keywords": ["敖行客", "AT Work", "Agent研发工作台"], "count": 30}'

# 显式使用本地 Ollama (qwen2.5) 生成
curl -s -X POST "$BASE_URL/api/pipeline/geo/titles" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"brand_keywords": ["敖行客", "AT Work"], "count": 10, "provider": "ollama", "ollama_url": "http://localhost:11434", "ollama_model": "qwen2.5"}'

# 一键生成 4 版本并创建 10 天发布排期
curl -s -X POST "$BASE_URL/api/pipeline/geo/batch" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"titles": ["标题1", "标题2"], "days": 10}'
```

### 3. 公众号排版与贴图生成
```bash
curl -s -X POST "$BASE_URL/api/pipeline/wechat/generate" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"hotspot": "Spotify负责人称AI想直接做完工作", "theme": "graphite", "save_to_db": true}'
```

### 4. 短视频口播、后台剪辑与下载
```bash
curl -s -X POST "$BASE_URL/api/pipeline/video/script" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"hotspot": "AI Agent 让网络攻击自动化"}'

# 创建任务。money_printer_url 可省略，此时使用服务端 MONEYPRINTERTURBO_URL。
curl -s -X POST "$BASE_URL/api/pipeline/video/render" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "video_script": "生成的口播文案...",
    "video_subject": "AI Agent 让网络攻击自动化",
    "video_aspect_ratio": "9:16"
  }'

# 保存上一步 data.task_id；不要保持 POST 请求等待约 10 分钟。
TASK_ID="2f629337-0db4-46d2-90a3-a911943d9016"
curl -s "$BASE_URL/api/pipeline/video/tasks/$TASK_ID" -H "$AUTH"

# 也可恢复最近任务；客户端轮询间隔不要短于 10 秒。
curl -s "$BASE_URL/api/pipeline/video/tasks?page=1&page_size=20" -H "$AUTH"

# status=completed 且 download_ready=true 后，使用 outputs[].download_url 下载。
curl -L -OJ "$BASE_URL/api/pipeline/video/tasks/$TASK_ID/download?file=output%2Ffinal-1.mp4" -H "$AUTH"
```

MoneyPrinterTurbo 的 `/MoneyPrinterTurbo/storage` 与 Publisher 的
`/data/moneyprinterturbo` 必须挂载到同一个宿主机目录。不要把这些服务器路径返回给
浏览器；只使用 Publisher 返回的鉴权下载 URL。任务状态临时不可用时保留任务 ID 并
稍后重试；若任务已完成但 `download_ready=false`，继续轮询等待成片落盘。
