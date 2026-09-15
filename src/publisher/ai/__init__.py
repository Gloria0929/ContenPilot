"""AI Provider 抽象与实现（支持 ChatGPT / OpenAI / 本地与远程 Ollama / Anthropic）。

支持两种核心形态：
1. ChatGPT (OpenAI API)：通过 API Key 远程调用 gpt-4o / gpt-4o-mini 或兼容服务；
2. Ollama (本地或远程部署)：支持本地 http://localhost:11434 或局域网/远程 http://<IP>:11434，无需繁琐凭证，支持 qwen2.5 / llama3.1 / deepseek-r1 等开源模型。
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...

    @abstractmethod
    async def revise(self, content: str, instruction: str) -> str: ...

    @abstractmethod
    async def adapt(self, content: str, platform: str) -> str: ...


class OpenAICompatProvider(AIProvider):
    """OpenAI / ChatGPT 协议（覆盖 OpenAI 官方、OpenRouter、Azure 及兼容反代）。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    @staticmethod
    async def list_models(base_url: str, api_key: str = "") -> list[str]:
        """探测 OpenAI 兼容服务连通性（GET /models）。"""
        import httpx

        try:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return sorted(
                        str(m.get("id") or m.get("name") or "")
                        for m in data.get("data", data if isinstance(data, list) else [])
                    )
        except Exception:
            pass
        return []

    async def _chat(self, messages: list[dict]) -> str:
        import httpx

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
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
            "segmentfault": "技术问答社区风格，保留 Markdown，重点突出",
            "51cto": "技术博客，保留 Markdown，结构清晰",
            "tencent_cloud": "云技术社区风格，保留 Markdown，面向开发者",
            "freebuf": "网络安全社区风格，专业严谨，术语准确",
            "baijiahao": "自媒体资讯风格，段落简短，标题吸引人",
            "qiehao": "资讯平台风格，段落简短，适合移动端阅读",
            "zhihu": "知乎富文本，观点明确，可读性强",
            "wechat": "微信公众号 HTML，排版美观",
            "wechat_mp": "微信公众号 HTML，排版美观",
            "toutiao": "今日头条资讯风格，引人入胜",
        }
        style = style_map.get(platform, "通用")
        msgs = [
            {"role": "system", "content": f"你是内容适配专家，将内容适配为{style}风格。"},
            {"role": "user", "content": content},
        ]
        return await self._chat(msgs)


