# AI Content Publisher V2.2
## AI 多平台内容生成、审核与自动发布系统技术需求文档

> 文档版本：V2.2（在 V2.1 基础上修订，修订点见文末第 76 节）
> 项目类型：个人使用 / 可扩展多平台内容发布系统
> 核心模式：AI 生成 → 内容适配 → 可配置审核 → 多平台发布 → 实时状态跟踪

---

# 1. 项目概述

AI Content Publisher 是一个统一的 AI 内容生产、多平台内容适配和发布系统。

系统提供：

- Web 管理后台
- CLI 命令行
- AI Agent Skill
- AI 内容生成
- 内容编辑
- 可配置审核流程
- 多平台内容适配
- 官方 API 发布
- Playwright 浏览器自动化
- 人工接管
- 多账号管理
- 发布任务管理
- 实时发布状态
- 发布日志和错误诊断

核心目标：

> **AI、Web、CLI、Skill 都只是入口，所有业务逻辑统一进入 Publisher Core。**

---

# 2. 核心设计原则

## 2.1 统一 Core

不能出现：

```text
Web → 一套业务逻辑
CLI → 一套业务逻辑
AI Skill → 一套业务逻辑
```

必须：

```text
Web ─────┐
CLI ─────┼──→ Publisher Core
Skill ───┘
```

## 2.2 平台 Adapter

平台发布必须通过统一 Adapter。

```text
PlatformAdapter
│
├── Official API
├── Browser Automation
├── Manual
└── Hybrid
```

不同平台可以使用不同实现方式。

## 2.3 官方 API 优先

平台存在可靠的官方发布 API 时优先使用 API。

没有合适 API 时使用 Playwright。

不能假设：

> 获取 OAuth Token 后就一定拥有发布权限。

平台实际发布能力必须根据当前开放平台权限决定。

## 2.4 审核流程可配置

**系统不再强制所有文章必须经过 Web 人工审核。**

审核是一个可配置策略，可以按 全局 / 平台 / 账号 / 文章 / 发布任务 五个层级进行覆盖。

## 2.5 【新增】策略字段必须支持"未配置 = 继承上级"语义

这是 V2.1 遗留的一个关键漏洞：如果每一层的策略字段永远有一个具体值（例如系统给 Article 一个默认值 `optional`），那么它将**永远覆盖**掉更上层的设置，多级覆盖机制就会形同虚设。

因此必须明确：

> **每一层的策略只有在"被用户显式设置过"时才参与 Resolve；未显式设置 = NULL = 继续向上一级查找。**

技术上，这意味着策略不应作为 Article / Account / Platform 表上的普通列（普通列很难区分"用户没填"和"用户填了默认值"），而应统一存放在一张独立的、按 scope 建行的策略表中（见第 48 节）：**没有对应的行，就代表这一层没有配置。**

## 2.6 【新增】账号 / 平台级别的强制审核是不可被文章覆盖的下限

V2.1 的优先级顺序（Task > Article > Account > Platform > Global）隐含了一个问题：Article 级别的设置会覆盖 Account / Platform 级别的设置。但 Article（内容维度）和 Account / Platform（发布目标维度）其实是两个不同的轴，不是严格嵌套关系。

如果用户为一个高风险账号（例如企业官方号）在 Account 层显式设置了 `review = always`，其本意是"任何经由这个账号发布的内容都必须审核"，这个约束不应该被文章层的设置（哪怕是 AI 顺手带的默认值）绕过。

因此规则修订为：

> **Account / Platform 层如果显式设置为 `always`，视为该层级的强制下限（floor）。Article / Task 层可以把审核要求"调严"（例如从 optional 改成 always），但不能把已被 Account/Platform 层强制为 always 的要求"调松"（改成 optional 或 never）。**

这一条对应第 12 节"AI 不能绕过强制审核"的安全目标，也是本次修订中最重要的一条设计约束（详见第 61 节 PolicyResolver 的实现要求）。

---

# 3. 整体架构

```text
                         AI Agent
                            │
                            ▼
                         Skill
                            │
                            ▼
                           CLI
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Publisher Core                        │
│                                                            │
│ Article │ AI │ Review │ Version │ Policy │ Publish        │
│ Task    │ Account │ Platform │ Event │ Storage │ Auth     │
└───────────────────┬───────────────────────┬──────────────┘
                    │                       │
                    ▼                       ▼
                 SQLite              Platform Adapter
                                            │
                              ┌─────────────┼─────────────┐
                              ▼             ▼             ▼
                             API         Browser        Manual
                                            │
                                            ▼
                                         Playwright
                                            │
                                            ▼
                                         Chromium

                    ▲
                    │
             Auth + REST + SSE
                    │
                    ▼
               Web Console
```

> 相比 V2.1，Core 中新增 **Auth**（鉴权）模块（见第 52 节），且 Web/CLI/API 的所有请求都必须先经过鉴权层。

---

# 4. 内容生命周期

文章生命周期不再简单等于 `生成 → 审核 → 发布`，而是：

```text
生成
 ↓
编辑
 ↓
根据发布策略判断（PolicyResolver，作用于具体 PublishTask）
 ↓
 ├── 无需审核 → 发布
 │
 └── 需要审核 → 等待审核
                       ↓
                    审核通过
                       ↓
                      发布
```

**注意**：审核判断的结果作用在"文章 × 平台"这个粒度（即 PublishTask），而不是文章整体。同一篇文章在不同平台上可以同时处于不同阶段（详见第 9、27 节）。

---

# 5. 审核策略

系统提供三个基础模式：`always` / `optional` / `never`。

## 5.1 always

始终需要审核，适合重要文章、品牌内容、商业文章、对外正式内容。

## 5.2 optional

默认不强制审核，但允许人工介入。用户可以在 Web 中选择 [审核后发布] / [直接发布]，也可以通过 CLI 指定 `publisher publish 123 --review`。

## 5.3 never

完全不进入审核流程，适合个人笔记、测试文章、自动化内容、已经高度信任的 AI 工作流。

---

# 6. 审核策略优先级与继承规则【修订】

审核配置支持多层覆盖，作用范围（scope）从粗到细为：

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

解析时按 **Global → Platform → Account → Article → Task** 的顺序依次读取，**只有某一层显式配置过（对应 scope 存在一行策略记录）才会覆盖前面的结果**，未配置的层级直接跳过（继承上一步的结果）。

