"""短视频内容生产与剪辑流水线。

涵盖：
1. 2 分钟、600 字以内、强冲突、带钩子的短视频口播文案生成
2. 短视频标题与前 3 秒黄金钩子
3. 封面图提示词与素材清单提取
4. 对接开源剪辑工具 MoneyPrinterTurbo 的 API，自动合成 mp4 视频
5. 支持分发到 抖音 (douyin) 与 微信视频号 (channels)
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..ai import get_provider
from ..knowledge.prompts import (
    build_short_video_script_prompt,
    build_video_cover_and_assets_prompt,
)

logger = logging.getLogger(__name__)


async def generate_short_video_script(
    hotspot_summary: str,
    angle: str = "",
    provider_name: str | None = None,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
    session=None,
) -> dict[str, Any]:
    """生成短视频口播脚本、标题、钩子及剪辑素材清单。"""
    provider = get_provider(
        name=provider_name,
        base_url=ollama_url if provider_name == "ollama" else None,
        model=ollama_model if provider_name == "ollama" else None,
        session=session,
    )

    # 1. 口播脚本
    script_prompt = build_short_video_script_prompt(hotspot_summary, angle=angle)
    script_content = await provider.generate(script_prompt)

    # 2. 视频标题与钩子提炼
    hook_prompt = f"""根据以下短视频口播文案，生成 3 个极具吸引力的短视频大标题和视频前3秒的口播爆点金句：
输出格式要求为 JSON 格式：
{{
  "titles": ["大标题1", "大标题2", "大标题3"],
  "opening_hooks": ["前3秒黄金钩子1", "前3秒黄金钩子2"]
}}

文案：
{script_content}
"""
    hook_raw = await provider.generate(hook_prompt)
    titles = ["AI Agent 正在替程序员上班：研发范式的大地震"]
    hooks = []
    try:
        clean = hook_raw.strip()
        if "```json" in clean:
            clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean:
            clean = clean.split("```", 1)[1].split("```", 1)[0].strip()
        parsed = json.loads(clean)
        titles = parsed.get("titles", titles)
        hooks = parsed.get("opening_hooks", [])
    except Exception:
        pass

    chosen_title = titles[0] if titles else "AI重构研发"

    # 3. 封面图提示词与素材清单
    cover_and_assets = build_video_cover_and_assets_prompt(script_content, chosen_title)
    cover_prompt = cover_and_assets["cover_prompt"]
    assets_manifest = await provider.generate(cover_and_assets["assets_prompt"])

    return {
        "title": chosen_title,
        "title_candidates": titles,
        "opening_hooks": hooks,
        "script": script_content,
        "word_count": len(script_content),
        "cover_prompt": cover_prompt,
        "assets_manifest": assets_manifest,
    }


class MoneyPrinterTurboClient:
    """对接开源剪辑工具 MoneyPrinterTurbo 的 API。

    支持将口播文本直接发送至本地或容器内的 MoneyPrinterTurbo 服务，自动化合成短视频。
    """

    def __init__(self, base_url: str = "http://localhost:8081"):
        self.base_url = base_url.rstrip("/")

    async def check_health(self) -> bool:
        """检测 MoneyPrinterTurbo 服务是否就绪。"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/ping")
                return resp.status_code == 200
        except Exception:
            return False

    async def create_video_task(
        self,
        video_script: str,
        video_subject: str,
        voice_name: str = "zh-CN-YunxiNeural",
        video_aspect_ratio: str = "9:16",
    ) -> dict[str, Any]:
        """提交视频合成任务至 MoneyPrinterTurbo。"""
        payload = {
            "video_subject": video_subject,
            "video_script": video_script,
            "voice_name": voice_name,
            "video_aspect": video_aspect_ratio,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{self.base_url}/api/v1/videos", json=payload)
                if resp.status_code in (200, 201):
                    return resp.json()
                return {"error": f"API returned {resp.status_code}", "detail": resp.text}
        except Exception as e:
            return {
                "error": "MoneyPrinterTurbo service unreachable",
                "message": f"请确保 MoneyPrinterTurbo API 已启动（默认端口 8081），错误详情：{str(e)}",
            }