class OllamaProvider(AIProvider):
    """Ollama 本地或远程服务适配器。

    支持调用 http://localhost:11434 或 http://<远程IP>:11434。
    自动通过 /v1/chat/completions 标准协议交互。
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5"):
        clean_url = base_url.rstrip("/")
        if not clean_url.endswith("/v1"):
            clean_url = f"{clean_url}/v1"
        self.base_url = clean_url
        self.model = model

    @staticmethod
    async def list_models(base_url: str = "http://localhost:11434") -> list[str]:
        """查询 Ollama 实例当前已安装拉取的模型列表。"""
        import httpx

        root_url = base_url.rstrip("/").removesuffix("/v1")
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get(f"{root_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    async def _chat(self, messages: list[dict]) -> str:
        import httpx

        # Ollama 无需复杂 Bearer Token，传 dummy token 以免反代拦截
        headers = {"Authorization": "Bearer ollama", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={"model": self.model, "messages": messages},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate(self, prompt: str) -> str:
        return await self._chat([{"role": "user", "content": prompt}])

    async def revise(self, content: str, instruction: str) -> str:
        msgs = [
            {"role": "system", "content": "你是资深编辑，按指令修改下面的内容。"},
            {"role": "user", "content": f"指令：{instruction}\n\n内容：\n{content}"},
        ]
        return await self._chat(msgs)

    async def adapt(self, content: str, platform: str) -> str:
        msgs = [
            {"role": "system", "content": f"你是内容适配专家，将以下内容适配为适合 {platform} 平台的阅读风格。"},
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


def get_provider(
    name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    session=None,
) -> AIProvider:
    """实例化 AI Provider。

    支持数据库设置、显式参数传递与环境变量优先级智能解析。
    支持：
    - "openai" / "chatgpt": 官方或兼容的 ChatGPT API
    - "ollama": 本地（http://localhost:11434）或远程（http://IP:11434）Ollama
    - "anthropic": Claude API
    """
    db_provider = ""
    db_openai_key = ""
    db_openai_base = ""
    db_openai_model = ""
    db_ollama_base = ""
    db_ollama_model = ""

    if session:
        from ..services.setting_service import get_setting
        db_provider = get_setting(session, "ai_provider")
        db_openai_key = get_setting(session, "openai_api_key")
        db_openai_base = get_setting(session, "openai_base_url")
        db_openai_model = get_setting(session, "openai_model")
        db_ollama_base = get_setting(session, "ollama_base_url")
        db_ollama_model = get_setting(session, "ollama_model")

    # 确定 Provider 类型
    if name:
        provider_name = name.lower()
    elif db_provider:
        provider_name = db_provider.lower()
    elif os.environ.get("PUBLISHER_AI_PROVIDER"):
        provider_name = os.environ["PUBLISHER_AI_PROVIDER"].lower()
    elif os.environ.get("OPENAI_API_KEY") or db_openai_key:
        provider_name = "openai"
    elif os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or db_ollama_base:
        provider_name = "ollama"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        provider_name = "anthropic"
    else:
        provider_name = "openai"

    # 1. Ollama 分支（支持本地或远程）
    if provider_name in ("ollama", "local_ollama", "remote_ollama"):
        final_base = (
            base_url
            or db_ollama_base
            or os.environ.get("OLLAMA_BASE_URL")
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434"
        )
        final_model = (
            model
            or db_ollama_model
            or os.environ.get("OLLAMA_MODEL")
            or os.environ.get("OLLAMA_MODEL_NAME")
            or os.environ.get("PUBLISHER_AI_MODEL")
            or "qwen2.5"
        )
        return OllamaProvider(base_url=final_base, model=final_model)

    # 2. ChatGPT / OpenAI 分支
    if provider_name in ("openai", "chatgpt", "openai_compat", "openrouter"):
        final_base = (
            base_url
            or db_openai_base
            or os.environ.get("PUBLISHER_AI_BASE_URL")
            or "https://api.openai.com/v1"
        )
        final_key = (
            api_key
            or db_openai_key
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )
        final_model = (
            model
            or db_openai_model
            or os.environ.get("PUBLISHER_AI_MODEL")
            or "gpt-4o-mini"
        )
        return OpenAICompatProvider(final_base, final_key, final_model)

    # 3. Anthropic 分支
    if provider_name == "anthropic":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        m = model or os.environ.get("PUBLISHER_AI_MODEL", "claude-sonnet-5")
        return AnthropicProvider(key, m)

    # 兜底作为 OpenAI 兼容
    return OpenAICompatProvider(
        base_url or "https://api.openai.com/v1",
        api_key or os.environ.get("OPENAI_API_KEY", ""),
        model or "gpt-4o-mini",
    )


async def ai_generate(
    prompt: str,
    provider: AIProvider | None = None,
    provider_name: str | None = None,
    session=None,
) -> str:
    p = provider or get_provider(name=provider_name, session=session)
    return await p.generate(prompt)


async def ai_revise(
    content: str,
    instruction: str,
    provider: AIProvider | None = None,
    provider_name: str | None = None,
    session=None,
) -> str:
    p = provider or get_provider(name=provider_name, session=session)
    return await p.revise(content, instruction)


async def ai_adapt(
    content: str,
    platform: str,
    provider: AIProvider | None = None,
    provider_name: str | None = None,
    session=None,
) -> str:
    p = provider or get_provider(name=provider_name, session=session)
    return await p.adapt(content, platform)