在此基础上叠加第 2.6 节的下限规则：

> 如果 Platform 或 Account 层显式设置为 `always`，那么无论 Article / Task 层如何设置，最终结果里 `review_mode` 不能低于 `always`（即最终一定是 `always`）。

举例：

```text
全局：            always
小红书（Account）： always     ← 显式设置为 always，成为下限
某篇文章（Article）： never    ← 试图放松

解析结果：仍然是 always（Account 层的 always 是下限，不能被 Article 覆盖）
```

而如果 Account 层没有配置（未显式设置），Article 的 `never` 则正常生效：

```text
全局：            always
小红书（Account）： 未配置
某篇文章（Article）： never

解析结果：never（Article 是当前最具体的显式配置，且没有下限限制）
```

Task 层始终拥有最高优先级，但同样受"是否试图放松被下游 Account/Platform 强制的 always"约束——如果 Task 层试图把已被下限锁定的 `always` 改成 `never`，必须走第 12 节的显式授权机制。

---

# 7. 推荐配置模型

配置（Global）：

```yaml
review:
  mode: always
```

平台（Platform）：

```yaml
platforms:
  juejin:
    review: never
  xiaohongshu:
    review: always
  zhihu:
    review: optional
```

账号（Account）：

```yaml
accounts:
  xhs_account_001:
    review: always
```

文章（Article，写入 review_policies 表，scope=article）：

```text
scope_type = article
scope_id   = 123
review_mode = optional
```

任务（Task，写入 review_policies 表，scope=task，仅当次生效）：

```text
scope_type = task
scope_id   = 5001
review_mode = never
```

> 注意：文章、任务层的配置**不再**作为 Article / PublishTask 表上的普通字段直接存在，而是统一写入 `review_policies` 表（见第 48 节），避免第 33 节提到的数据冗余问题。

---

# 8. 审核策略不能只保存 Boolean

不推荐：`require_review = true`

推荐：`review_policy` 取值 `always / optional / never`

原因：`optional` 和 `never` 的业务含义不同，Boolean 无法表达"允许但不强制"这种中间态。

---

# 9. 状态设计：Article 状态与 Task 审核状态分离【修订】

V2.1 中 Article 状态机里混入了 `pending_review / approved / rejected` 这类审核相关状态，但第 17 节明确指出审核策略应作用于 PublishTask 而不是 Article——同一篇文章在不同平台可以同时处于不同的审核阶段。因此 V2.2 把两套状态机拆开：

## 9.1 Article 状态（只反映内容本身的编辑/生命周期状态）

```text
draft        编辑中
ready        内容已完成，可以创建发布任务（不代表任何平台已通过审核）
archived     已归档，不再参与发布
```

Article 层不再保存 `pending_review / approved / rejected`，这些状态属于"文章 × 平台"这一粒度，见 9.2。

## 9.2 Review（审核记录）状态 —— 绑定具体 PublishTask / ArticleVersion

```text
pending      等待审核
approved     审核通过
rejected     审核被拒绝
```

`rejected` 之后允许两种去向，需在实现时二选一并在 Web 上明确提示：

- 允许用户编辑文章生成新版本后重新提交审核（回到 `pending`，绑定新的 `article_version_id`）；
- 或该 PublishTask 直接终结为 `failed`，用户需要手动创建新任务。

推荐前者，体验更连贯。

## 9.3 Article 的"聚合展示状态"（只读，非持久化状态机）

Web Dashboard 上展示的"文章整体状态"（如 `partial_success`）是**根据该文章下所有 PublishTask 的当前状态实时聚合计算出来的只读视图**，不是 Article 表里存储的一个状态字段。聚合规则见第 27 节。

---

# 10. 审核流程

## always

```text
AI Generate → Article(ready) → 为该平台创建 PublishTask
      ↓
ReviewPolicy(该 Task) = always
      ↓
Review: pending
      ↓
Web / CLI / API 审核
      ↓
Review: approved
      ↓
Task: queued
      ↓
Publish
```

## optional

```text
AI Generate → Article(ready) → 创建 PublishTask
      ↓
ReviewPolicy(该 Task) = optional
      ↓
Task: ready
      │
      ├── 直接发布
      │
      └── 用户主动送审
              ↓
           Review: approved
              ↓
            Publish
```

## never

```text
AI Generate → Article(ready) → 创建 PublishTask
      ↓
ReviewPolicy(该 Task) = never
      ↓
Task: ready
      ↓
Publish
```

---

# 11. 审核入口

审核不限制为 Web，支持 Web / CLI / API 三种入口：

```text
Web： [通过] [拒绝]
CLI： publisher review approve 123 / publisher review reject 123
API： POST /reviews/{id}/approve / POST /reviews/{id}/reject
```

三个入口都必须调用同一个 Core.PolicyResolver + Core.ReviewService，不允许各自实现判断逻辑（见第 62 节）。

---

# 12. AI 审核权限边界【修订】

默认：

> AI 不能自行修改审核策略，尤其不能把已经被某一层显式设置为 `always` 的策略调松为 `optional` 或 `never`。

结合第 2.6 节的"下限"规则，这里进一步明确：

- AI 可以在 Article / Task 层新增或收紧策略（例如把 `optional` 改成 `always`）；
- AI **不能**在任何层级把一个已经被上游（Account 或 Platform）显式设为 `always` 的结果调松；
- 只有**人类用户**通过 Web/CLI 显式操作，或系统管理员配置的"明确授权的自动化策略"（需要有独立的权限标记，见第 52 节鉴权部分，例如某个 API Key 被标记为 `allow_override_review=true`）才能突破下限。

`--no-review` 这类 CLI 覆盖参数必须校验调用方权限，普通 AI Skill 默认不具备该权限。

---

# 13. 自动化发布策略：审核策略与发布策略分离

建议把"审核策略"和"发布策略"分开：

```text
review_policy   → always / optional / never
publish_policy  → automatic / manual / scheduled / disabled
```

例如：

```yaml
review:
  mode: always
publish:
  mode: manual
```

或：

```yaml
review:
  mode: never
publish:
  mode: automatic
```

---

# 14. Publish Policy

```text
automatic  满足条件后自动创建发布任务
manual     需要用户点击发布
scheduled  到指定时间自动发布
disabled   禁止发布
```

