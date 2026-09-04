# AI Content Publisher

AI 驱动的多平台内容生成与发布系统。

通过统一的内容管理、AI 生成、审核策略、平台适配器和异步任务系统，将一篇文章自动适配并发布到多个内容平台。

系统同时提供 **Web、CLI 和 AI Skill** 三种使用方式：

```text
                    ┌──────────────────┐
                    │      AI Agent    │
                    │   Content Skill  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │       CLI        │
                    └────────┬─────────┘
                             │
┌──────────────┐     ┌───────▼────────┐
│     Web      │────►│ Publisher Core  │
│  管理后台     │     │ 统一业务核心      │
└──────────────┘     └───────┬────────┘
                             │
                    ┌────────▼─────────┐
                    │  Task / Worker   │
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
       ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
       │ 小红书   │      │  掘金   │      │  知乎   │
       │Adapter  │      │Adapter  │      │Adapter  │
       └─────────┘      └─────────┘      └─────────┘
```

---

## 项目定位

AI Content Publisher 不是一个单纯的“文章发布脚本”，而是一套统一的内容发布基础设施。

它解决的问题是：

> **AI 负责生成内容，人可以审核和修改，系统负责把内容可靠地发布到多个平台，并持续反馈每个平台的发布状态。**

例如：

一篇技术文章生成后，可以自动转换成：

- 掘金 Markdown
- CSDN Markdown
- 知乎适合的富文本结构
- 小红书短内容 + 图片
- 微信公众号 HTML

然后根据每个平台配置的策略决定：

- 是否需要人工审核
- 是否自动发布
- 是否需要人工点击发布
- 是否定时发布
- 是否需要重新登录
- 是否需要人工处理验证码
- 发布是否成功
- 发布后的远程文章地址是什么

---

# 核心功能

## 1. AI 内容生成

支持通过配置的 AI Provider 生成文章。

支持的 Provider 类型包括：

- OpenAI
- Anthropic
- Google
- OpenRouter
- Ollama
- OpenAI Compatible API

统一 AI Provider 接口，业务层不直接依赖具体模型。

例如：

```text
输入主题
   ↓
AI 生成文章
   ↓
保存 Article
   ↓
生成 ArticleVersion
   ↓
审核 / 发布
```

支持：

- 文章生成
- 内容改写
- 标题优化
- 摘要生成
- 平台适配
- 指令式修改
- 多轮修改

---

# 2. 多平台发布

系统通过 `PlatformAdapter` 统一不同平台的发布能力。

每个平台都是独立 Adapter。

例如：

```text
PlatformAdapter
├── XiaohongshuAdapter
├── JuejinAdapter
├── CSDNAdapter
├── ZhihuAdapter
└── WechatAdapter
```

不同平台根据实际情况选择不同发布方式。

### Official API

平台提供可靠官方 API 时优先使用 API。

### Browser Automation

没有可靠发布 API 时，通过 Playwright 操作浏览器。

### Manual

平台不适合自动化时，可以直接进入人工发布流程。

### Hybrid

部分流程自动化，部分流程人工处理。

---

# 3. 内容平台适配

同一篇文章不一定适合直接发布到所有平台。

系统采用：

```text
Canonical Article
       │
       ├── Juejin Version
       ├── CSDN Version
       ├── Zhihu Version
       ├── Xiaohongshu Version
       └── Wechat Version
```

每个平台可以拥有独立的 `ArticleVersion`。

例如：

### 掘金

```text
标题
Markdown 正文
代码块
图片
```

### 知乎

```text
标题
富文本正文
图片
代码
```

### 小红书

```text
短标题
短段落
图片
标签
```

### 微信公众号

```text
标题
HTML 正文
封面
摘要
```

平台 Adapter 负责最终格式转换和发布。

---

# 4. 可配置审核

系统不会强制所有文章都经过人工审核。

审核策略可以配置为：

```text
always
optional
never
```

### always

始终需要人工审核。

```text
AI生成
 ↓
等待审核
 ↓
审核通过
 ↓
发布
```

### optional

默认可以直接发布，但允许人工介入。

### never

完全不进入审核流程。

---

# 5. 可配置发布

发布策略独立于审核策略。

