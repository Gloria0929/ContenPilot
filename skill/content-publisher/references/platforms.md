# 平台差异参考

已注册平台（与 `platforms` 表同步，由 registry 初始化写入）：

| 平台 | 模式 | 内容形态 | 审核建议 | 账号添加方式 |
|---|---|---|---|---|
| 博客园 cnblogs | api | Markdown 技术博客 | optional | `account add cnblogs --key <key> --name <名> --username <用户名> --token <MetaWeblog令牌> [--blog-name <博客名>]` |
| 微信公众号 wechat_mp | api | 富文本图文（推入官方草稿箱） | optional | `account add wechat_mp --key wechat_default --credentials '{"appid":"...","secret":"...","author":"敖行客"}'` |
| 掘金 juejin | browser | Markdown 技术博客 | optional | `browser login juejin` |
| CSDN csdn | browser | Markdown 技术博客 | optional | `browser login csdn` |
| 知乎 zhihu | browser | 富文本专栏/文章 | optional | `browser login zhihu` |
| 今日头条 toutiao | browser | 资讯图文（头条号） | always | `browser login toutiao` |
| 思否 segmentfault | browser | Markdown 技术问答 | optional | `browser login segmentfault` |
| FreeBuf freebuf | browser | 网络安全文章（投稿制） | always | `browser login freebuf` |
| 百家号 baijiahao | browser | 资讯图文（富文本） | always | `browser login baijiahao` |
| 企鹅号 qiehao | browser | 资讯图文（富文本，分发腾讯系渠道） | always | `browser login qiehao` |
| 51CTO 51cto | browser | Markdown 技术博客 | optional | `browser login 51cto` |
| 腾讯云开发者社区 tencent_cloud | browser | 云技术文章 | optional | `browser login tencent_cloud` |

## api 模式（cnblogs / wechat_mp）

- **cnblogs**：凭据（username + token，另需 blog_name）加密存储，发布走 MetaWeblog API，无需浏览器。
- **wechat_mp**：凭据（appid + secret）加密存储，直调微信公众平台官方草稿箱 API `POST /cgi-bin/draft/add`。排版好的富文本 HTML 直接推入草稿箱，无需人工输入验证码，极为安全稳定。

## browser 模式（juejin / csdn / zhihu / toutiao / segmentfault / freebuf / baijiahao / qiehao / 51cto / tencent_cloud）

- 发布走 Playwright：加载 storage_state → 打开创作页 → 填内容 → 提交 → 成功确认。同账号任务互斥（一任务一浏览器 + 账号锁）。
- 登录态失效或缺失 → 任务 `waiting_auth`，重新 `browser login` 后 resume。
- Markdown 输入按平台编辑器自动适配：CodeMirror / textarea 平台（csdn、segmentfault、51cto、tencent_cloud 的 MD 模式）直接填 Markdown；富文本平台（zhihu、toutiao、baijiahao、qiehao）自动以富文本或纯文本插入。

### 知乎实测要点 (zhihu)
- 创作页路由：`https://zhuanlan.zhihu.com/write`
- 正文为 DraftJS 富文本编辑器，支持标题自动填充与确认发布弹窗；
- 发布成功跳转 `/p/<id>` 专栏详情页。

### 今日头条实测要点 (toutiao)
- 创作页路由：`https://mp.toutiao.com/profile_v4/graphic/publish`
- 正文为 ProseMirror 编辑器，发布后跳转文章管理页 `/graphic/manage`。

### CSDN 实测要点（2026-09 已实测发布成功，selector 见 `src/publisher/browser/scripts/csdn.py`）
- 创作页路由：`https://editor.csdn.net/md?not_checkout=1`
- 标题特殊交互：可见区是 `.article-bar__title-display`（显示【无标题】），点击后激活隐藏的 `input.article-bar__title`；受控组件，必须全选删除 + insert_text。
- 标签必填（红 *）：点「+ 添加文章标签」→ 搜索框输入关键词 → Enter 即可添加自定义标签。

### 掘金实测要点（2026-09，selector 见 `src/publisher/browser/scripts/juejin.py`）
- 创作页路由：`https://juejin.cn/editor/drafts/new?v=2`
- 发布面板必填项：分类（默认选「前端」）、标签（默认「前端」）、编辑摘要（≥50 字，脚本自动从正文补足）。