---

# 15. 审核与发布组合

| 审核 | 发布 | 行为 |
|---|---|---|
| always | automatic | 审核通过后自动发布 |
| always | manual | 审核通过后等待人工点击发布 |
| optional | automatic | 默认自动发布，可先审核 |
| optional | manual | 默认人工发布 |
| never | automatic | AI 生成后自动发布 |
| never | manual | AI 生成后等待人工点击 |
| 任意 | scheduled | 满足审核条件后定时发布 |
| 任意 | disabled | 不允许发布 |

---

# 16. 最推荐的默认配置

个人使用场景：

```yaml
review:
  mode: optional
publish:
  mode: manual
```

如果以后想完全自动化：

```yaml
review:
  mode: never
publish:
  mode: automatic
```

---

# 17. 多平台审核策略（核心原则）

同一篇文章：

```text
├── 掘金 → 不审核 → 自动发布
├── CSDN → 不审核 → 自动发布
├── 知乎 → 审核 → 等待
└── 小红书 → 审核 → 等待
```

因此：

> **审核策略最终应该应用到 PublishTask，而不是简单绑定 Article。这是多平台发布系统非常重要的一点，也是 V2.2 拆分状态机（第 9 节）和数据模型（第 33、48 节）的根本原因。**

---

# 18. Article 与 PublishTask 的关系

```text
Article
   │
   ├── Juejin Task      review = never
   ├── CSDN Task        review = never
   ├── Zhihu Task        review = always
   └── XHS Task          review = always
```

同一篇文章可以针对不同平台使用不同审核规则。

---

# 19. PublishTask 创建流程【修订：加锁 + 唯一数据来源】

```text
用户/AI 请求发布
        ↓
读取 Article（校验 status = ready）
        ↓
生成 / 复用 ArticleVersion（按 article_id + platform 做内容适配）
        ↓
获取幂等锁：(article_version_id, platform, account_id) 在非终态任务中唯一（见第 30 节）
        ↓
PolicyResolver 依次读取 review_policies 表中
  Global → Platform → Account → Article → Task Override
（应用第 2.6 节下限规则）
        ↓
Resolve Policy → { review_policy, publish_policy }
        ↓
创建 PublishTask，并把 Resolve 出的最终策略、article_version_id 一并写入
        ↓
释放锁 / 任务进入 pending
```

最终任务保存 `review_policy` / `publish_policy` 的**快照值**（而不是引用），避免后续配置改变导致正在执行中的任务行为不确定——这一点与 V2.1 保持一致。

---

# 20. PublishTask 状态

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
timeout   【新增，见第 21 节】
```

---

# 21. 等待类状态的超时策略【新增】

V2.1 只要求"浏览器任务必须有超时"，但没有约束 `waiting_review / waiting_auth / waiting_manual` 这些"等人处理"的状态本身要不要有超时。V2.2 明确：

- `waiting_review`：默认不设强制超时（审核本来就该等人），但 Web/CLI 需要提供"超过 N 天未处理"的提醒（事件 `task.review_stale`），具体阈值可配置，默认 3 天。
- `waiting_auth` / `waiting_manual`：必须设置超时（默认 24 小时可配置），超时后任务状态转为 `timeout`，并从 `waiting_*` 释放对应账号的浏览器并发锁（见第 50 节），避免长期占用资源或阻塞同账号的其它任务。
- `timeout` 状态允许用户手动 `resume` 重新进入 `waiting_manual`，或 `cancel` 终结任务。

---

# 22. 任务示例

```text
Task #1001
Platform: Xiaohongshu
Review: always
Publish: automatic
Status: waiting_review
```

Web：

```text
小红书 · 等待审核
[查看文章] [审核通过] [拒绝]
```

审核通过：`waiting_review → queued → processing`

---

# 23. 浏览器自动化

对于没有可靠官方 API 的平台，使用 Playwright：

```text
PublishTask → BrowserWorker → Playwright → Chromium → Platform
```

支持：登录态 / Cookie / LocalStorage / storage_state / 页面操作 / 图片上传 / 内容填写 / 发布 / 状态检测 / 截图 / Trace。

---

# 24. 浏览器登录

首次：

```text
publisher browser login xiaohongshu
        ↓
