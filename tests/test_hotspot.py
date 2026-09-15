from __future__ import annotations

import logging

from publisher.ai import OllamaProvider
from publisher.pipeline import hotspot


class _FakeOllamaProvider(OllamaProvider):
    def __init__(self):
        super().__init__("http://192.168.3.119:11434", "qwen3.8:latest")
        self.responses = iter(
            [
                '[{"id": 1, "title": "热点" "summary": "缺少逗号"}]',
                '[{"id": 1, "title": "热点", "summary": "已修复", '
                '"conflict_point": "冲突", "relevance_angle": "关联"}]',
            ]
        )
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return next(self.responses)


async def test_hotspot_repair_stays_on_configured_ollama(monkeypatch, caplog):
    provider = _FakeOllamaProvider()
    monkeypatch.setattr(hotspot, "get_provider", lambda **_kwargs: provider)

    with caplog.at_level(logging.INFO):
        result = await hotspot.fetch_daily_hotspots(session=object())

    assert result[0]["summary"] == "已修复"
    assert len(provider.prompts) == 2
    assert "修复为合法 JSON 数组" in provider.prompts[1]
    assert "使用 Ollama（模型 qwen3.8:latest）生成最新热点" in caplog.text
    assert "ChatGPT" not in caplog.text
