from __future__ import annotations

import tomllib
from pathlib import Path

from publisher.ai import OllamaProvider, get_provider


def test_ollama_environment_selects_ollama_without_api_key(monkeypatch):
    monkeypatch.setenv("PUBLISHER_AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://192.168.3.119:11434")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL_NAME", "qwen3.8:latest")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = get_provider()

    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://192.168.3.119:11434/v1"
    assert provider.model == "qwen3.8:latest"


def test_moneyprinterturbo_uses_configured_ollama():
    config_path = (
        Path(__file__).resolve().parents[1]
        / "docker"
        / "moneyprinterturbo.config.toml"
    )
    with config_path.open("rb") as config_file:
        config = tomllib.load(config_file)

    assert config["app"]["llm_provider"] == "ollama"
    assert config["app"]["ollama_base_url"] == "http://192.168.3.119:11434/v1"
    assert config["app"]["ollama_model_name"] == "qwen3.8:latest"