启动 Chromium → 用户登录 → 人工完成验证码 → 保存 storage_state
```

后续：

```text
Worker → Load storage_state → Check Login → Publish
```

登录失效 → `waiting_auth`

---

# 25. 人工接管【修订：明确 V1 的可视化落地方案】

浏览器自动化过程中遇到验证码 / 风控 / 手机验证 / 二次确认 / 页面异常 → 进入 `waiting_manual`。

V2.1 的问题：第 65 节验收标准要求 V1 必须支持"人工接管"，但可视化浏览器接入（noVNC）在原文档中被列为"后续扩展"。如果 V1 默认以 `HEADLESS=true` 部署在 Docker 里，用户点击"打开浏览器"时实际看不到页面，无法完成验证码——人工接管功能名存实亡。

**V2.2 修订：把"最简可视化人工接管"纳入 V1 范围**，二选一均可，由实现方按部署条件选择：

- 方案 A（推荐，容器化部署）：容器内运行 `Xvfb + x11vnc/noVNC`，Web 端通过内嵌 iframe 展示 noVNC 页面，用户直接在浏览器里完成验证码操作；
- 方案 B（本地部署简化版）：Worker 检测到需要人工接管时，以 `HEADLESS=false` 重新拉起一个可见的 Chromium 窗口（仅限本机 / 非容器场景），用户在宿主机桌面直接操作。

两种方案至少要实现一种，且必须在 V1 验收标准（第 70 节）中体现，不能推迟到"后续扩展"。

人工完成后：`resume → processing`。

---

# 26. 发布成功判断

不能只判断"点击发布按钮成功"，必须尽可能确认：`发布成功提示 + 远程 ID + 远程 URL`。如果无法确认 → `blocked`（避免重复发布）。

---

# 27. 多平台任务与 Article 聚合状态【修订】

一次发布：

```text
Article #100
├── Juejin
├── CSDN
├── Zhihu
├── Xiaohongshu
└── WeChat
```

每个平台独立运行，例如：

```text
Juejin       SUCCESS
CSDN         SUCCESS
Zhihu        WAITING_REVIEW
XHS          WAITING_MANUAL
WeChat       FAILED
```

**聚合规则（对应第 9.3 节的"只读聚合状态"）**：

```text
若存在任意 Task 处于 waiting_*      → 文章聚合状态 = "processing"
否则若存在 Task = FAILED 且存在 Task = SUCCESS → "partial_success"
否则若所有 Task = FAILED             → "failed"
否则若所有 Task = SUCCESS            → "published"
```

聚合状态只用于 Dashboard 展示，不写入 Article 表，每次查询时实时计算（或用物化视图 / 缓存加速，但不作为权威数据源）。

---

# 28. Worker

发布必须异步执行：

```text
错误：POST /publish → 直接执行 Playwright
正确：POST /publish → 创建 PublishTask → Queue → Worker → PlatformAdapter
```

---

# 29. 重试

默认 `max_attempts = 3`。

可自动重试：网络错误 / API 5xx / 页面加载失败 / 浏览器启动失败。

不应自动重试（进入 `waiting_auth / waiting_manual / blocked`）：验证码 / 登录失效 / 风控 / 内容违规 / 账号异常。

---

# 30. 幂等设计【修订：覆盖非终态】

V2.1 的幂等键只防止"任务成功后重复创建"，没有约束任务还在**非终态**（pending / queued / processing / waiting_*）时被重复创建的情况（例如 Web 和 CLI 几乎同时点击发布）。

逻辑幂等键：

```text
article_version_id + platform + account_id
```

**V2.2 修订**：在数据库层为 PublishTask 增加**部分唯一索引**（partial unique index），约束条件为：

```sql
-- 伪代码示意
CREATE UNIQUE INDEX uq_task_active
ON publish_tasks (article_version_id, platform, account_id)
WHERE status NOT IN ('success', 'failed', 'cancelled', 'timeout');
```

即：同一个 `(article_version_id, platform, account_id)` 组合，在"未结束"的任务里最多只能存在一条记录；已结束（success/failed/cancelled/timeout）的任务不受此约束，允许后续重新发起（生成新任务）。这样即可同时满足"防止并发重复创建"和"允许失败后重试/新版本重发"两个需求。

---

# 31. 平台 Adapter 接口

```python
class PlatformAdapter:
    async def capabilities(self): ...
    async def check_account(self, account): ...
    async def authorize(self, account): ...
    async def validate(self, content): ...
    async def create_draft(self, content): ...
    async def publish(self, content): ...
    async def get_status(self, remote_id): ...
    async def cancel(self, task): ...
```

---

# 32. Platform Capabilities

```json
{
  "platform": "xiaohongshu",
  "mode": "browser",
  "supports_text": true,
  "supports_images": true,
  "supports_video": false,
  "supports_draft": true,
  "supports_publish": true,
  "supports_status": false
}
```

---

# 33. Article（数据模型）【修订：移除策略字段】

字段：

```text
id
title
content
summary
cover_image
status          -- 仅限 draft / ready / archived（见第 9.1 节）
source
created_at
updated_at
```

**与 V2.1 的差异**：不再包含 `review_policy` / `publish_policy` 字段。文章层的策略覆盖统一写入 `review_policies` 表（scope=article），避免"Article 表字段"和"review_policies 表记录"两处数据源互相打架（见第 2.5、7、48 节）。

---

# 34. ArticleVersion

```text
id
article_id
platform
title
content
images
cover_image
metadata
version
created_at
updated_at
```

```text
原始文章
   │
   ├── 掘金 Markdown
   ├── CSDN Markdown
   ├── 知乎富文本
   ├── 小红书短内容
   └── 微信 HTML
```

---

# 35. Review 记录与版本绑定【新增】

V2.1 未明确"审核通过的是哪个版本的内容"。V2.2 新增独立的 `reviews` 表，强制绑定具体版本：

```text
id
task_id                -- 绑定具体 PublishTask
article_version_id     -- 绑定具体内容版本，而不是笼统绑定 article_id
status                 -- pending / approved / rejected
reviewer               -- 审核人（用户标识 / API Key 标识）
comment
created_at
updated_at
```

规则：

> 如果 Article 在 `approved` 之后又产生了新的 `ArticleVersion`（内容被重新编辑），该 Task 对应的审核记录**不再对新版本生效**，必须重新走一遍 Review 流程。第 63 节"审核后自动发布"的实现必须在真正执行发布前，校验 `PublishTask.article_version_id` 与最新 `approved` 的 `reviews.article_version_id` 一致，不一致则打回 `waiting_review`。

这一条直接堵住了"审核过的内容"和"实际发布的内容"不一致的漏洞。

---

# 36. AI Provider

支持：OpenAI / Anthropic / Google / OpenRouter / Ollama / OpenAI Compatible。

```python
class AIProvider:
    async def generate(self, prompt): ...
    async def revise(self, content, instruction): ...
    async def adapt(self, content, platform): ...