支持：

```text
automatic
manual
scheduled
disabled
```

例如：

```yaml
review:
  mode: optional

publish:
  mode: automatic
```

表示：

> 默认不要求审核，生成完成后自动发布。

也可以：

```yaml
review:
  mode: always

publish:
  mode: automatic
```

表示：

> 必须人工审核，审核通过后自动发布。

或者：

```yaml
review:
  mode: always

publish:
  mode: manual
```

表示：

> 必须审核，审核通过后还需要人工点击发布。

---

# 6. 多层级策略

审核和发布策略支持不同层级。

```text
Global
  ↓
Platform
  ↓
Account
  ↓
Article
  ↓
PublishTask
```

越具体的配置优先级越高。

例如：

```text
全局：
默认自动发布

知乎：
必须审核

知乎账号 A：
审核通过后自动发布

文章：
强制人工审核
```

创建 PublishTask 时会解析最终策略，并保存到任务中。

这样后续修改全局配置不会影响已经创建的任务。

---

# 7. 多平台独立任务

一篇文章发布到多个平台时，不会使用一个“大任务”。

而是：

```text
Article
 │
 ├── PublishTask → Juejin
 ├── PublishTask → CSDN
 ├── PublishTask → Zhihu
 ├── PublishTask → Xiaohongshu
 └── PublishTask → Wechat
```

因此：

> 一个平台失败，不会影响其他平台。

例如：

```text
掘金       ✓ 发布成功
CSDN       ✓ 发布成功
知乎       ⚠ 登录失效
小红书     ⏳ 等待人工
微信公众号 ✓ 发布成功
```

---

# 8. 实时发布状态

Web 管理后台可以实时查看任务状态。

支持状态：

```text
pending
queued
processing
waiting_review
waiting_auth
waiting_manual
blocked
success
failed
cancelled
```

例如：

```text
┌────────────┬──────────────┬────────────────┐
│ 平台       │ 状态         │ 信息           │
├────────────┼──────────────┼────────────────┤
│ 掘金       │ ✓ 成功       │ 已发布         │
│ CSDN       │ ✓ 成功       │ 已发布         │
│ 知乎       │ ⚠ 登录失效   │ 等待重新登录    │
│ 小红书     │ ⏳ 人工处理   │ 等待验证码      │
└────────────┴──────────────┴────────────────┘
```

使用 SSE 向 Web 推送任务状态变化。

---

# 9. Playwright 浏览器自动化

对于没有可靠 API 的平台，可以使用 Playwright。

浏览器自动化主要负责：

- 登录
- 登录态检测
- 创建文章
- 填写标题
- 填写正文
- 上传图片
- 设置标签
- 点击发布
- 检查发布结果

浏览器自动化与业务逻辑隔离：

```text
FastAPI
   │
Publisher Core
   │
Worker
   │
PlatformAdapter
   │
Browser Layer
   │
Playwright
   │
Chromium
```

不会把 Playwright 代码直接写在 FastAPI Route 中。

---

# 10. 登录态管理

系统不保存平台账号密码作为主要登录方式。

Playwright 使用浏览器 `storage_state` 保存登录态。

例如：

```text
BrowserSession
       │
       ├── Platform
       ├── Account
       ├── Session
       └── storage_state
```

系统可以检测：

- 登录是否有效
- Session 是否过期
- 是否需要重新登录
- 是否出现验证码
- 是否出现二次认证

---

# 11. 人工接管

浏览器自动化并不是 100% 无人值守。

遇到以下情况时：

- 验证码
- 风控
- 二次验证
- 登录失效
- 页面异常
- 平台要求人工确认

任务不会直接标记为失败。

而是进入：

```text
waiting_auth
waiting_manual
blocked
```

Web 可以显示：

```text
小红书

状态：等待人工处理

原因：
检测到验证码

[打开浏览器]
[处理完成]
[继续任务]
```

人工处理完成后，Worker 可以继续执行任务。

---

# 12. 发布成功判断

系统不会简单地认为：

```text
点击发布按钮 = 发布成功
```

而是尽可能进行多重确认。

例如：

