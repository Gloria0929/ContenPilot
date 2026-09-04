"""掘金浏览器发布链路单元测试（Adapter + 脚本注册）。"""
import pytest

from publisher.platforms.base import PublishResult


@pytest.fixture()
def adapter():
    from publisher.platforms.registry import get_adapter, import_platforms

    import_platforms()
    return get_adapter("juejin")


async def test_capabilities_browser_mode(adapter):
    caps = await adapter.capabilities()
    assert caps["mode"] == "browser"
    assert caps["supports_publish"] is True


async def test_check_account_browser_mode_needs_no_credentials(adapter):
    """浏览器平台依赖 storage_state 登录态，不要求加密凭据。"""

    class _Account:
        encrypted_credentials = None
        key = "juejin_default"

    assert await adapter.check_account(_Account()) is True


async def test_publish_routes_to_browser_layer(adapter, monkeypatch):
    """publish/create_draft 已接入浏览器层（不再返回 not_implemented 占位）。"""
    captured = []

    async def fake_run(platform, content, account=None, task_id=None, mode="publish"):
        captured.append((platform, mode))
        return PublishResult(success=True)

    import publisher.browser

    monkeypatch.setattr(publisher.browser, "run_browser_publish", fake_run)

    class _Content:
        title = "t"
        content = "c"

    await adapter.publish(_Content())
    await adapter.create_draft(_Content())
    assert captured == [("juejin", "publish"), ("juejin", "draft")]


def test_browser_script_registered():
    from publisher.browser.scripts import get_script

    script = get_script("juejin")
    assert script is not None
    assert script.platform == "juejin"
    assert script.creator_url == "https://juejin.cn/editor/drafts/new?v=2"