```

---

# 37. Web 页面

```text
Dashboard / Articles / AI Writer / Review / Publish Tasks
Accounts / Platforms / Browser Sessions / Logs / Settings / Login
```

> 新增 **Login** 页面，对应第 52 节鉴权要求。

---

# 38. Review 页面【修订】

需要显示：文章 / 目标平台 / **当前审核对应的 ArticleVersion** / 审核策略 / 发布策略 / 创建时间。

支持：[通过] [拒绝] [编辑] [AI 修改]。

如果策略是 `never`，则无需进入 Review 页面。

若审核期间文章产生了新版本，页面需要明确提示"内容已更新，当前审核针对的是旧版本"，并提供"刷新到最新版本重新审核"的操作（对应第 35 节）。

---

# 39. Article 页面【修订】

显示当前文章在各平台上**解析后**的审核 / 发布策略（只读展示 PolicyResolver 的计算结果，而不是一个可以随意覆盖的单一字段）。

允许用户为该文章新增/修改 **Article 层的策略覆盖**（写入 `review_policies` 表，scope=article）：

```text
审核： [始终审核] [可选审核] [无需审核] [跟随上级]
发布： [自动发布] [手动发布] [定时发布] [禁止发布] [跟随上级]
```

"跟随上级"即删除该 scope 对应的行（回到未配置状态，参见第 2.5 节）。如果某个下游账号/平台已把 `always` 设为下限，界面需要显示提示："该文章在小红书上强制审核，无法调低"。

---

# 40. Publish 页面

用户选择 文章 + 平台 + 账号，系统展示每个平台**最终解析后**的策略：

```text
掘金     审核：无需审核   发布：自动
小红书   审核：始终审核（账号层强制，不可调）  发布：自动
知乎     审核：可选       发布：手动
```

用户可以清楚看到"这次发布到底会不会等待审核"，以及是否是被下游强制的。

---

# 41. Dashboard

显示：文章总数 / 待审核 / 待发布 / 发布中 / 发布成功 / 发布失败 / 等待授权 / 等待人工 / 超时。

---

# 42. SSE 实时事件

```text
task.created / task.queued / task.started / task.progress
task.waiting_review / task.waiting_auth / task.waiting_manual
task.review_stale     【新增，见第 21 节】
task.timeout          【新增，见第 21 节】
task.success / task.failed / task.retry / task.completed
```

---

# 43. CLI

```bash
publisher server
publisher article create / list / show <id>
publisher ai generate / revise
publisher review list / approve <id> / reject <id>
publisher publish <id>
publisher task list / show <id> / retry <id> / resume <id> / cancel <id>
publisher account list / add <platform>
publisher browser login <platform>
publisher auth login / logout / whoami   【新增，见第 52 节】
```

---

# 44. CLI 审核控制

```bash
publisher publish 123               # 根据配置自动判断
publisher publish 123 --review      # 本次强制走审核
publisher publish 123 --no-review   # 本次跳过审核（仅在权限允许且未被下限锁定时生效）
```

`--no-review` 是否允许使用必须受到调用方权限 + 目标 scope 是否被下限锁定（第 2.6 节）双重限制，不能让普通 AI Skill 随意绕过强制审核。

---

# 45. CLI JSON

```bash
publisher article list --json
publisher task list --json
publisher task show 1001 --json
```

AI 不需要解析终端格式化文本。

---

# 46. Skill

Skill 负责指导 AI 使用 Publisher。

能力：创建文章 / AI 生成 / 修改文章 / 生成平台版本 / 查询审核状态 / 提交审核 / 创建发布任务 / 查询发布状态 / 重试任务 / 恢复任务 / 查询账号。

Skill 不负责：Playwright selector / Cookie / OAuth / 平台 API / 浏览器实现，这些全部由 Publisher Core 处理。

---

# 47. 数据库

V1 使用 SQLite。**需开启 WAL 模式**（`PRAGMA journal_mode=WAL;`），并明确写入策略：FastAPI / CLI 走短事务、Worker 独占写入队列相关表，减少 `database is locked` 的概率（详见第 66 节技术栈补充说明）。

主要表：

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
reviews          【新增，见第 35 节】
api_keys         【新增，见第 52 节】
```

---

# 48. review_policies（策略表）【修订：nullable、唯一约束、下限标记】

字段：

```text
id
scope_type      -- global / platform / account / article / task
scope_id        -- 对应实体 id（global 可为 null）
review_mode     -- always / optional / never，非空
publish_mode    -- automatic / manual / scheduled / disabled，非空
is_floor        -- boolean，仅 platform / account 层可为 true，表示"不可被下游放松"
created_at
updated_at
```

约束：`(scope_type, scope_id)` 唯一——每个 scope 只能有一行有效配置，**没有行 = 未配置 = 继承上一级**（对应第 2.5 节）。`is_floor=true` 只允许在 `review_mode=always` 时设置，PolicyResolver 遇到 `is_floor=true` 的记录时按第 6 节规则处理为下限。

---

# 49. PublishTask（数据模型）【修订】

```text
id
article_id
article_version_id      -- 必填，用于幂等键与审核版本绑定
platform
account_id

review_policy            -- 快照值
publish_policy           -- 快照值
policy_floor_locked      -- boolean，标记本次策略是否被下限锁定（用于 Web 展示，见第 40 节）

status

attempt
max_attempts

remote_id
remote_url

error_code
error_message

started_at
finished_at
timeout_at               【新增，见第 21 节】

created_at
updated_at
```

任务创建时保存最终解析出的策略快照（`review_policy` / `publish_policy` / `policy_floor_locked`），避免后续配置改变影响正在执行的任务；`(article_version_id, platform, account_id)` 在非终态任务中唯一（第 30 节部分唯一索引）。

---

# 50. BrowserSession 与账号级并发锁【修订】

```text
id
account_id
platform

status
session_path

current_task_id     -- 【新增】当前占用该账号浏览器会话的 PublishTask id，为空表示空闲
locked_at           -- 【新增】加锁时间，用于配合第 21 节超时释放锁

started_at
stopped_at
last_error

created_at
updated_at
```

**并发规则（修订）**：任一时刻，同一 `account_id + platform` 组合的浏览器任务只能有一个在执行。Worker 在启动浏览器任务前必须先对该 BrowserSession 加锁（写入 `current_task_id`），任务结束（success/failed/cancelled/timeout）或超时（第 21 节）后释放锁。其它 PublishTask 若发现目标账号已被锁定，则保持在 `queued`，不得并发抢占同一个 `storage_state`，避免 cookie 冲突或触发平台风控。

---

# 51. PublishLog【修订：敏感信息脱敏】

```text
id
task_id
level
event
message
metadata      -- 写入前必须经过统一的脱敏中间件处理
created_at
```

记录事件：`task_created / task_started / browser_started / login_checked / page_opened / content_filled / image_uploaded / submit_clicked / publish_success / publish_failed / waiting_review / waiting_manual / waiting_auth / task_retry / task_completed`。

**脱敏要求**：所有写入 `metadata` 的内容必须先经过统一的日志脱敏函数，按字段名（`token / cookie / secret / password / storage_state` 等关键字）自动屏蔽，而不是仅依赖开发者自觉不打印——这一条对应第 53 节安全要求，V2.1 只提了原则没提机制，V2.2 明确要求有代码层面强制执行的脱敏中间件，而不是约定俗成。

---

# 52. 鉴权与访问控制【新增】

V2.1 全文没有提到任何身份鉴权机制，而系统涉及审核通过/拒绝、发布、账号管理等高风险操作，并且存储着 `access_token / cookie` 等敏感信息。即便定位是"个人使用"，只要 Web/API 监听在非 `127.0.0.1` 的地址上，缺少鉴权就是一个现实的安全漏洞。

