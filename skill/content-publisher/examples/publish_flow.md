# 发布流程示例

## 场景 A：API 平台（cnblogs）自动发布

```bash
# 1. 首次：添加带凭据的账号（令牌加密存储）
publisher account add cnblogs --key cnblogs_Gloria0816 --name Gloria0816 \
  --username Gloria0816 --token <MetaWeblog令牌>

# 2. 创建文章并置为 ready
publisher article create --title "Docker 部署 FastAPI 实战" --content "..."
publisher article update <id> --status ready

# 3. 发布（系统自动判断审核策略）
publisher publish 1 cnblogs
# task #1 platform=cnblogs review=never publish=automatic status=queued

# 4. 轮询状态
publisher task show 1
```

## 场景 B：浏览器平台（掘金）首次发布

```bash
# 1. 首次：打开浏览器登录（无账号时自动创建 <platform>_default）
publisher browser login juejin
# → 登录态已保存: data/browser/juejin/juejin_default.json

# 2. 创建文章 → ready → 发布
publisher article create --title "..." --content "..."
publisher article update <id> --status ready
publisher publish 2 juejin
# task #2 platform=juejin review=never publish=automatic status=queued

# 3. 轮询直到终态
publisher task show 2
# success + remote_url=https://juejin.cn/post/<id>
```

## 场景 C：多平台 + 需审核

```bash
publisher publish 3
# task #3 platform=juejin        review=never   publish=automatic status=queued
# task #4 platform=freebuf       review=always  publish=automatic status=waiting_review

# FreeBuf 为投稿制，需人工审核
publisher review list
publisher review approve <review_id>
#   publish=automatic → 任务自动转 queued 发布
#   publish=manual    → 任务转 pending，需 resume 放行
publisher task resume 4   # 仅 manual 策略需要
```

## 场景 C2：新增浏览器平台（CSDN / 百家号 / 企鹅号等）

新增平台与掘金同一套流程，仅 `browser login` 的平台名不同：

```bash
publisher browser login csdn          # 或 baijiahao / qiehao / 51cto /
                                      # segmentfault / freebuf / tencent_cloud
# → 登录态已保存: data/browser/csdn/csdn_default.json

publisher publish 5 csdn
# task #5 platform=csdn review=never publish=automatic status=queued
```

注意：

- FreeBuf 提交后由平台人工审核，任务 success 仅代表投稿成功；
- 企鹅号发布成功即分发腾讯系渠道（腾讯网/腾讯新闻等）；
- 新平台 selector 未经逐站实测，首次发布建议
  `publisher policy set article <id> --review always` 人工确认后再发；
  报 selector 失效错误时按 `references/platforms.md` 的指引修正脚本。

## 场景 D：异常处置

```bash
# 登录态失效 → waiting_auth
publisher browser login juejin     # 重新登录
publisher task resume 5

# 验证码/风控 → waiting_manual（浏览器持锁等待）
#   本机：浏览器窗口还在，人工完成验证
#   容器：noVNC :6080 接管
publisher task resume 5

# unconfirmed → blocked（可能已发布，禁止自动重试）
#   先到平台后台核实是否已发布；确认未发布才显式重试
publisher task retry 6

# 频率限制（300s 间隔）→ blocked，等待后重试即可
publisher task retry 6

# 卡死的等待任务 → 取消（会释放账号锁）
publisher task cancel 7
```

## 注意事项

- 文章必须 `ready` 才能发布：`publisher article update <id> --status ready`
- 浏览器平台必须先 `browser login`，否则任务直接 `waiting_auth`
- 同一账号发布间隔 300s，连续风控会进入冷却期
- `blocked` 与 `failed` 不同：blocked 可能已发布成功，盲目重试会重复发文

## 服务与人工审核

- 发布任务由 Worker 执行，需要 `publisher server` 在运行（默认 127.0.0.1:8000）。
  不确定时请求 `http://127.0.0.1:8000/auth/whoami`：返回 401 说明服务在运行
  （未带凭据属正常），连接失败则说明未启动。
- 需要人工审核时，可引导用户到 Web UI（开发环境 `http://localhost:5173`，
  内容审核页）处理，或直接用 `publisher review approve/reject` 代为操作。
