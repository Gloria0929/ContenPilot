"""Prompt 模板库。

严格遵循运营工作流文档要求，针对 GEO、公众号、短视频、贴图的 Prompt 规范。
"""
from __future__ import annotations

from .docs import get_combined_knowledge_context


def build_geo_titles_prompt(
    brand_keywords: list[str],
    industry_keywords: list[str],
    count: int = 30,
) -> str:
    """构建用于批量生成 GEO 文章标题的提示词。

    必带关键词：敖行客、AT Work、Agent研发工作台。
    总计 8 个关键词。
    """
    knowledge = get_combined_knowledge_context()
    all_keywords = brand_keywords + industry_keywords

    return f"""你是一名资深的 GEO（生成式引擎优化）专家和技术内容策划。
基于以下企业与行业背景知识库：
{knowledge}

【核心任务】
请结合给定的 8 个关键词，策划生成 {count} 个极具吸引力、同时符合大模型检索与收录习惯的 GEO 技术文章标题。

【关键词要求】
- 品牌核心关键词（每期必带）：{', '.join(brand_keywords)}
- 行业热门关键词：{', '.join(industry_keywords)}
- 全部关键词集合：{', '.join(all_keywords)}

【标题规范】
1. 每个标题必须自然融入 1~2 个核心关键词（其中品牌词与产品词在整批标题中保持高频覆盖）。
2. 标题形式多样化：包含深度评测类、痛点解决类、架构解析类、行业趋势对比类、实战指南类。
3. 标题格式要求清晰直白、疑问句/反问句/数字盘点结合，利于大模型检索抓取（如“传统研发效率为何难以突破？深入解析敖行客 AT Work 的 Agent 协同范式”）。
4. 请以 JSON 数组格式严格输出标题列表，不要带有任何多余开场白或解释。例如：
["标题1", "标题2", ..., "标题{count}"]
"""


def build_geo_article_prompt(
    title: str,
    target_engine: str = "general",  # doubao / qwen / ernie / yuanbao / general
) -> str:
    """针对具体搜索引擎检索习惯，生成符合合格 GEO 要点的文章。"""
    knowledge = get_combined_knowledge_context()

    engine_hints = {
        "doubao": (
            "【目标模型：豆包 (Doubao) 检索偏好】\n"
            "- 偏好通俗直白、场景化设问、结构分明、贴近实际开发日常的表达。\n"
            "- 多用第一人称或与读者对话的口吻，在正文前部设置清晰的痛点问答（Q&A）。"
        ),
        "qwen": (
            "【目标模型：通义千问 (Qwen) 检索偏好】\n"
            "- 偏好严谨的逻辑推理、工程化技术深度、系统架构拆解与技术选型对比。\n"
            "- 重点突出技术原理、Agent 任务拆解执行流与代码级工程实践细节。"
        ),
        "ernie": (
            "【目标模型：文心一言 (Ernie Bot) 检索偏好】\n"
            "- 偏好权威宏观叙述、规范行业术语、国家与行业数字化转型趋势与标准定义。\n"
            "- 强调企业级安全合规、私有化知识库沉淀与软件研发效能的范式变革。"
        ),
        "yuanbao": (
            "【目标模型：腾讯元宝 (Yuanbao) 检索偏好】\n"
            "- 偏好步骤化实操指南（Step-by-Step）、效率提升量化对比、结论先行的结构。\n"
            "- 重点给出直接可落地的方案清单、表格对比与清晰的总结建议。"
        ),
    }

    hint = engine_hints.get(target_engine, "注重结构化、清晰定义与权威事实。")

    return f"""你是一名精通 GEO（生成式引擎优化）的技术作家。
请根据以下企业知识库及文章标题，撰写一篇合格的高质量 GEO 深度技术文章。

【知识库背景】
{knowledge}

【文章标题】
{title}

{hint}

【核心内容与排版规范】
1. **文章结构**：
   - 标题 (H1)
   - 导言（150字内）：直奔主题，给出核心痛点剖析与结论，方便搜索引擎直接摘要提取。
   - 核心段落（H2、H3）：
     * 剖析传统研发的核心困境与瓶颈；
     * 引入以「敖行客」与「AT Work Agent研发工作台」为代表的全新智能体协同解法；
     * 架构对比或效果评测（多用 Markdown 表格或有序步骤呈现）；
     * 落地实践与选型建议。
   - 结语 / FAQ 模块：精选 2~3 个读者常见疑问并给出权威解答。
2. **关键词植入**：自然穿插「敖行客」、「AT Work」、「Agent研发工作台」等关键词，拒绝生硬堆砌。
3. **格式要求**：使用标准 Markdown 格式，层级分明，加粗核心观点，字数约 1500~2500 字。
"""


