"""CLI 远程模式：存在 ~/.contentpilot/api_client.json（或 CONTENTPILOT_* 环境变量）
时，CLI 命令自动转发为 REST API 调用，与 skill/content-publisher 的路由规则一致。

无配置时 remote_client() 返回 None，CLI 维持本地数据库模式（行为不变）。
配置存在但不完整时抛 RemoteError（不静默回落本地，避免误写本地库）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.table import Table

console = Console()

_CONFIG_FILE = Path.home() / ".contentpilot" / "api_client.json"
_TIMEOUT = 30.0


class RemoteError(Exception):
    """远程调用失败（只携带用户可读消息，不带 traceback）。"""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


# ---- 配置加载（环境变量 > 配置文件） ----


def _config_from_env() -> dict | None:
    base_url = os.environ.get("CONTENTPILOT_BASE_URL")
    access_key = os.environ.get("CONTENTPILOT_ACCESS_KEY")
    secret_key = os.environ.get("CONTENTPILOT_SECRET_KEY")
    if not any((base_url, access_key, secret_key)):
        return None
    if not all((base_url, access_key, secret_key)):
        raise RemoteError(
            "CONTENTPILOT_BASE_URL / CONTENTPILOT_ACCESS_KEY / "
            "CONTENTPILOT_SECRET_KEY 需同时设置"
        )
    return {"base_url": base_url, "access_key": access_key, "secret_key": secret_key}


def _config_from_file() -> dict | None:
    if not _CONFIG_FILE.exists():
        return None
    try:
        data = json.loads(_CONFIG_FILE.read_text())
    except (OSError, ValueError):
        raise RemoteError(f"api_client.json 无法解析，请检查 {_CONFIG_FILE}")
    if not isinstance(data, dict) or not all(
        data.get(k) for k in ("base_url", "access_key", "secret_key")
    ):
        raise RemoteError(
            f"api_client.json 缺少 base_url / access_key / secret_key，请补全 {_CONFIG_FILE}"
        )
    return data


_client: "RemoteClient | None" = None
_client_resolved = False


def remote_client() -> "RemoteClient | None":
    """存在远程配置时返回 RemoteClient，否则 None（本地模式）。"""
    global _client, _client_resolved
    if _client_resolved:
        return _client
    _client_resolved = True
    cfg = _config_from_env() or _config_from_file()
    _client = RemoteClient(**cfg) if cfg else None
    return _client


class RemoteClient:
    def __init__(self, base_url: str, access_key: str, secret_key: str):
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {access_key}:{secret_key}"}

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
    ) -> Any:
        url = f"{self.base_url}/api{path}"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            resp = httpx.request(
                method,
                url,
                params=clean_params or None,
                json=json_body,
                headers=self._headers,
                timeout=_TIMEOUT,
            )
        except httpx.HTTPError:
            raise RemoteError(f"无法连接到 {self.base_url}：服务是否在运行？")
        if resp.is_error:
            raise RemoteError(self._error_message(resp), status=resp.status_code)
        try:
            return resp.json()
        except ValueError:
            return None

    @staticmethod
    def _error_message(resp: httpx.Response) -> str:
        if resp.status_code == 401:
            return "API Key 无效或已吊销，请在 Web 设置页重新生成并更新 api_client.json"
        try:
            detail = resp.json().get("detail")
        except ValueError:
            detail = None
        if detail:
            return str(detail)
        return f"请求失败（HTTP {resp.status_code}）"


# ---- 输出辅助（与 cli/__init__.py 本地模式观感一致） ----


def _print_json(data: Any) -> None:
    console.print_json(json.dumps(data, ensure_ascii=False, default=str, indent=2))


def _not_found(e: RemoteError, label: str, ref: Any) -> RemoteError:
    """把 404 / not found 转换为与本地模式一致的提示。"""
    if e.status == 404 or "not found" in str(e):
        return RemoteError(f"{label} {ref} not found")
    return e


def _find_account(accounts: list[dict], account: str) -> dict | None:
    """按数字 id 或账号 key 解析账号（与本地 _resolve_account 一致）。"""
    return next(
        (a for a in accounts if str(a["id"]) == account or a["key"] == account), None
    )


# ---- article ----


def article_create(c, *, title, content, summary, source, json_):
    a = c.request(
        "POST",
        "/articles",
        json_body={"title": title, "content": content, "summary": summary, "source": source},
    )
    _print_json(a) if json_ else console.print(f"created article #{a['id']}")


def article_list(c, *, json_):
    articles = c.request("GET", "/articles")
    if json_:
        _print_json(articles)
        return
    table = Table(title="Articles")
    for col in ("ID", "Title", "Status"):
        table.add_column(col)
    for a in articles:
        table.add_row(str(a["id"]), a["title"], a["status"])
    console.print(table)


def article_show(c, *, article_id, json_):
    try:
        a = c.request("GET", f"/articles/{article_id}")
    except RemoteError as e:
        raise _not_found(e, "article", article_id)
    if json_:
        _print_json(a)
    else:
        console.print(f"[bold]{a['title']}[/bold] ({a['status']})\n{a['content']}")


def article_update(c, *, article_id, title, content, summary, status, json_):
    body = {
        k: v
        for k, v in {
            "title": title,
            "content": content,
            "summary": summary,
            "status": status,
        }.items()
        if v is not None
    }
    try:
        a = c.request("PATCH", f"/articles/{article_id}", json_body=body)
    except RemoteError as e:
        raise _not_found(e, "article", article_id)
    _print_json(a) if json_ else console.print(f"updated article #{a['id']} ({a['status']})")


# ---- publish / task ----


def publish(c, *, article_id, platform, account, review, no_review, json_):
    # 平台校验（数据来自远程）
    platforms_data = c.request("GET", "/platforms")
    valid = [p["name"] for p in platforms_data]
    if platform and platform not in valid:
        raise RemoteError(f"未知平台 '{platform}'，可用平台：{', '.join(valid)}")

    accounts = c.request("GET", "/accounts")
    platforms = [platform] if platform else []
    account_ids: dict[str, int] = {}
    if account:
        acc = _find_account(accounts, account)
        if not acc:
            raise RemoteError(f"account {account} not found")
        # 未指定平台时使用账号所属平台
        platforms = platforms or [acc["platform"]]
        account_ids = {p: acc["id"] for p in platforms}
    elif platforms and len(platforms) == 1:
        # 未指定账号：该平台唯一账号时自动绑定
        platform_accounts = [a for a in accounts if a["platform"] == platforms[0]]
        if len(platform_accounts) == 1:
            account_ids = {platforms[0]: platform_accounts[0]["id"]}

    if not platforms:
        raise RemoteError(
            "缺少平台：请指定平台参数（publisher publish <文章id> <平台>），"
            "或用 --account 指定账号以使用其所属平台"
        )

    review_override = None
    if review:
        review_override = "always"
    elif no_review:
        review_override = "never"

    tasks = c.request(
        "POST",
        "/publish",
        json_body={
            "article_id": article_id,
            "platforms": platforms,
            "account_ids": account_ids or None,
            "review_override": review_override,
        },
    )
    if json_:
        _print_json(tasks)
    else:
        for t in tasks:
            console.print(
                f"task #{t['id']} platform={t['platform']} review={t['review_policy']} "
                f"publish={t['publish_policy']} status={t['status']}"
            )


def task_list(c, *, status, json_):
    tasks = c.request("GET", "/tasks", params={"status": status})
    if json_:
        _print_json(tasks)
        return
    table = Table(title="Tasks")
    for col in ("ID", "Platform", "Review", "Publish", "Status"):
        table.add_column(col)
    for t in tasks:
        table.add_row(
            str(t["id"]), t["platform"], t["review_policy"], t["publish_policy"], t["status"]
        )
    console.print(table)


def task_show(c, *, task_id, json_):
    try:
        t = c.request("GET", f"/tasks/{task_id}")
    except RemoteError as e:
        raise _not_found(e, "task", task_id)
    _print_json(t) if json_ else console.print(t)


def _task_action(c, path: str, task_id: int) -> None:
    try:
        t = c.request("POST", f"/tasks/{task_id}/{path}")
    except RemoteError as e:
        raise _not_found(e, "task", task_id)
    console.print(f"task #{t['id']} -> {t['status']}")


def task_retry(c, *, task_id):
    _task_action(c, "retry", task_id)


def task_resume(c, *, task_id):
    _task_action(c, "resume", task_id)


def task_cancel(c, *, task_id):
    _task_action(c, "cancel", task_id)


# ---- review ----


def review_list(c, *, json_):
    # REST /reviews 返回全部记录；CLI 语义与本地一致：仅待审核项
    reviews = [r for r in c.request("GET", "/reviews") if r["status"] == "pending"]
    if json_:
        _print_json(reviews)
        return
    for r in reviews:
        console.print(f"#{r['id']} task={r['task_id']} version={r['article_version_id']}")


def review_approve(c, *, review_id, comment):
    r = c.request("POST", f"/reviews/{review_id}/approve", json_body={"comment": comment})
    console.print(f"approved review #{r['id']}")


def review_reject(c, *, review_id, comment):
    r = c.request("POST", f"/reviews/{review_id}/reject", json_body={"comment": comment})
    console.print(f"rejected review #{r['id']}")


# ---- account ----


def account_list(c, *, json_):
    accounts = c.request("GET", "/accounts")
    if json_:
        _print_json(accounts)
        return
    for a in accounts:
        console.print(f"#{a['id']} {a['key']} platform={a['platform']} status={a['status']}")


def account_add(c, *, platform, key, name, username, token, blog_name):
    key = key or f"{platform}_{name or (username or 'default')}"
    credentials = None
    if token or username:
        if not (token and username):
            raise RemoteError("--username 与 --token 必须同时提供")
        credentials = {"username": username, "token": token}
        if platform == "cnblogs":
            credentials["blog_name"] = blog_name or username
    a = c.request(
        "POST",
        "/accounts",
        json_body={"key": key, "platform": platform, "name": name, "credentials": credentials},
    )
    hint = "（凭据已加密保存）" if credentials else ""
    console.print(f"account #{a['id']} {a['key']}{hint}")


def _set_account_status(c, *, account, enabled):
    accounts = c.request("GET", "/accounts")
    acc = _find_account(accounts, account)
    if not acc:
        raise RemoteError(f"account {account} not found")
    a = c.request(
        "PATCH",
        f"/accounts/{acc['id']}",
        json_body={"status": "active" if enabled else "disabled"},
    )
    console.print(f"account #{a['id']} {a['key']} 已{'启用' if enabled else '停用'}")


def account_disable(c, *, account):
    _set_account_status(c, account=account, enabled=False)


def account_enable(c, *, account):
    _set_account_status(c, account=account, enabled=True)


# ---- policy ----


def policy_resolve(c, *, platform, account_id, article_id, task_id, json_):
    platform_id = None
    if platform:
        row = next(
            (p for p in c.request("GET", "/platforms") if p["name"] == platform), None
        )
        if not row:
            raise RemoteError(f"unknown platform: {platform}")
        platform_id = row["id"]
    r = c.request(
        "GET",
        "/policies/resolve",
        params={
            "platform_id": platform_id,
            "account_id": account_id,
            "article_id": article_id,
            "task_id": task_id,
        },
    )
    data = {
        "review_policy": r["review_policy"],
        "publish_policy": r["publish_policy"],
        "is_floor_locked": r["is_floor_locked"],
        "review_scope": r["review_scope"],
        "publish_scope": r["publish_scope"],
    }
    if json_:
        _print_json(data)
    else:
        floor = " [red]（下限锁定，不可被调松）[/red]" if r["is_floor_locked"] else ""
        console.print(f"审核策略: {data['review_policy']}{floor}")
        console.print(f"发布策略: {data['publish_policy']}")


def policy_set(c, *, scope, scope_id, review, publish, floor, clear):
    # 参数校验与本地 CLI 一致
    if scope == "global":
        scope_id = None
    elif scope_id is None:
        raise RemoteError(f"scope={scope} 需要提供 scope_id")
    if clear:
        review, publish = None, None
    elif review is None and publish is None:
        raise RemoteError("需要 --review/--publish 至少一项，或使用 --clear")

    c.request(
        "POST",
        "/policies",
        json_body={
            "scope_type": scope,
            "scope_id": scope_id,
            "review_mode": review,
            "publish_mode": publish,
            "is_floor": floor,
        },
    )
    if clear:
        console.print(f"cleared {scope} policy")
    else:
        console.print(
            f"set {scope}({scope_id}) review={review or '-'} publish={publish or '-'}"
            + (" [floor]" if floor else "")
        )


# ---- auth ----


def auth_whoami(c):
    w = c.request("GET", "/auth/whoami")
    console.print(f"{w['username']}（远程 API Key，{c.base_url}）")
