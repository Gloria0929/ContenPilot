"""Typer CLI（文档第 43-45 节）。所有命令走 Publisher Core，支持 --json。"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..config import settings as _settings
from ..database import SessionLocal, init_db

app = typer.Typer(help="AI Content Publisher")
console = Console()

json_app = typer.Typer()
app.add_typer(json_app, name="json")


def _session():
    init_db()
    session = SessionLocal()
    return session


def _print_json(obj) -> None:
    import json

    from ..schemas import ORMModel

    if isinstance(obj, list):
        data = [_to_dict(o) for o in obj]
    else:
        data = _to_dict(obj)
    console.print_json(json.dumps(data, ensure_ascii=False, default=str, indent=2))


def _to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        d = {}
        for k, v in vars(obj).items():
            if k.startswith("_"):
                continue
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            d[k] = v
        return d
    return str(obj)


# ---- server ----

@app.command()
def server(host: str = "127.0.0.1", port: int = 8000):
    """启动 Web 服务（同进程后台运行发布 Worker）。"""
    import threading

    import uvicorn

    init_db()

    def _run_worker() -> None:
        import asyncio

        from ..workers import run_worker_loop

        asyncio.run(run_worker_loop())

    threading.Thread(target=_run_worker, daemon=True, name="publisher-worker").start()
    uvicorn.run("publisher.api.app:app", host=host, port=port, reload=False)


# ---- article ----

article_app = typer.Typer()
app.add_typer(article_app, name="article")


@article_app.command("create")
def article_create(
    title: str = typer.Option("", "--title"),
    content: str = typer.Option("", "--content"),
    summary: str = typer.Option("", "--summary"),
    source: str = typer.Option("manual", "--source"),
    json_: bool = typer.Option(False, "--json"),
):
    from ..services.article_service import ArticleService

    s = _session()
    try:
        a = ArticleService(s).create(title, content, summary, source=source)
    finally:
        s.close()
    _print_json(a) if json_ else console.print(f"created article #{a.id}")


@article_app.command("list")
def article_list(json_: bool = typer.Option(False, "--json")):
    from ..services.article_service import ArticleService

    s = _session()
    try:
        articles = ArticleService(s).list()
    finally:
        s.close()
    if json_:
        _print_json([{"id": a.id, "title": a.title, "status": a.status} for a in articles])
        return
    table = Table(title="Articles")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Status")
    for a in articles:
        table.add_row(str(a.id), a.title, a.status)
    console.print(table)


@article_app.command("show")
def article_show(article_id: int, json_: bool = typer.Option(False, "--json")):
    from ..services.article_service import ArticleService

    s = _session()
    try:
        a = ArticleService(s).get(article_id)
    finally:
        s.close()
    if not a:
        console.print(f"[red]article {article_id} not found[/red]")
        raise typer.Exit(1)
    if json_:
        _print_json(_to_dict(a))
    else:
        console.print(f"[bold]{a.title}[/bold] ({a.status})\n{a.content}")


@article_app.command("update")
def article_update(
    article_id: int = typer.Argument(...),
    title: Optional[str] = typer.Option(None, "--title"),
    content: Optional[str] = typer.Option(None, "--content"),
    summary: Optional[str] = typer.Option(None, "--summary"),
    status: Optional[str] = typer.Option(None, "--status", help="draft / ready / archived"),
    json_: bool = typer.Option(False, "--json"),
):
    """修改文章。内容变更后，已有的版本审核不再对新版本生效（§35）。"""
    from ..services.article_service import ArticleService

    if not any((title, content, summary, status)):
        console.print("[red]至少提供 --title/--content/--summary/--status 之一[/red]")
        raise typer.Exit(1)
    if status and status not in ("draft", "ready", "archived"):
        console.print(f"[red]无效的 status '{status}'，可选：draft / ready / archived[/red]")
        raise typer.Exit(1)

    s = _session()
    try:
        a = ArticleService(s).update(
            article_id, title=title, content=content, summary=summary, status=status
        )
    finally:
        s.close()
    if not a:
        console.print(f"[red]article {article_id} not found[/red]")
        raise typer.Exit(1)
    _print_json(_to_dict(a)) if json_ else console.print(f"updated article #{a.id} ({a.status})")


# ---- ai ----

ai_app = typer.Typer()
app.add_typer(ai_app, name="ai")


@ai_app.command("generate")
def ai_generate_cmd(prompt: str):
    import asyncio

    from ..ai import ai_generate

    result = asyncio.run(ai_generate(prompt))
    console.print(result)


@ai_app.command("revise")
def ai_revise_cmd(content: str, instruction: str):
    import asyncio

    from ..ai import ai_revise

    result = asyncio.run(ai_revise(content, instruction))
    console.print(result)


@ai_app.command("adapt")
def ai_adapt_cmd(content: str, platform: str):
    """把内容适配为指定平台风格（文档第 36 节）。"""
    import asyncio

    from ..ai import ai_adapt

    result = asyncio.run(ai_adapt(content, platform))
    console.print(result)


# ---- policy ----

policy_app = typer.Typer()
app.add_typer(policy_app, name="policy")


@policy_app.command("resolve")
def policy_resolve(
    platform: Optional[str] = typer.Option(None, "--platform", help="平台名，如 juejin"),
    account_id: Optional[int] = typer.Option(None, "--account-id"),
    article_id: Optional[int] = typer.Option(None, "--article-id"),
    task_id: Optional[int] = typer.Option(None, "--task-id"),
    json_: bool = typer.Option(False, "--json"),
):
    """查询某作用域组合最终解析出的审核/发布策略（只读）。"""
    from sqlalchemy import select

    from ..models import Platform
    from ..services.policy_service import PolicyService

    s = _session()
    try:
        platform_id = None
        if platform:
            row = s.scalar(select(Platform).where(Platform.name == platform))
            if not row:
                console.print(f"[red]unknown platform: {platform}[/red]")
                raise typer.Exit(1)
            platform_id = row.id
        r = PolicyService(s).resolve(
            platform_id=platform_id,
            account_id=account_id,
            article_id=article_id,
            task_id=task_id,
        )
    finally:
        s.close()
    data = {
        "review_policy": r.review_policy.value,
        "publish_policy": r.publish_policy,
        "is_floor_locked": r.is_floor_locked,
        "review_scope": r.review_scope,
        "publish_scope": r.publish_scope,
    }
    if json_:
        _print_json(data)
    else:
        floor = " [red]（下限锁定，不可被调松）[/red]" if r.is_floor_locked else ""
        console.print(f"审核策略: {data['review_policy']}{floor}")
        console.print(f"发布策略: {data['publish_policy']}")


@policy_app.command("set")
def policy_set(
    scope: str = typer.Argument(..., help="global / platform / account / article / task"),
    scope_id: Optional[int] = typer.Argument(None),
    review: Optional[str] = typer.Option(None, "--review", help="always / optional / never"),
    publish: Optional[str] = typer.Option(None, "--publish", help="automatic / manual / scheduled / disabled"),
    floor: bool = typer.Option(False, "--floor", help="仅 platform/account 层：设为不可被下游调松的下限"),
    clear: bool = typer.Option(False, "--clear", help="删除该层配置，恢复跟随上级"),
):
    """设置某层策略覆盖。未配置 = 继承上级（§2.5）。"""
    from ..services.policy_service import PolicyService

    if scope == "global":
        scope_id = None
    elif scope_id is None:
        console.print(f"[red]scope={scope} 需要提供 scope_id[/red]")
        raise typer.Exit(1)

    if clear:
        review, publish = None, None
    elif review is None and publish is None:
        console.print("[red]需要 --review/--publish 至少一项，或使用 --clear[/red]")
        raise typer.Exit(1)

    s = _session()
    try:
        PolicyService(s).set_policy(scope, scope_id, review, publish, is_floor=floor)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        s.close()
    if clear:
        console.print(f"cleared {scope} policy")
    else:
        console.print(
            f"set {scope}({scope_id}) review={review or '-'} publish={publish or '-'}"
            + (" [floor]" if floor else "")
        )


# ---- review ----

review_app = typer.Typer()
app.add_typer(review_app, name="review")


@review_app.command("list")
def review_list(json_: bool = typer.Option(False, "--json")):
    s = _session()
    try:
        from ..services.review_service import ReviewService
        reviews = ReviewService(s).list_pending()
    finally:
        s.close()
    if json_:
        _print_json([_to_dict(r) for r in reviews])
    else:
        for r in reviews:
            console.print(f"#{r.id} task={r.task_id} version={r.article_version_id}")


@review_app.command("approve")
def review_approve(review_id: int, comment: Optional[str] = None):
    from ..services.review_service import ReviewService

    s = _session()
    try:
        r = ReviewService(s).approve(review_id, "cli", comment)
        console.print(f"approved review #{r.id}")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        s.close()


@review_app.command("reject")
def review_reject(review_id: int, comment: Optional[str] = None):
    from ..services.review_service import ReviewService

    s = _session()
    try:
        r = ReviewService(s).reject(review_id, "cli", comment)
        console.print(f"rejected review #{r.id}")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        s.close()


# ---- publish ----

@app.command("publish")
def publish(
    article_id: int,
    platform: Optional[str] = typer.Argument(None),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="账号 key 或 id；单平台时可省略（自动选该平台唯一账号）"),
    review: bool = typer.Option(False, "--review"),
    no_review: bool = typer.Option(False, "--no-review"),
    json_: bool = typer.Option(False, "--json"),
):
    from ..services.account_service import AccountService
    from ..services.publish_service import PublishService

    if platform:
        from ..platforms.registry import available_platforms, import_platforms

        import_platforms()
        valid = available_platforms()
        if platform not in valid:
            console.print(
                f"[red]未知平台 '{platform}'，可用平台：{', '.join(valid)}[/red]"
            )
            raise typer.Exit(1)

    s = _session()
    try:
        svc = PublishService(s)
        platforms = [platform] if platform else []
        review_override = None
        if review:
            review_override = "always"
        elif no_review:
            review_override = "never"

        # 解析账号 → account_ids（文档第 19 节）
        account_ids: dict[str, int] = {}
        if account:
            accounts = AccountService(s)
            acc = (
                accounts.get(int(account))
                if account.isdigit()
                else accounts.get_by_key(account)
            )
            if not acc:
                console.print(f"[red]account {account} not found[/red]")
                raise typer.Exit(1)
            target_platforms = platforms or [acc.platform]
            account_ids = {p: acc.id for p in target_platforms}
        elif platforms and len(platforms) == 1:
            # 未指定账号：该平台唯一账号时自动绑定
            platform_accounts = [
                a for a in AccountService(s).list() if a.platform == platforms[0]
            ]
            if len(platform_accounts) == 1:
                account_ids = {platforms[0]: platform_accounts[0].id}

        tasks = svc.create_tasks(
            article_id, platforms,
            account_ids=account_ids or None,
            review_override=review_override,
            allow_override_review=True,  # 本机 CLI 默认信任
            requester="cli",
        )
        if json_:
            _print_json(tasks)
        else:
            for t in tasks:
                console.print(f"task #{t.id} platform={t.platform} review={t.review_policy} publish={t.publish_policy} status={t.status}")
    except (ValueError, PermissionError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        s.close()


# ---- task ----

task_app = typer.Typer()
app.add_typer(task_app, name="task")


@task_app.command("list")
def task_list(status: Optional[str] = None, json_: bool = typer.Option(False, "--json")):
    from ..services.publish_service import PublishService

    s = _session()
    try:
        tasks = PublishService(s).list_tasks(status)
    finally:
        s.close()
    if json_:
        _print_json(tasks)
    else:
        table = Table(title="Tasks")
        for col in ("ID", "Platform", "Review", "Publish", "Status"):
            table.add_column(col)
        for t in tasks:
            table.add_row(str(t.id), t.platform, t.review_policy, t.publish_policy, t.status)
        console.print(table)


@task_app.command("show")
def task_show(task_id: int, json_: bool = typer.Option(False, "--json")):
    from ..services.publish_service import PublishService

    s = _session()
    try:
        t = PublishService(s).get_task(task_id)
    finally:
        s.close()
    if not t:
        console.print(f"[red]task {task_id} not found[/red]")
        raise typer.Exit(1)
    _print_json(t) if json_ else console.print(_to_dict(t))


@task_app.command("retry")
def task_retry(task_id: int):
    from ..services.publish_service import PublishService

    s = _session()
    try:
        t = PublishService(s).retry(task_id)
        console.print(f"task #{t.id} -> {t.status}")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        s.close()


@task_app.command("resume")
def task_resume(task_id: int):
    from ..services.publish_service import PublishService

    s = _session()
    try:
        t = PublishService(s).resume(task_id)
        console.print(f"task #{t.id} -> {t.status}")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        s.close()


@task_app.command("cancel")
def task_cancel(task_id: int):
    from ..services.publish_service import PublishService

    s = _session()
    try:
        t = PublishService(s).cancel(task_id)
        console.print(f"task #{t.id} -> {t.status}")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        s.close()


# ---- account ----

account_app = typer.Typer()
app.add_typer(account_app, name="account")


@account_app.command("list")
def account_list(json_: bool = typer.Option(False, "--json")):
    from ..services.account_service import AccountService

    s = _session()
    try:
        accounts = AccountService(s).list()
    finally:
        s.close()
    if json_:
        _print_json(accounts)
    else:
        for a in accounts:
            console.print(f"#{a.id} {a.key} platform={a.platform} status={a.status}")


@account_app.command("add")
def account_add(
    platform: str,
    key: Optional[str] = None,
    name: str = "",
    username: Optional[str] = typer.Option(None, "--username", help="平台登录用户名（如博客园）"),
    token: Optional[str] = typer.Option(None, "--token", help="API 访问令牌（如博客园 MetaWeblog 访问令牌），加密存储"),
    blog_name: Optional[str] = typer.Option(None, "--blog-name", help="博客名（博客地址中 /<博客名>/ 部分），缺省取 username"),
):
    """添加账号。带 --token 时凭据将加密保存（§53），用于官方 API 平台发布。"""
    from ..services.account_service import AccountService

    key = key or f"{platform}_{name or (username or 'default')}"
    credentials = None
    if token or username:
        if not (token and username):
            console.print("[red]--username 与 --token 必须同时提供[/red]")
            raise typer.Exit(1)
        credentials = {"username": username, "token": token}
        if platform == "cnblogs":
            credentials["blog_name"] = blog_name or username

    s = _session()
    try:
        a = AccountService(s).create(key, platform, name, credentials=credentials)
        hint = "（凭据已加密保存）" if credentials else ""
        console.print(f"account #{a.id} {a.key}{hint}")
    finally:
        s.close()


# ---- browser ----

browser_app = typer.Typer()
app.add_typer(browser_app, name="browser")


@browser_app.command("login")
def browser_login(
    platform: str,
    account: Optional[str] = typer.Option(None, "--account", "-a", help="账号 key；缺省用该平台唯一账号，没有则自动创建"),
    timeout: int = typer.Option(300, "--timeout", help="等待登录完成的最长时间（秒）"),
):
    """打开可见浏览器完成登录并保存 storage_state（§24/§25）。

    本机：直接弹出 Chromium 窗口；容器：经 noVNC(:6080) 操作。
    """
    import asyncio

    from ..browser import LoginError, run_browser_login
    from ..services.account_service import AccountService

    s = _session()
    try:
        svc = AccountService(s)
        if account:
            acct = svc.get_by_key(account)
            if not acct:
                console.print(f"[red]account {account} not found[/red]")
                raise typer.Exit(1)
        else:
            platform_accounts = [a for a in svc.list() if a.platform == platform]
            if len(platform_accounts) == 1:
                acct = platform_accounts[0]
            elif not platform_accounts:
                acct = svc.create(f"{platform}_default", platform, "")
                console.print(f"created account #{acct.id} {acct.key}")
            else:
                console.print(
                    f"[red]该平台有多个账号，请用 --account 指定: "
                    f"{', '.join(a.key for a in platform_accounts)}[/red]"
                )
                raise typer.Exit(1)

        console.print(
            f"[yellow]请在打开的浏览器窗口中完成 {platform} 登录"
            f"（容器环境请通过 noVNC :6080 操作），等待最多 {timeout}s…[/yellow]"
        )
        try:
            path = asyncio.run(run_browser_login(platform, acct.key, timeout=timeout))
        except LoginError as e:
            console.print(f"[red]login failed: {e}[/red]")
            raise typer.Exit(1)

        bs = svc.ensure_session(acct.id, platform)
        bs.session_path = str(path)
        bs.status = "idle"
        s.commit()
        console.print(f"[green]登录态已保存: {path}[/green]")
    finally:
        s.close()


# ---- auth ----

auth_app = typer.Typer()
app.add_typer(auth_app, name="auth")

CLI_TOKEN_FILE = _settings.data_dir / "cli_session.json"
CLI_KEY_NAME = "cli"


def _load_cli_token() -> str | None:
    import json

    try:
        return json.loads(CLI_TOKEN_FILE.read_text())["token"]
    except (OSError, ValueError, KeyError):
        return None


def _save_cli_token(raw: str) -> None:
    import json
    import time

    CLI_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    CLI_TOKEN_FILE.write_text(
        json.dumps({"token": raw, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    )
    CLI_TOKEN_FILE.chmod(0o600)  # token 视同密码，仅当前用户可读


def _clear_cli_token() -> None:
    try:
        CLI_TOKEN_FILE.unlink()
    except FileNotFoundError:
        pass


@auth_app.command("login")
def auth_login(
    username: Optional[str] = typer.Option(None, "--username", "-u", help="默认 admin"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="未提供时交互输入"),
):
    """登录并把 API Key 持久化到本地（跨进程生效，可用于 CLI 与 REST API Bearer）。"""
    from ..auth import AuthService

    username = username or _settings.admin_username
    if password is None:
        password = typer.prompt("密码", hide_input=True)

    s = _session()
    try:
        auth = AuthService(s)
        # login() 同时完成凭据校验（恒定时间比较）与 session 创建（此处只用其校验结果）
        if not auth.login(username, password):
            console.print("[red]登录失败：用户名或密码错误[/red]")
            raise typer.Exit(1)
        # 撤销旧的 cli key，避免重复 login 堆积
        for key in auth.list_api_keys():
            if key.name == CLI_KEY_NAME and not key.revoked_at:
                auth.revoke_api_key(key.id)
        raw = auth.create_api_key(CLI_KEY_NAME)
    finally:
        s.close()
    _save_cli_token(raw)
    console.print(f"已登录（{username}），token 已保存到 {CLI_TOKEN_FILE}")
    console.print(f"该 token 也可用于 REST API：Authorization: Bearer {raw[:8]}…")


@auth_app.command("logout")
def auth_logout():
    """撤销当前 CLI 登录态（revoke API Key 并删除本地 token 文件）。"""
    from ..auth import AuthService

    raw = _load_cli_token()
    if not raw:
        console.print("not logged in")
        return
    s = _session()
    try:
        auth = AuthService(s)
        key = auth.validate_api_key(raw)
        if key:
            auth.revoke_api_key(key.id)
    finally:
        s.close()
    _clear_cli_token()
    console.print("logged out")


@auth_app.command("whoami")
def auth_whoami():
    """显示当前 CLI 登录态（校验本地 token 对应的 API Key 是否仍有效）。"""
    from ..auth import AuthService

    raw = _load_cli_token()
    if not raw:
        console.print("not logged in")
        return
    s = _session()
    try:
        key = AuthService(s).validate_api_key(raw)
    finally:
        s.close()
    if key:
        console.print(f"{key.name} (api key #{key.id})")
    else:
        console.print("not logged in (token 已失效，请重新 login)")


def main() -> None:
    import sys

    try:
        app()
    except Exception as e:  # 兜底：只显示错误信息，不显示代码 traceback
        console.print(f"[red]错误：{e}[/red]")
        sys.exit(1)