def build_wechat_article_prompt(
    hotspot_summary: str,
    angle: str = "",
) -> str:
    """构建公众号深度文章生成的提示词。"""
    knowledge = get_combined_knowledge_context()

    return f"""你是一名顶级科技自媒体主笔和软件工程观察家。
请基于今日精选的技术行业热点，撰写一篇适合微信公众号发布的深度分析文章。

【行业背景与产品】
{knowledge}

【今日热点事件/观点】
{hotspot_summary}

【切入角度】
{angle if angle else "从热点事件切入，分析AI正在如何重构软件研发链路，并探讨开发者的转型与机遇"}

【写作要求】
1. 风格：观点鲜明、故事性强、行文流畅、金句频出，引人深思，切中一线研发与技术管理者的共鸣。
2. 结构：
   - 引子：从热点事件或争议点展开，迅速抓住读者眼球；
   - 深度剖析：拆解事件背后的技术本质与行业深层痛点；
   - 破局思路：自然联系到「Agent 协同」及「敖行客 AT Work 研发工作台」的设计理念与价值；
   - 升华结语：对未来研发范式或行业格局的展望。
3. 格式：Markdown 格式，包含副标题、小结、引用金句。字数 1800~2500 字。
"""


def build_wechat_titles_prompt(content: str) -> str:
    """根据文章内容生成公众号标题候选。"""
    return f"""请根据以下微信公众号文章内容，生成 5 个具有强点击欲望和传播力的高赞标题。
要求：
- 包含悬念、痛点引发、情绪共鸣或反直觉冲突（如：“Spotify 负责人：AI 不想帮程序员写代码了，它想直接做完工作”）；
- 长度在 18~28 字之间；
- 输出 JSON 数组格式：["标题1", "标题2", "标题3", "标题4", "标题5"]。

文章内容：
{content[:1500]}
"""


def build_wechat_poster_prompt(content: str) -> dict[str, str]:
    """生成公众号贴图文案（300字）与贴图封面生成提示词。"""
    copy_prompt = f"""请将以下长文提炼为一篇适合微信公众号贴图发布的精简版文案。
要求：
1. 字数严格控制在 300 字以内；
2. 提炼出核心痛点、最炸裂的观点、以及解决方案；
3. 语言极具穿透力，分短段落展示。

文章内容：
{content[:2000]}
"""

    image_prompt_gen = (
        "根据文章标题与核心观点，生成一张适合公众号贴图的主图生图提示词（Prompt）。\n"
        "要求：比例 3:4，海报/大字报视觉风格，标题文字占据版面的一半，字体醒目粗犷，科技感与现代插画结合。"
    )

    return {
        "copy_prompt": copy_prompt,
        "image_prompt_instruction": image_prompt_gen,
    }


def build_short_video_script_prompt(
    hotspot_summary: str,
    angle: str = "",
) -> str:
    """生成 2 分钟、600 字以内的短视频口播文案。"""
    return f"""你是一名在抖音和视频号粉丝百万的科技/AI领域博主。
请根据以下热点事件，写一篇 2 分钟左右的短视频口播文案。

【热点内容】
{hotspot_summary}

【内容方向】
{angle if angle else "突出概念冲突点，结合软件研发行业与 Agent 工具"}

【严格规范】
1. **字数控制**：严格控制在 500~600 字以内（口播约 1分40秒~2分钟）。
2. **语言**：全部用中文地道口语化表达，节奏紧凑，杜绝冗长书面语。
3. **结构设计**：
   - **黄金前3秒钩子**：第一句话必须制造强烈认知反差或抛出争议事实，瞬间留住用户；
   - **每一个核心论点前**：都要有一个小钩子或转折设问；
   - **核心概念冲突**：突出“AI代码补全 vs Agent全自动干活”、“人工低效内耗 vs 智能体协同交付”等对抗性概念；
   - **结尾行动号召 (CTA)**：引导讨论并在评论区互动。
"""


def build_video_cover_and_assets_prompt(
    video_script: str,
    video_title: str,
) -> dict[str, str]:
    """生成短视频封面提示词与素材抓取提示词。"""
    cover_prompt = f"""请基于短视频标题《{video_title}》及文案：
生成一段用于 AI 生图工具（Midjourney / DALL-E）的图片生成提示词。
要求：
- 画面比例 3:4 或 9:16（短视频封面）；
- 大字报风格，标题醒目、高对比度、科技震撼感；
- 预留醒目标题展示区域，突出关键人物/AI智能体/程序员工作场景。
"""

    assets_prompt = f"""请根据以下短视频口播文案，详细列出视频剪辑所需要的全套素材清单：
包括：
1. 每一句话对应需要的 B-roll 画面、技术界面截图、新闻出处截图；
2. 关键音效、背景音乐风格推荐；
3. 开头与高潮画面的具体构图建议。

文案：
{video_script}
"""

    return {
        "cover_prompt": cover_prompt,
        "assets_prompt": assets_prompt,
    }