V2.2 最低要求（V1 必须实现）：

- **Web**：基于用户名+密码或单一管理密码的登录态（Session Cookie 或 JWT 均可），未登录不能访问除登录页外的任何页面/接口。
- **CLI**：本机运行默认信任（等同于已登录管理员），远程连接 `publisher server` 时需要配置 API Key。
- **API**：所有 `/reviews`、`/publish`、`/tasks`、`/accounts` 等写操作接口，必须携带有效的 API Key（`Authorization: Bearer <key>`）。
- **API Key 权限位**：至少支持一个 `allow_override_review` 标记位，用于第 12 节"明确授权的自动化策略"——只有带此标记的 Key 才能在需要时突破 Account/Platform 层的 `always` 下限，且每次突破都必须记录审计日志（写入 `publish_logs`，`event=policy_override`）。
- 默认部署仅监听 `127.0.0.1`，如需暴露到局域网/公网，文档需在 README 中明确提示用户必须先配置鉴权。

`api_keys` 表：

```text
id
name
key_hash
allow_override_review   -- boolean
created_at
last_used_at
revoked_at
```

---

# 53. 安全（敏感信息）

敏感信息：`access_token / refresh_token / client_secret / cookie / storage_state`。

必须：加密存储 / 日志脱敏（见第 51 节）/ 限制文件权限 / 禁止日志输出 / 禁止 Git 提交。AI 不得直接获取这些信息。

---

# 54. 平台风控与频率限制【新增】

V2.1 完全没有提及自动化发布可能带来的平台合规/风控风险。用 Playwright 模拟人工操作在小红书、知乎等平台上自动发布，存在触发平台风控甚至封号的风险，尤其在 `review=never + publish=automatic` 全自动模式下无人工介入时风险更高。这属于用户需要自行承担的平台合规风险，但系统应尽量提供保护机制：

- 每个账号维护一个**最小发布间隔**（可配置，默认建议不低于平台常见风控阈值，例如同账号相邻两次发布间隔 ≥ 5 分钟），Worker 在调度浏览器任务时必须遵守。
- 短时间内同一账号连续失败（例如连续 3 次 `blocked` 或页面异常）时，自动将该账号标记为"高风险冷却"（暂停接受新任务一段时间），而不是无脑重试。
- 在 README / Web 设置页明确提示：浏览器自动化发布可能违反目标平台的服务条款，请用户自行评估风险，尤其是全自动模式。

---

# 55. 内容安全兜底检测【新增】

在 `review=never` 的全自动模式下，AI 生成内容会直接发布，没有任何人工把关。V2.2 建议增加一层**轻量兜底检测**（不等同于人工审核，也不作为强制项，但作为默认开启的安全网）：

- 发布前对内容做基础的违禁词/敏感词过滤（可配置词库），命中则自动转入 `waiting_manual` 而不是直接失败或强行发布；
- 该检测独立于 `review_policy`，即使 `review=never`，兜底检测依然生效，除非用户在 Settings 中显式关闭。

---

# 56. Docker

V1：

```text
publisher
├── FastAPI
├── Web
├── Worker
└── Playwright（含第 25 节人工接管的可视化方案）
```

Volume：`/data` `/uploads` `/logs`，例如 `/data/publisher.db` `/data/accounts` `/data/browser` `/data/logs`。

---

# 57. 浏览器 Docker 与人工接管的可视化方案【修订】

Playwright 使用容器内 Chromium，需要支持 `HEADLESS=true`。

**V2.2 修订**：人工接管所需的可视化能力（第 25 节方案 A：`Xvfb + noVNC`）不再是"后续扩展"，而是 **V1 必须交付**的一部分（至少提供一种可用的人工接管可视化路径），因为它直接对应验收标准里"支持人工接管"这一硬性要求。

```text
Chromium → Xvfb → noVNC → Web（V1 范围）
```

---

# 58. 项目目录

```text
publisher/
│
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── README.md
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
│       ├── auth/          【新增，见第 52 节】
│       └── config/
│
├── web/
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

# 59. 技术栈

## Backend

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy 2
Alembic
SQLite（WAL 模式）
httpx
Typer
Rich
Playwright
```

## Frontend

```text
Vue 3
TypeScript
Vite
Pinia
Vue Router
Naive UI
Axios
SSE
```

## Deployment

```text
Docker
Docker Compose
Chromium
Xvfb + noVNC（V1 必须，见第 57 节）
```

---

# 60. API

主要接口：

```text
/auth/login /auth/logout /auth/whoami        【新增】

/articles
/articles/{id}
/articles/{id}/versions

/ai/generate
/ai/revise

/reviews
/reviews/{id}/approve
/reviews/{id}/reject

/policies
/policies/resolve

/publish
/publish/{task_id}

/tasks
/tasks/{id}
/tasks/{id}/retry
/tasks/{id}/resume
/tasks/{id}/cancel

/accounts
/accounts/{id}

/platforms

/browser/sessions

/events
```

除 `/auth/login` 外，其余接口全部要求鉴权（第 52 节）。

---

# 61. 核心 Policy Resolver【修订】

系统必须有统一 PolicyResolver。

输入：`Global / Platform / Account / Article / Task`（每一项都可能是"未配置"，即 `review_policies` 表中不存在对应行）。

输出：`review_policy / publish_policy / is_floor_locked`。

解析算法（伪代码）：

```text
result = None
floor_locked = false

for scope in [Global, Platform, Account, Article, Task]:
    row = lookup(scope)
    if row is None:
        continue                      # 未配置，跳过
    if floor_locked and row.review_mode != 'always':
        continue                      # 已被下限锁定，忽略试图放松的配置
    result = row
    if scope in (Platform, Account) and row.is_floor and row.review_mode == 'always':
        floor_locked = true

return result, floor_locked
```

举例：

```text
Global    review = always
Platform: Juejin   review = never
Article   review = optional

最终：optional（无 floor 锁定）
```

```text
Global    review = always
Account: xhs_account_001  review = always, is_floor = true
Article   review = never   （试图放松）

最终：always，floor_locked = true（Article 的 never 被忽略）
```

---

# 62. Policy Resolver 不能被 Web/CLI 重复实现

