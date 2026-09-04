"""内容安全兜底检测测试（文档第 55 节）。"""
from publisher.services.content_safety import check_content_safety


def test_clean_content_passes():
    ok, hits = check_content_safety("今天聊聊 Docker 部署", "标题")
    assert ok
    assert hits == []


def test_banned_word_triggers():
    ok, hits = check_content_safety("这篇文章介绍如何参与赌博", "标题")
    assert not ok
    assert "赌博" in hits


def test_banned_word_in_title():
    ok, hits = check_content_safety("正文", "关于欺诈的一切")
    assert not ok
    assert "欺诈" in hits