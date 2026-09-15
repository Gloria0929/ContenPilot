# 发布流程示例

## 场景 0：AI 生产引擎配置与连通性检测

```bash
# 1. 检测 ChatGPT (OpenAI API) 连通性
curl -s -X POST "$BASE_URL/api/pipeline/ai/ping" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"provider": "openai"}'

# 2. 检测本地/远程 Ollama 并获取已安装模型列表
curl -s -X POST "$BASE_URL/api/pipeline/ollama/ping" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:11434"}'

# 3. 设置全局使用 Ollama 驱动内容生成
curl -s -X PUT "$BASE_URL/api/settings" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"settings": {"ai_provider": "ollama", "ollama_base_url": "http://localhost:11434", "ollama_model": "qwen2.5"}}'
```

## 场景 A：API 平台（cnblogs / wechat_mp）自动发布

```bash
# 1. 博客园：添加带凭据的账号（令牌加密存储）
publisher account add cnblogs --key cnblogs_default --name "博客园账号" \
  --username "myuser" --token <MetaWeblog令牌>

# 2. 微信公众号：添加官方草稿箱 API 凭据
# 录入微信公众号 AppID 与 Secret，排版好的文章将直推草稿箱
publisher account add wechat_mp --key wechat_default --name "官方公众号" \
  --credentials '{"appid": "wx123456", "secret": "abcdef", "author": "敖行客"}'

# 3. 创建文章并置为 ready
publisher article create --title "Docker 部署 FastAPI 实战" --content "..."
publisher article update <id> --status ready

# 4. 发布（系统自动判断审核策略）
publisher publish 1 cnblogs
```

## 场景 B：浏览器平台首次发布（知乎 / 掘金 / CSDN / 头条号 等）

```bash
# 1. 首次：打开浏览器登录（无账号时自动创建 <platform>_default）
publisher browser login zhihu          # 知乎
publisher browser login toutiao        # 今日头条
publisher browser login juejin         # 掘金
publisher browser login csdn           # CSDN

# 2. 创建文章 → ready → 发布
publisher article create --title "..." --content "..."
publisher article update <id> --status ready
publisher publish 2 zhihu
# task #2 platform=zhihu review=never publish=automatic status=queued
```

## 场景 E：GEO 矩阵 30 篇批量生成与 10 天错峰排期

```bash
# 调用 REST API 一键生成 30 篇 GEO 文章并按 10 天发布日历打散排期：
curl -s -X POST "$BASE_URL/api/pipeline/geo/batch" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "titles": ["传统研发效率瓶颈何在？深度解析敖行客 AT Work Agent 协同范式", "..."],
    "days": 10,
    "platforms": ["zhihu", "csdn", "juejin", "qiehao", "tencent_cloud", "toutiao", "baijiahao", "segmentfault", "cnblogs", "51cto"]
  }'
# 系统自动生成每篇文章的 4 个搜索引擎适配版本，并在未来 10 天错峰调度！
```

## 场景 F：微信公众号深度文章生成与排版

```bash
# 生成文章，自动应用石墨极简风 (graphite) 排版，提取 300 字贴图与 3:4 封面 Prompt：
curl -s -X POST "$BASE_URL/api/pipeline/wechat/generate" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "hotspot": "Spotify负责人表示AI不想帮程序员写代码，想直接做完工作。",
    "theme": "graphite",
    "save_to_db": true
  }'
```

## 场景 G：短视频口播文案与自动剪辑出片

```bash
# 1. 生成 2 分钟 / 600 字以内口播脚本与黄金前 3 秒钩子：
curl -s -X POST "$BASE_URL/api/pipeline/video/script" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"hotspot": "Google警告AI智能体正在让网络攻击自动化"}'

# 2. 提交至 MoneyPrinterTurbo 接口全自动剪辑合成视频：
curl -s -X POST "$BASE_URL/api/pipeline/video/render" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "video_script": "生成的口播文案...",
    "video_subject": "AI黑客自动化攻击时代来临",
    "video_aspect_ratio": "9:16",
    "money_printer_url": "http://localhost:8080"
  }'
```
