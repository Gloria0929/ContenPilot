# 平台差异参考

已注册平台（与 `platforms` 表同步，由 registry 初始化写入）：

| 平台 | 模式 | 内容形态 | 审核建议 | 账号添加方式 |
|---|---|---|---|---|
| 博客园 cnblogs | api | Markdown 技术博客 | optional | `account add cnblogs --key <key> --name <名> --username <用户名> --token <MetaWeblog令牌> [--blog-name <博客名>]` |
| 掘金 juejin | browser | Markdown 技术博客 | optional | `browser login juejin` |
| 小红书 xiaohongshu | browser | 短内容 + 图片 | always | `browser login xiaohongshu` |
| CSDN csdn | browser | Markdown 技术博客 | optional | `browser login csdn` |
| 思否 segmentfault | browser | Markdown 技术问答 | optional | `browser login segmentfault` |
| FreeBuf freebuf | browser | 网络安全文章（投稿制） | always | `browser login freebuf` |
| 百家号 baijiahao | browser | 资讯图文（富文本） | always | `browser login baijiahao` |
| 企鹅号 qiehao | browser | 资讯图文（富文本，分发腾讯系渠道） | always | `browser login qiehao` |
| 51CTO 51cto | browser | Markdown 技术博客 | optional | `browser login 51cto` |
| 腾讯云开发者社区 tencent_cloud | browser | 云技术文章 | optional | `browser login tencent_cloud` |

## api 模式（cnblogs）

- 凭据（username + token，cnblogs 另有 blog_name）加密存储，发布走
  MetaWeblog API，无需浏览器。
- Web 页面添加的账号若无凭据，发布会失败——API 平台账号必须经 CLI
  `account add --token` 添加。

## browser 模式（juejin / csdn / segmentfault / freebuf / baijiahao / qiehao / 51cto / tencent_cloud）

- 发布走 Playwright：加载 storage_state → 打开创作页 → 填内容 → 提交 →
  成功确认。同账号任务互斥（一任务一浏览器 + 账号锁）。
- 登录态失效或缺失 → 任务 `waiting_auth`，重新 `browser login` 后 resume。
- Markdown 输入按平台编辑器自动适配：CodeMirror / textarea 平台
  （csdn、segmentfault、51cto、tencent_cloud 的 MD 模式）直接填 Markdown；
  富文本平台（baijiahao、qiehao）以纯文本插入，换行由平台自动转换。

### CSDN 实测要点（2026-09 已实测发布成功，selector 见 `src/publisher/browser/scripts/csdn.py`）

- 创作页路由：`https://editor.csdn.net/md?not_checkout=1`
- **标题特殊交互**：可见区是 `.article-bar__title-display`（显示【无标题】），
  点击后激活隐藏的 `input.article-bar__title`（aria-hidden + display:none）；
  受控组件，`fill` 会被失焦清空，必须 **全选删除 + insert_text**
- 正文编辑器是 `pre.editor__inner`（自定义 MD 编辑器，非 CodeMirror），
  点击聚焦 + 全选删除模板 + insert_text
- 发布流程：底部 `button.btn-publish`「发布文章」→ 面板（.modal__publish-article）
  → **标签必填（红 \*）**：点「+ 添加文章标签」→ 搜索框输入关键词 →
  Enter 即可添加自定义标签（无需从候选列表选）→ 面板底部
  `button.btn-b-red`「发布文章」确认
- 发布成功跳转 `/article/details/<id>`；摘要非必填（默认取正文前 256 字）
- CSDN 登录风控较严：容器 Xvfb 环境滑块易验证失败，反检测
  （AutomationControlled 禁用 + webdriver 隐藏）已内置；如仍失败，
  建议本机跑 `publisher browser login csdn`（登录态与容器共享 data 目录）

### 新平台脚本说明（2026-09 新增）

- CSDN / 思否 / 51CTO 发布面板**标签必填**：脚本自动用标题关键词搜索
  并选第一个候选；分类未选时选第一项。
- 腾讯云开发者社区为**两步确认**：「发布」→ 属性面板（专栏必选）→
  「确认发布」→ 封面弹窗 →「确认并发布」，脚本链式处理。
- FreeBuf 为投稿制：任务成功 = 提交成功，最终是否刊出由平台人工审核决定。
- 企鹅号发布成功后自动分发腾讯网 / 腾讯新闻 / QQ浏览器等腾讯系渠道。
- 各平台 selector 未经逐站实测，首次发布建议 `--review always` 人工确认；
  报 `publish_button_not_found` / `confirm_button_not_found` 等 selector
  失效错误时，查看 `logs/diagnostics/` 截图修正
  `src/publisher/browser/scripts/<platform>.py` 中的常量。

### 掘金实测要点（2026-09，selector 见 `src/publisher/browser/scripts/juejin.py`）

- 创作页路由：`https://juejin.cn/editor/drafts/new?v=2`（老路由 `/editor` 已重定向首页）
- 发布面板必填项：分类（默认选「前端」）、标签（byte-select 下拉，默认「前端」）、
  **编辑摘要（≥50 字，脚本自动从正文补足）**
- 「确定并发布」按钮在草稿自动保存期间 disabled，脚本会等其可用再点击
- 发布成功后落地行为不稳定：可能跳「已发布」列表 `/published`，也可能停留编辑器；
  远程链接优先从 `/article/publish` API 响应的 `article_id` 抓取
- 文章发布后进入平台审核期，审核通过前未登录访问文章页会 404（正常现象）
