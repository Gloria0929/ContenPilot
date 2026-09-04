# 平台差异参考

已注册平台（与 `platforms` 表同步，由 registry 初始化写入）：

| 平台 | 模式 | 内容形态 | 审核建议 | 账号添加方式 |
|---|---|---|---|---|
| 博客园 cnblogs | api | Markdown 技术博客 | optional | `account add cnblogs <key> --name <名> --username <用户名> --token <MetaWeblog令牌> [--blog-name <博客名>]` |
| 掘金 juejin | browser | Markdown 技术博客 | optional | `browser login juejin` |
| 小红书 xiaohongshu | browser | 短内容 + 图片 | always | `browser login xiaohongshu` |

## api 模式（cnblogs）

- 凭据（username + token，cnblogs 另有 blog_name）加密存储，发布走
  MetaWeblog API，无需浏览器。
- Web 页面添加的账号若无凭据，发布会失败——API 平台账号必须经 CLI
  `account add --token` 添加。

## browser 模式（juejin / xiaohongshu）

- 发布走 Playwright：加载 storage_state → 打开创作页 → 填内容 → 提交 →
  成功确认。同账号任务互斥（一任务一浏览器 + 账号锁）。
- 登录态失效或缺失 → 任务 `waiting_auth`，重新 `browser login` 后 resume。

### 掘金实测要点（2026-09，selector 见 `src/publisher/browser/scripts/juejin.py`）

- 创作页路由：`https://juejin.cn/editor/drafts/new?v=2`（老路由 `/editor` 已重定向首页）
- 发布面板必填项：分类（默认选「前端」）、标签（byte-select 下拉，默认「前端」）、
  **编辑摘要（≥50 字，脚本自动从正文补足）**
- 「确定并发布」按钮在草稿自动保存期间 disabled，脚本会等其可用再点击
- 发布成功后落地行为不稳定：可能跳「已发布」列表 `/published`，也可能停留编辑器；
  远程链接优先从 `/article/publish` API 响应的 `article_id` 抓取
- 文章发布后进入平台审核期，审核通过前未登录访问文章页会 404（正常现象）