```text
点击发布
   ↓
等待页面响应
   ↓
检查成功提示
   ↓
获取 remote_id
   ↓
获取 remote_url
   ↓
必要时再次查询
   ↓
确认成功
```

如果无法确定是否成功：

```text
blocked
```

而不是直接再次发布。

这样可以降低重复发布的风险。

---

# 13. 自动重试

任务支持自动重试。

默认：

```text
max_attempts = 3
```

适合重试：

- 网络错误
- HTTP 5xx
- 页面加载失败
- 临时连接错误
- Worker 异常

不应该自动重试：

- 验证码
- 登录失效
- 风控
- 平台违规
- 账号异常
- 明确的业务错误

---

# 14. 幂等控制

系统需要避免同一篇文章重复发布。

默认幂等维度：

```text
article_id
+
article_version_id
+
platform
+
account_id
```

例如：

```text
Article #100
Version #3
Juejin
Account #1
```

只能存在一个有效 PublishTask。

---

# 15. Web 管理后台

Web 是主要的人机交互入口。

主要页面：

```text
Dashboard
Articles
Article Detail
Review
Publish Tasks
Platforms
Accounts
Browser Sessions
AI Providers
Settings
```

---

## Dashboard

查看：

- 今日生成文章
- 待审核
- 发布中
- 发布成功
- 发布失败
- 等待人工
- 登录失效的平台
- 平台健康状态

---

## Articles

管理文章：

- 创建
- 编辑
- 删除
- AI 生成
- AI 改写
- 查看版本
- 审核
- 发布
- 查看发布记录

---

## Review

查看需要审核的文章。

支持：

- 预览
- 编辑
- 通过
- 驳回
- 重新生成
- 修改后通过

---

## Publish Tasks

查看所有发布任务。

支持：

- 查看状态
- 查看日志
- 查看错误
- 重试
- 取消
- 恢复
- 人工接管

---

# 16. 平台健康状态

系统提供平台健康检查。

例如：

```text
┌────────────┬──────────┬──────────────┐
│ 平台       │ 状态     │ 最后检查      │
├────────────┼──────────┼──────────────┤
│ 掘金       │ 正常     │ 1 分钟前      │
│ CSDN       │ 正常     │ 2 分钟前      │
│ 知乎       │ 登录失效 │ 1 分钟前      │
│ 小红书     │ 正常     │ 5 分钟前      │
└────────────┴──────────┴──────────────┘
```

同时记录：

- Adapter Version
- Platform Version
- 最后测试时间
- 最后错误
- 登录状态

方便平台页面发生变化时快速定位问题。

---

# 17. CLI

系统提供 CLI。

例如：

```bash
publisher server
```

创建文章：

```bash
publisher article create
```

查看文章：

```bash
publisher article list
publisher article show 123
```

AI 生成：

```bash
publisher ai generate
```

AI 修改：

```bash
publisher ai revise 123
```

审核：

```bash
publisher review list
publisher review approve 123
publisher review reject 123
```

发布：

```bash
publisher publish 123
```

任务：

```bash
publisher task list
publisher task show 123
publisher task retry 123
publisher task resume 123
publisher task cancel 123
```

账号：

```bash
publisher account list
publisher account add juejin
```

浏览器：

```bash
publisher browser login juejin
publisher browser sessions
```

---

# 18. AI Skill

项目同时提供 AI Agent Skill。

Skill 的作用是让 AI Agent 能够使用 Publisher。

例如 AI 可以执行：

```text
用户：
帮我写一篇关于 Docker 的文章，并发布到掘金和 CSDN。
```

AI Agent：

```text
1. 调用 Publisher Skill
2. 生成文章
3. 创建 Article
4. 创建发布任务
5. 检查审核策略
6. 发布到掘金
7. 发布到 CSDN
8. 查询任务状态
9. 返回最终结果
```

AI 不需要了解：

- Playwright Selector
- Cookie
- storage_state
- 平台 API
- 浏览器启动参数
- 平台具体 DOM

这些都由 Publisher Core 和 Platform Adapter 负责。

---

# 19. AI / Web / CLI 使用同一个 Core

这是项目非常重要的设计原则。

不允许：

```text
Web → 自己实现一套发布逻辑

CLI → 自己实现一套发布逻辑

AI Skill → 自己实现一套发布逻辑
```

