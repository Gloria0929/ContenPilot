"""AI Provider 抽象与实现（文档第 36 节）。

支持 OpenAI / Anthropic / Google / OpenRouter / Ollama / OpenAI Compatible。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...

    @abstractmethod
    async def revise(self, content: str, instruction: str) -> str: ...

    @abstractmethod
    async def adapt(self, content: str, platform: str) -> str: ...


class OpenAICompatProvider(AIProvider):
    """OpenAI 兼容协议（覆盖 OpenAI / OpenRouter / Ollama / 大多数兼容服务）。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    async def _chat(self, messages: list[dict]) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": messages},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate(self, prompt: str) -> str:
        return await self._chat([{"role": "user", "content": prompt}])

    async def revise(self, content: str, instruction: str) -> str:
        msgs = [
            {"role": "system", "content": "你是内容编辑，按指令修改下面的内容。"},
            {"role": "user", "content": f"指令：{instruction}\n\n内容：\n{content}"},
        ]
        return await self._chat(msgs)

    async def adapt(self, content: str, platform: str) -> str:
        style_map = {
            "juejin": "技术博客，保留 Markdown，结构清晰",
            "csdn": "技术博客，保留 Markdown，结构清晰",
            "zhihu": "知乎富文本，观点明确，可读性强",
            "xiaohongshu": "小红书短内容，口语化，带 emoji 和标签",
            "wechat": "微信公众号 HTML，排版美观",
        }
        style = style_map.get(platform, "通用")
        msgs = [
            {"role": "system", "content": f"你是内容适配专家，将内容适配为{style}风格。"},
            {"role": "user", "content": content},
        ]
        return await self._chat(msgs)


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-5"):
        self.api_key = api_key
        self.model = model

    async def _chat(self, messages: list[dict]) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return "".join(b.get("text", "") for b in data.get("content", []))

    async def generate(self, prompt: str) -> str:
        return await self._chat([{"role": "user", "content": prompt}])

    async def revise(self, content: str, instruction: str) -> str:
        return await self._chat(
            [{"role": "user", "content": f"指令：{instruction}\n\n内容：\n{content}"}]
        )

    async def adapt(self, content: str, platform: str) -> str:
        return await self._chat(
            [{"role": "user", "content": f"将以下内容适配到 {platform} 平台：\n{content}"}]
        )


def get_provider(name: str | None = None) -> AIProvider:
    """根据配置/环境变量实例化 Provider。"""
    import os

    name = name or os.environ.get("PUBLISHER_AI_PROVIDER", "anthropic")
    if name == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        model = os.environ.get("PUBLISHER_AI_MODEL", "claude-sonnet-5")
        return AnthropicProvider(key, model)
    if name in ("openai", "openai_compat", "ollama", "openrouter"):
        base = os.environ.get(
            "PUBLISHER_AI_BASE_URL", "https://api.openai.com/v1"
        )
        key = os.environ.get("OPENAI_API_KEY", "")
        model = os.environ.get("PUBLISHER_AI_MODEL", "gpt-4o-mini")
        return OpenAICompatProvider(base, key, model)
    raise ValueError(f"unknown ai provider: {name}")


async def ai_generate(prompt: str, provider: AIProvider | None = None) -> str:
    p = provider or get_provider()
    return await p.generate(prompt)


async def ai_revise(
    content: str, instruction: str, provider: AIProvider | None = None
) -> str:
    p = provider or get_provider()
    return await p.revise(content, instruction)


async def ai_adapt(
    content: str, platform: str, provider: AIProvider | None = None
) -> str:
    p = provider or get_provider()
    return await p.adapt(content, platform)