必须：`Web / CLI / AI` 三个入口都调用 `Core.PolicyResolver`，不允许各自实现判断逻辑，否则不同入口可能出现"Web：需要审核 / CLI：不需要审核"这种不一致，造成安全漏洞。

---

# 63. 发布权限检查【修订：加入账号并发锁】

真正执行发布前再次检查：

```text
Article status（必须为 ready）
PublishTask status
Review status（若 review_policy=always，必须存在 approved 且 article_version_id 与 Task 一致，见第 35 节）
Publish policy
Account status
Platform capability
BrowserSession 是否已被其它 Task 占用（见第 50 节）
```

即使 Task 已经创建，也不能跳过最终检查。

---

# 64. 自动发布

`review=never + publish=automatic`：

```text
AI Generate → Article(ready) → PolicyResolver → Create PublishTask → Worker → Publish
```

整个过程无需打开 Web（但仍会经过第 55 节的内容安全兜底检测）。

---

# 65. 审核后自动发布【修订：版本一致性检查】

`review=always + publish=automatic`：

```text
AI Generate → waiting_review → Web/CLI Approve
  ↓（发布前二次校验 approved 记录的 article_version_id 与 Task 一致，见第 35 节）
queued → Worker → Publish
```

用户只需要审核一次，不需要再次点击"发布"；但如果审核通过后文章又被编辑产生新版本，系统会自动打回 `waiting_review` 而不是带着旧审核结果发布新内容。

---

# 66. 审核后手动发布

`review=always + publish=manual`：

```text
AI Generate → waiting_review → Approve → ready → 等待用户点击发布 → Publish
```

---

# 67. 完全自动模式

```yaml
review:
  mode: never
publish:
  mode: automatic
```

```text
AI → Generate → Adapt → 内容安全兜底检测（第 55 节）→ Publish
```

适合用户明确允许的自动化内容，但仍建议开启第 54 节的频率限制以降低封号风险。

---

# 68. 最终推荐默认配置

个人使用：

```yaml
review:
  mode: optional
publish:
  mode: manual
```

高度自动化：

```yaml
review:
  mode: never
publish:
  mode: automatic
```

正式内容：

```yaml
review:
  mode: always
publish:
  mode: automatic
```

---

# 69. V1 开发范围【修订】

第一阶段不建议同时实现所有平台。

先实现：`Core / Auth / Web / CLI / Skill / AI / Policy / Review / Task / Worker`

然后实现：`API Platform × 1`、`Browser Platform × 1`（含第 57 节人工接管可视化方案），用一个 API 平台验证 API Adapter，用一个浏览器平台验证 Playwright Adapter。

> 相比 V2.1，V1 范围新增 **Auth** 模块，且浏览器平台必须包含可用的人工接管可视化路径，不再推迟到后续扩展。

---

# 70. V1 验收标准【修订】

## 内容

- AI 可以生成文章 / 可以人工编辑 / 可以保存草稿 / 支持平台版本 / 支持审核策略

## 审核

必须支持 `always / optional / never`，并支持 `global / platform / account / article / task` 覆盖，且账号/平台层的 `always` 不可被文章层绕过（第 2.6、61 节）。

## 发布

必须支持：API 发布 / Browser 发布 / 多平台 / 多账号 / 独立任务 / 自动重试 / 人工接管（**含可视化操作路径，见第 57 节**）/ 登录失效 / 任务恢复 / 幂等（**含非终态去重，见第 30 节**）。

## 鉴权【新增】

Web 必须要求登录才能访问；写操作 API 必须校验 API Key；默认只监听本机地址。

## Web

可以看到：待审核 / 待发布 / 发布中 / 发布成功 / 发布失败 / 等待授权 / 等待人工 / 超时，并实时更新。

## CLI

AI 可以：创建文章 / 生成文章 / 修改文章 / 查询文章 / 查询策略 / 提交审核 / 创建发布任务 / 查询任务 / 重试任务 / 恢复任务。

---

# 71. 后续扩展

```text
Redis
PostgreSQL
多 Worker
Browser Pool
远程浏览器池
定时发布
内容日历
批量发布
账号轮换
Webhook
代理
```

> noVNC 已从"后续扩展"移入 V1 范围（第 57、69 节），此处不再重复列出。

---

# 72. 最终使用场景

## 场景一：普通自动文章

`review = never, publish = automatic`

```text
AI生成 → 自动适配 → 内容安全兜底检测 → 自动发布
```

用户不需要打开 Web。

## 场景二：重要文章

`review = always, publish = automatic`

```text
AI生成 → Web出现待审核 → 用户点击通过 → 校验版本一致 → 自动发布
```

## 场景三：同一篇文章不同平台不同规则

```text
掘金    review=never   publish=automatic  → 自动发布
CSDN    review=never   publish=automatic  → 自动发布
知乎    review=always  publish=automatic  → 等待审核 → 通过 → 自动发布
小红书  review=always  publish=manual     → 等待审核 → 通过 → 等待人工点击发布
```

---

# 73. 最终架构原则【修订：新增第 13-16 条】

1. 平台必须 Adapter 化，新增平台不能修改 Core。
2. 官方 API 优先，Browser Automation 只是补充。
3. Playwright 与业务层解耦，浏览器代码只能存在 Platform Adapter / Browser 层。
4. 支持人工接管，验证码、风控、登录异常不能简单视为失败。
5. 审核必须可配置，不能强制所有文章进入 Web 审核。
6. 审核策略必须支持多级覆盖：`Global / Platform / Account / Article / Task`。
7. 审核和发布必须是两个独立策略：`review_policy / publish_policy`。
8. 多平台任务独立，一个平台失败不能影响其他平台。
9. 所有长任务异步执行，由 Worker 负责。
10. 所有任务可恢复，不能因为进程重启导致状态丢失。
11. AI 默认不能自行修改强制审核策略，防止自动化绕过安全策略。
12. 所有入口共享 Core：`Web / CLI / Skill / API → Publisher Core`。
13. 【新增】策略字段必须支持"未配置 = 继承上级"语义，账号/平台层的 `always` 是不可被文章/任务层绕过的下限。
14. 【新增】审核记录必须绑定具体 `ArticleVersion`，内容变更后必须重新审核。
15. 【新增】同一账号的浏览器任务必须互斥执行，不允许并发操作同一 `storage_state`。
16. 【新增】所有对外暴露的入口（Web/API）必须要求身份鉴权，默认只监听本机地址。