而应该：

```text
             Web
              │
             CLI
              │
          AI Skill
              │
              ▼
       Publisher Core
              │
       ┌──────┴──────┐
       │             │
     Policy        Service
       │             │
       └──────┬──────┘
              │
           Worker
              │
       PlatformAdapter
```

这样可以确保：

- 权限一致
- 审核规则一致
- 发布规则一致
- 状态一致
- 日志一致
- AI 和人工行为一致

---

# 技术架构

```text
┌──────────────────────────────────────────────┐
│                    Web                       │
│             Vue3 + TypeScript                │
│                 Naive UI                     │
└──────────────────────┬───────────────────────┘
                       │ HTTP / SSE
                       ▼
┌──────────────────────────────────────────────┐
│                  FastAPI                     │
├──────────────────────────────────────────────┤
│                    Core                      │
│                                              │
│ Article / Review / Policy / Publish / AI    │
├──────────────────────────────────────────────┤
│                  Services                    │
├──────────────────────────────────────────────┤
│                 Repositories                 │
├──────────────────────────────────────────────┤
│                  Database                    │
│                  SQLite                      │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│                   Worker                     │
├──────────────────────────────────────────────┤
│              Platform Adapter                │
├───────────────┬───────────────┬──────────────┤
│ Official API  │  Playwright   │    Manual    │
└───────────────┴───────────────┴──────────────┘
```

---

# 技术栈

## Backend

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic
- SQLite
- httpx
- Typer
- Rich
- Playwright

## Frontend

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- Naive UI
- Axios
- SSE

## Deployment

- Docker
- Docker Compose
- Chromium

可选：

- Xvfb
- noVNC

---

# 项目结构

```text
publisher/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── README.md
├── TECHNICAL_REQUIREMENTS.md
│
├── src/
│   └── publisher/
│       ├── cli/
│       ├── api/
│       ├── core/
│       ├── models/
│       ├── schemas/
│       ├── repositories/
│       ├── services/
│       ├── workers/
│       ├── events/
│       ├── browser/
│       ├── platforms/
│       │   ├── base.py
│       │   ├── xiaohongshu/
│       │   ├── juejin/
│       │   ├── csdn/
│       │   ├── zhihu/
│       │   └── wechat/
│       ├── ai/
│       ├── database/
│       ├── storage/
│       ├── security/
│       └── config/
│
├── web/
│
├── skill/
│   └── content-publisher/
│       ├── SKILL.md
│       ├── references/
│       └── examples/
│
├── data/
├── uploads/
└── logs/
```

---

# 数据模型

核心数据：

```text
Article
   │
   ├── ArticleVersion
   │
   └── PublishTask
          │
          ├── PublishLog
          ├── Account
          └── Platform
```

主要数据表：

```text
articles
article_versions
platforms
accounts
publish_tasks
publish_logs
ai_generations
browser_sessions
media
settings
review_policies
```

---

# 内容生命周期

典型流程：

```text
                    ┌─────────────┐
                    │ AI Generate │
                    └──────┬──────┘
                           ▼
                       Draft
                           │
                    ┌──────▼──────┐
                    │ Policy      │
                    │ Resolver    │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
          Need Review               No Review
              │                         │
              ▼                         │
        Waiting Review                  │
              │                         │
        ┌─────┴─────┐                   │
        │           │                   │
      Reject      Approve               │
        │           │                   │
        ▼           └──────────┬────────┘
      Rejected                 ▼
                            PublishTask
                                │
                                ▼
                              Worker
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
              API          Playwright         Manual
                │               │               │
                └───────────────┼───────────────┘
                                ▼
                         Success / Failed /
                         Waiting / Blocked
```

---

# 默认配置

适合个人使用的默认配置：

```yaml
review:
  mode: optional

publish:
  mode: manual
```

也可以完全自动化：

```yaml
review:
  mode: never

publish:
  mode: automatic
```

重要文章：

```yaml
review:
  mode: always

publish:
  mode: automatic
```

---

# 安全设计

系统不会要求 AI Skill 直接接触平台账号密码。

敏感数据包括：

- API Key
- Access Token
- Cookie
- Browser Session
- storage_state

