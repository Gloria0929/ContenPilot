from __future__ import annotations

import json

import httpx
import pytest

from publisher.pipeline import video_pipeline


def _mock_async_client(monkeypatch, handler):
    real_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return real_async_client(transport=transport, **kwargs)

    monkeypatch.setattr(video_pipeline.httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_moneyprinterturbo_health_uses_ping(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == httpx.URL("http://moneyprinterturbo:8080/ping")
        return httpx.Response(200, text='"pong"')

    _mock_async_client(monkeypatch, handler)

    client = video_pipeline.MoneyPrinterTurboClient(
        "http://moneyprinterturbo:8080/"
    )
    assert await client.check_health() is True


@pytest.mark.asyncio
async def test_moneyprinterturbo_create_video_uses_v1_api(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == httpx.URL(
            "http://moneyprinterturbo:8080/api/v1/videos"
        )
        assert json.loads(request.content) == {
            "video_subject": "测试主题",
            "video_script": "测试文案",
            "voice_name": "zh-CN-YunxiNeural",
            "video_aspect": "9:16",
        }
        assert request.headers["content-type"] == "application/json"
        return httpx.Response(
            200,
            json={
                "status": 200,
                "message": "success",
                "data": {"task_id": "task-123"},
            },
        )

    _mock_async_client(monkeypatch, handler)

    client = video_pipeline.MoneyPrinterTurboClient(
        "http://moneyprinterturbo:8080"
    )
    result = await client.create_video_task(
        video_script="测试文案",
        video_subject="测试主题",
        voice_name="zh-CN-YunxiNeural",
        video_aspect_ratio="9:16",
    )

    assert result["data"]["task_id"] == "task-123"
