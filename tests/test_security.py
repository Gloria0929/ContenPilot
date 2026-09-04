"""日志脱敏中间件测试（文档第 75.21 条）。"""
from publisher.security import redact, redact_json


def test_redact_top_level_sensitive_key():
    assert redact({"token": "abc123"}) == {"token": "***REDACTED***"}


def test_redact_nested_sensitive_key():
    data = {"config": {"access_token": "secret", "foo": "keep"}}
    assert redact(data) == {
        "config": {"access_token": "***REDACTED***", "foo": "keep"}
    }


def test_redact_list_of_dicts():
    data = {"cookies": [{"name": "session", "value": "x"}]}
    assert redact(data) == {"cookies": "***REDACTED***"}


def test_redact_does_not_touch_non_sensitive():
    data = {"title": "hello", "content": "world", "platform": "juejin"}
    assert redact(data) == data


def test_redact_json_serializes():
    out = redact_json({"password": "x", "a": 1})
    assert "***REDACTED***" in out
    import json

    parsed = json.loads(out)
    assert parsed["password"] == "***REDACTED***"
    assert parsed["a"] == 1