需要：

- 限制文件权限
- 敏感配置加密存储
- 日志中禁止输出 Token/Cookie
- AI Skill 不直接读取敏感凭证
- API 返回时脱敏

---

# Docker 部署

项目支持 Docker Compose。

基本结构：

```text
docker compose
      │
      ├── publisher
      │     ├── FastAPI
      │     ├── Worker
      │     └── CLI
      │
      └── Chromium
```

推荐资源：

### 最低

```text
CPU: 2 Core
RAM: 4 GB
```

### 推荐

```text
CPU: 4 Core
RAM: 8 GB
```

如果同时运行多个 Chromium：

```text
CPU: 4～8 Core
RAM: 8～16 GB
```

---

# V1 开发范围

第一版不追求一次实现所有平台。

优先验证完整链路：

```text
Article
  ↓
Policy
  ↓
PublishTask
  ↓
Worker
  ↓
PlatformAdapter
  ↓
Success / Failed / Manual
  ↓
Web SSE
```

推荐第一阶段实现：

- Web
- CLI
- AI Skill
- AI Provider
- Article
- ArticleVersion
- Review Policy
- Publish Policy
- PublishTask
- Worker
- SSE
- 1 个 API 平台
- 1 个 Browser Automation 平台
- Docker

通过一个 API 平台验证 API 发布流程。

通过一个 Browser 平台验证：

- Playwright
- 登录态
- 发布
- 登录失效
- 人工接管
- 发布成功判断
- 任务恢复

---

# 后续扩展

V1 稳定后可以增加：

- 更多平台
- 多账号
- 定时发布
- 发布日历
- 批量发布
- AI 自动选题
- AI 自动生成封面
- AI 自动生成配图
- 内容模板
- 平台数据统计
- 发布数据分析
- Redis Queue
- PostgreSQL
- 多 Worker
- noVNC
- 平台插件市场

---

# 设计原则

## 统一入口

Web、CLI、AI Skill 最终都调用 Publisher Core。

## 平台隔离

每个平台必须通过 Adapter 隔离。

## API 优先

有可靠官方 API 时优先 API。

## 自动化兜底

没有 API 时使用 Playwright。

## 人工可接管

自动化遇到验证码、风控、登录异常时允许人工接管。

## 状态真实

不能因为点击了“发布”按钮就直接认为发布成功。

## 任务独立

一个平台失败不能影响其他平台。

## 策略可配置

审核和发布必须支持配置，不强制所有内容人工审核。

## AI 不绕过规则

AI 必须经过统一 Policy Resolver，不能绕过审核和发布策略。

## 可恢复

任务出现异常后应该能够：

```text
retry
resume
cancel
```

而不是只能重新创建任务。

---

# 文档说明

项目包含两类核心文档：

### README.md

面向：

- 开发者
- 使用者
- GitHub
- 项目维护者

主要介绍：

- 项目是什么
- 能做什么
- 如何运行
- 系统架构
- 核心功能
- 技术栈
- 开发范围

### TECHNICAL_REQUIREMENTS.md

面向：

- Claude Code
- Codex
- AI Coding Agent
- 项目开发者

包含详细：

- 功能需求
- 数据库设计
- API 设计
- 状态机
- Policy Resolver
- Worker
- Platform Adapter
- Playwright
- AI Provider
- CLI
- Skill
- Web 页面
- Docker
- 安全
- 测试
- 验收标准
- 开发阶段

**实现代码时应以 `TECHNICAL_REQUIREMENTS.md` 为主要开发依据。**

README 只负责项目介绍，不作为详细实现规范。

---

# 项目目标

最终目标不是简单实现：

> “自动帮我发文章”。

而是构建一个统一的：

> **AI Content → Review → Adapt → Publish → Monitor**

内容生产与分发平台。

让 AI、Web 和 CLI 都可以使用同一套发布能力：

```text
                 AI Agent
                    │
                 Skill
                    │
                  CLI
                    │
                   Web
                    │
                    ▼
            Publisher Core
                    │
          ┌─────────┴─────────┐
          │                   │
       Content             Policy
          │                   │
          └─────────┬─────────┘
                    ▼
                 Worker
                    │
           Platform Adapter
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
     API        Playwright      Manual
      │             │             │
      └─────────────┼─────────────┘
                    ▼
              Publish Result
                    │
                    ▼
             Web / CLI / AI
```