---

# 74. 最终目标

最终用户可以直接对 AI 说：

```text
帮我写一篇关于 Docker 部署 FastAPI 的文章，
发布到掘金、小红书、知乎和 CSDN。
```

系统自动：

```text
AI → 生成文章 → 平台适配 → 内容安全兜底检测 → 读取发布策略
┌───────────────────────────────┐
│ 掘金       无需审核 → 自动发布 │
│ CSDN       无需审核 → 自动发布 │
│ 知乎       需要审核 → 等待审核 │
│ 小红书     需要审核 → 等待审核 │
└───────────────────────────────┘
```

用户只需要在需要审核的平台上处理审核，审核通过后系统会校验版本一致性再决定自动发布或等待人工点击。

整个系统最终实现：

> **AI 负责生产，Policy 决定流程，Worker 负责执行，Adapter 负责平台，Auth 负责准入，Web 负责管理，CLI/Skill 负责自动化入口。**

---

# 75. Codex 开发要求【修订：新增第 26-33 条】

Codex 实现时必须遵守：

1. 先实现数据库和 Core。
2. 再实现 PolicyResolver（含第 2.6 节下限规则）。
3. 再实现 Auth（鉴权，第 52 节）。
4. 再实现 Article / Version。
5. 再实现 Review（含第 35 节版本绑定）。
6. 再实现 PublishTask。
7. 再实现 Worker。
8. 再实现 PlatformAdapter。
9. 最后接入具体平台。
10. 不允许在 FastAPI Route 中直接执行 Playwright。
11. 不允许 Web 和 CLI 重复实现业务逻辑。
12. 不允许平台逻辑写死在 PublishService。
13. 不允许 AI 绕过 PolicyResolver。
14. 不允许 AI 把已被 Account/Platform 层显式设为 `always` 的策略调松为 `optional/never`（第 2.6、12 节）。
15. `waiting_review`、`waiting_auth`、`waiting_manual`、`blocked`、`timeout` 与 `failed` 必须严格区分。
16. 所有发布任务必须持久化。
17. 所有任务必须支持恢复。
18. 所有任务必须幂等（含非终态去重，第 30 节）。
19. 浏览器任务必须有超时；`waiting_auth/waiting_manual` 同样必须有超时并释放账号锁（第 21 节）。
20. 浏览器异常必须保存诊断信息。
21. 敏感账号信息不得进入日志，必须经过统一脱敏中间件（第 51 节），不能只靠开发者自觉。
22. 新增平台不得修改已有平台核心逻辑。
23. 所有核心模块必须提供测试。
24. PolicyResolver 必须有完整的优先级 + 下限规则测试（含"account 强制 always 时 article 无法调松"的用例）。
25. Web 必须能显示任务最终采用的审核/发布策略，以及是否被下限锁定（`policy_floor_locked`）。
26. Task 创建后必须保存当时解析出来的最终 Policy，避免后续配置变化影响正在执行的任务。
27. 【新增】Article 表不得保存 `review_policy/publish_policy` 字段，策略统一来自 `review_policies` 表。
28. 【新增】同一账号同一时刻只能有一个浏览器任务持有锁，Worker 调度前必须检查 `BrowserSession.current_task_id`。
29. 【新增】所有写操作 API 必须校验鉴权（Session 或 API Key），`/auth/login` 除外。
30. 【新增】Review 记录必须绑定 `article_version_id`；发布前必须重新校验版本一致性。
31. 【新增】PublishTask 的幂等唯一索引必须覆盖非终态（`WHERE status NOT IN (...)` 的部分唯一索引，或等价实现）。
32. 【新增】默认部署仅监听 `127.0.0.1`；暴露到公网前 README 必须提示用户配置鉴权。
33. 【新增】提供可配置的内容安全兜底检测（第 55 节）和账号发布频率限制（第 54 节），默认开启。

---

# 76. V2.2 核心变化总结（相对 V2.1）【新增】

本次修订针对 V2.1 中发现的以下问题逐一修复：

1. **数据模型冲突**：Article 表不再保存 `review_policy/publish_policy` 字段，统一由 `review_policies` 表管理（第 33、48 节）。
2. **覆盖语义不明确**：明确"未配置 = NULL = 继承上级"，避免默认值把多级覆盖机制架空（第 2.5、48、61 节）。
3. **优先级顺序的安全漏洞**：引入"下限（floor）"概念，账号/平台层显式设置的 `always` 不可被文章/任务层绕过（第 2.6、6、12、61 节）。
4. **Article 状态机与 Task 审核状态冲突**：拆分为 Article 内容状态（draft/ready/archived）与 Task/Review 审核状态两套体系，聚合状态改为只读计算视图（第 9、27 节）。
5. **rejected 之后流程缺失**：明确允许重新编辑生成新版本后再次送审（第 9.2 节）。
6. **审核与实际发布内容可能不一致**：新增 `reviews` 表并绑定 `article_version_id`，发布前二次校验版本一致性（第 35、65 节）。
7. **幂等只覆盖终态**：新增针对非终态任务的部分唯一索引（第 30 节）。
8. **同账号并发浏览器任务风险**：BrowserSession 新增并发锁字段，同账号同一时刻只允许一个浏览器任务（第 50 节）。
9. **鉴权完全缺失**：新增 Auth 模块、`api_keys` 表、Web 登录、API Key 校验（第 52 节）。
10. **平台风控/合规风险未提及**：新增发布频率限制与账号冷却机制（第 54 节）。
11. **全自动模式无安全网**：新增可配置的内容安全兜底检测（第 55 节）。
12. **SQLite 并发写入风险**：明确要求开启 WAL 模式（第 47、59 节）。
13. **等待类状态无超时**：新增 `timeout` 状态及超时释放锁机制（第 21 节）。
14. **V1 验收标准与人工接管方案矛盾**：把 noVNC 可视化方案从"后续扩展"移入 V1 必须交付范围（第 25、57、69、71 节）。
15. **日志脱敏无强制机制**：明确要求统一的脱敏中间件，而非仅作为原则性要求（第 51 节）。
16. **状态命名不一致**：统一说明 Article 层不再使用 `pending_review`，审核状态统一归属 Review/Task 层的 `waiting_review`/`pending`，减少概念混淆（第 9 节）。