**一句话总结：**

> **AI Content Publisher 是一个面向个人使用的 AI 多平台内容生成、审核、适配、自动发布和发布状态管理系统。**
---

# V2.2 实现说明（本仓库代码）

以下内容对应 `TECHNICAL_REQUIREMENTS_V2.2.md` 的实现状态。

## 项目结构

```text
src/publisher/
├── config.py              # 环境配置（默认仅监听 127.0.0.1）
├── database.py            # SQLAlchemy 引擎，SQLite WAL 模式
├── models/                # 全部数据表（enums + tables）
├── schemas/               # Pydantic v2 模型
├── services/              # 核心业务：Policy / Article / Review / Publish / Account / Log
├── security/              # 敏感信息加密 + 日志脱敏中间件
├── auth/                  # 登录态 + API Key + allow_override_review
├── api/                   # FastAPI 路由（除 /auth/login 外全部鉴权）
├── cli/                   # Typer CLI（支持 --json）
├── workers/               # 异步 Worker（重试/超时/账号锁/超时释放）
├── events/                # SSE 事件总线
├── browser/               # Playwright 自动化层（含人工接管检测）
├── platforms/             # Adapter 基类 + 掘金/小红书示例
│   ├── base.py            # PlatformAdapter 统一接口
│   └── registry.py        # 平台注册表（新增平台不改 Core）
├── ai/                    # AI Provider（Anthropic / OpenAI 兼容）
└── storage/               # 上传文件

web/                       # Vue 3 + Naive UI 前端
skill/content-publisher/   # AI Agent Skill
docker/ + Dockerfile + docker-compose.yml   # 含 Xvfb + noVNC 可视化
tests/                     # PolicyResolver 完整测试 + 脱敏测试 + 内容安全测试
```

## 核心机制实现对照

| 文档章节 | 机制 | 实现位置 |
|---|---|---|
| §2.5, §48 | 无行 = 未配置 = 继承上级 | `models/tables.py` ReviewPolicy + `services/policy_service.py` |
| §2.6, §6, §61 | 下限（floor）不可被下游放松 | `services/policy.py` PolicyResolver |
| §9 | Article 状态与 Task 审核状态分离 | `models/tables.py`（Article 仅 draft/ready/archived） |
| §30 | 非终态部分唯一索引（幂等） | `models/tables.py` uq_task_active |
| §35 | 审核绑定 article_version_id | `models/tables.py` Review + `services/review_service.py` |
| §50 | 账号级浏览器并发锁 | `services/account_service.py` try_lock/unlock |
| §51, §53 | 日志脱敏中间件 + 加密 | `security/` redact_json + encrypt |
| §52 | 鉴权（登录态 + API Key + override 权限位） | `auth/` + `api/deps.py` |
| §54 | 发布频率限制 + 冷却 | `services/account_service.py` check_publish_allowed |
| §55 | 内容安全兜底检测 | `services/content_safety.py` |
| §21 | 等待类状态超时 + review_stale | `workers/` process_timeouts |

## 运行

```bash
# 安装
pip install -e ".[dev]"

# 测试
pytest

# 启动 Web 服务（默认 127.0.0.1:8000）
publisher server
# 或
python -m uvicorn publisher.api.app:app --host 127.0.0.1 --port 8000

# CLI
publisher article create --title "标题" --content "内容"
publisher publish 1 xiaohongshu
publisher task list --json

# 前端
cd web && npm install && npm run dev

# Docker（含 Xvfb + noVNC）
docker compose up
```

## 安全提示（文档 §52, §53）

- 默认**仅监听 `127.0.0.1`**；暴露到公网前必须先配置鉴权并修改默认密码。
- 生产环境务必通过环境变量设置 `PUBLISHER_ADMIN_PASSWORD` 与 `PUBLISHER_SESSION_SECRET`。
- `data/`、`uploads/`、`logs/`、`.env`、`storage_state` 已加入 `.gitignore`，禁止提交敏感信息。
