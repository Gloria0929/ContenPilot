from __future__ import annotations

from typing import Optional

import click
import typer
from rich.console import Console
from rich.table import Table

from ..config import settings as _settings
from ..database import SessionLocal, init_db

app = typer.Typer(help="AI Content Publisher - 内容发布系统")
console = Console()

json_app = typer.Typer(help="JSON 格式输出（所有子命令均支持 --json）")
app.add_typer(json_app, name="json")


@app.callback(invoke_without_command=True)
def main_context(ctx: typer.Context):
    """
    AI Content Publisher - 内容发布系统
    
    如果不带任何子命令，显示帮助信息。
    """
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]AI Content Publisher[/bold cyan]\n")
        click.echo(ctx.command.get_help(ctx))
        raise typer.Exit()


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

@app.command(help="启动 Web 服务（同进程后台运行发布 Worker）")
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

article_app = typer.Typer(help="文章管理（创建/列表/查看/更新）")
app.add_typer(article_app, name="article")


@article_app.command("create", help="创建新文章")
def article_create(
    title: str = typer.Option("", "--title", help="文章标题"),
    content: str = typer.Option("", "--content", help="文章内容"),
    summary: str = typer.Option("", "--summary", help="文章摘要"),
    source: str = typer.Option("manual", "--source", help="来源标识"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出"),
):
    from ..services.article_service import ArticleService

    s = _session()
    try:
        a = ArticleService(s).create(title, content, summary, source=source)
    finally:
        s.close()
    _print_json(a) if json_ else console.print(f"created article #{a.id}")


@article_app.command("list", help="列出所有文章")
def article_list(json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出")):
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


@article_app.command("show", help="查看单篇文章详情")
def article_show(
    article_id: int = typer.Argument(..., help="文章 ID"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出"),
):
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


@article_app.command("update", help="修改文章。内容变更后，已有的版本审核不再对新版本生效")
def article_update(
    article_id: int = typer.Argument(..., help="文章 ID"),
    title: Optional[str] = typer.Option(None, "--title", help="新标题"),
    content: Optional[str] = typer.Option(None, "--content", help="新内容"),
    summary: Optional[str] = typer.Option(None, "--summary", help="新摘要"),
    status: Optional[str] = typer.Option(None, "--status", help="draft / ready / archived"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出"),
):
    """修改文章。内容变更后，已有的版本审核不再对新版本生效。"""
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

ai_app = typer.Typer(help="AI 功能（生成/修改/适配内容）")
app.add_typer(ai_app, name="ai")


@ai_app.command("generate", help="使用 AI 生成内容")
def ai_generate_cmd(
    prompt: str = typer.Argument(..., help="生成提示词"),
):
    import asyncio

    from ..ai import ai_generate

    result = asyncio.run(ai_generate(prompt))
    console.print(result)


@ai_app.command("revise", help="使用 AI 修改内容")
def ai_revise_cmd(
    content: str = typer.Argument(..., help="待修改的内容"),
    instruction: str = typer.Argument(..., help="修改指令"),
):
    import asyncio

    from ..ai import ai_revise

    result = asyncio.run(ai_revise(content, instruction))
    console.print(result)


@ai_app.command("adapt", help="把内容适配为指定平台风格（文档第 36 节）")
def ai_adapt_cmd(
    content: str = typer.Argument(..., help="待适配的内容"),
    platform: str = typer.Argument(..., help="目标平台名称"),
):
    """把内容适配为指定平台风格（文档第 36 节）。"""
    import asyncio

    from ..ai import ai_adapt

    result = asyncio.run(ai_adapt(content, platform))
    console.print(result)


# ---- policy ----

policy_app = typer.Typer(help="审核/发布策略管理")
app.add_typer(policy_app, name="policy")


@policy_app.command("resolve", help="查询某作用域组合最终解析出的审核/发布策略（只读）")
def policy_resolve(
    platform: Optional[str] = typer.Option(None, "--platform", help="平台名，如 juejin"),
    account_id: Optional[int] = typer.Option(None, "--account-id", help="账号 ID"),
    article_id: Optional[int] = typer.Option(None, "--article-id", help="文章 ID"),
    task_id: Optional[int] = typer.Option(None, "--task-id", help="任务 ID"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出"),
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


@policy_app.command("set", help="设置某层策略覆盖。未配置 = 继承上级")
def policy_set(
    scope: str = typer.Argument(..., help="global / platform / account / article / task"),
    scope_id: Optional[int] = typer.Argument(None, help="作用域 ID（global 不需要）"),
    review: Optional[str] = typer.Option(None, "--review", help="always / optional / never"),
    publish: Optional[str] = typer.Option(None, "--publish", help="automatic / manual / scheduled / disabled"),
    floor: bool = typer.Option(False, "--floor", help="仅 platform/account 层：设为不可被下游调松的下限"),
    clear: bool = typer.Option(False, "--clear", help="删除该层配置，恢复跟随上级"),
):
    """设置某层策略覆盖。未配置 = 继承上级。"""
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

review_app = typer.Typer(help="审核管理（待审列表/通过/驳回）")
app.add_typer(review_app, name="review")


@review_app.command("list", help="列出所有待审核项")
def review_list(json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出")):
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


@review_app.command("approve", help="通过审核")
def review_approve(
    review_id: int = typer.Argument(..., help="审核记录 ID"),
    comment: Optional[str] = typer.Option(None, "--comment", help="审核意见"),
):
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


@review_app.command("reject", help="驳回审核")
def review_reject(
    review_id: int = typer.Argument(..., help="审核记录 ID"),
    comment: Optional[str] = typer.Option(None, "--comment", help="驳回理由"),
):
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

@app.command(help="发布文章到指定平台（支持审核策略覆盖）")
def publish(
    article_id: int = typer.Argument(..., help="文章 ID"),
    platform: Optional[str] = typer.Argument(None, help="平台名称，如 juejin / cnblogs"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="账号 key 或 id；单平台时可省略（自动选该平台唯一账号）"),
    review: bool = typer.Option(False, "--review", help="强制要求审核"),
    no_review: bool = typer.Option(False, "--no-review", help="跳过审核"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出"),
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
            # 未指定平台时使用账号所属平台（并同步到 platforms，否则不会创建任务）
            platforms = platforms or [acc.platform]
            account_ids = {p: acc.id for p in platforms}
        elif platforms and len(platforms) == 1:
            # 未指定账号：该平台唯一账号时自动绑定
            platform_accounts = [
                a for a in AccountService(s).list() if a.platform == platforms[0]
            ]
            if len(platform_accounts) == 1:
                account_ids = {platforms[0]: platform_accounts[0].id}

        if not platforms:
            console.print(
                "[red]缺少平台：请指定平台参数（publisher publish <文章id> <平台>），"
                "或用 --account 指定账号以使用其所属平台[/red]"
            )
            raise typer.Exit(1)

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

task_app = typer.Typer(help="发布任务管理（列表/查看/重试/恢复/取消）")
app.add_typer(task_app, name="task")


@task_app.command("list", help="列出发布任务")
def task_list(
    status: Optional[str] = typer.Option(None, "--status", help="按状态筛选"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出"),
):
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


@task_app.command("show", help="查看任务详情")
def task_show(
    task_id: int = typer.Argument(..., help="任务 ID"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出"),
):
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


@task_app.command("retry", help="重试失败的任务")
def task_retry(
    task_id: int = typer.Argument(..., help="任务 ID"),
):
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


@task_app.command("resume", help="恢复暂停的任务")
def task_resume(
    task_id: int = typer.Argument(..., help="任务 ID"),
):
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


@task_app.command("cancel", help="取消任务")
def task_cancel(
    task_id: int = typer.Argument(..., help="任务 ID"),
):
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

account_app = typer.Typer(help="账号管理（列表/添加/启用/停用）")
app.add_typer(account_app, name="account")


@account_app.command("list", help="列出所有账号")
def account_list(json_: bool = typer.Option(False, "--json", help="以 JSON 格式输出")):
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


@account_app.command("add", help="添加账号。带 --token 时凭据将加密保存，用于官方 API 平台发布")
def account_add(
    platform: str = typer.Argument(..., help="平台名称"),
    key: Optional[str] = typer.Option(None, "--key", help="账号唯一标识（缺省自动生成）"),
    name: str = typer.Option("", "--name", help="账号显示名称"),
    username: Optional[str] = typer.Option(None, "--username", help="平台登录用户名（如博客园）"),
    token: Optional[str] = typer.Option(None, "--token", help="API 访问令牌（如博客园 MetaWeblog 访问令牌），加密存储"),
    blog_name: Optional[str] = typer.Option(None, "--blog-name", help="博客名（博客地址中 /<博客名>/ 部分），缺省取 username"),
):
    """添加账号。带 --token 时凭据将加密保存，用于官方 API 平台发布。"""
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


def _resolve_account(svc, account: str):
    """按数字 id 或账号 key 解析账号。"""
    return svc.get(int(account)) if account.isdigit() else svc.get_by_key(account)


@account_app.command("disable", help="停用账号（key 或 id）。停用后新发布任务被拦截，历史任务保留")
def account_disable(
    account: str = typer.Argument(..., help="账号 key 或 ID"),
):
    """停用账号（key 或 id）。停用后新发布任务被拦截，历史任务保留。"""
    from ..services.account_service import AccountService

    s = _session()
    try:
        svc = AccountService(s)
        acc = _resolve_account(svc, account)
        if not acc:
            console.print(f"[red]account {account} not found[/red]")
            raise typer.Exit(1)
        a = svc.set_enabled(acc.id, enabled=False)
        console.print(f"account #{a.id} {a.key} 已停用")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        s.close()


@account_app.command("enable", help="启用已停用的账号（key 或 id）")
def account_enable(
    account: str = typer.Argument(..., help="账号 key 或 ID"),
):
    """启用已停用的账号（key 或 id）。"""
    from ..services.account_service import AccountService

    s = _session()
    try:
        svc = AccountService(s)
        acc = _resolve_account(svc, account)
        if not acc:
            console.print(f"[red]account {account} not found[/red]")
            raise typer.Exit(1)
        a = svc.set_enabled(acc.id, enabled=True)
        console.print(f"account #{a.id} {a.key} 已启用")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        s.close()


# ---- browser ----

browser_app = typer.Typer(help="浏览器登录（保存登录态）")
app.add_typer(browser_app, name="browser")


@browser_app.command("login", help="打开可见浏览器完成登录并保存 storage_state")
def browser_login(
    platform: str = typer.Argument(..., help="平台名称"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="账号 key；缺省用该平台唯一账号，没有则自动创建"),
    timeout: int = typer.Option(300, "--timeout", help="等待登录完成的最长时间（秒）"),
):
    """打开可见浏览器完成登录并保存 storage_state。

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

auth_app = typer.Typer(help="认证管理（登录/登出/查看状态）")
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


@auth_app.command("login", help="登录并把 API Key 持久化到本地（跨进程生效，可用于 CLI 与 REST API Bearer）")
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
        # 删除旧的 cli key，避免重复 login 堆积
        for key in auth.list_api_keys():
            if key.name == CLI_KEY_NAME:
                auth.delete_api_key(key.id)
        access_key, secret_key = auth.create_api_key(CLI_KEY_NAME)
        raw = f"{access_key}:{secret_key}"
    finally:
        s.close()
    _save_cli_token(raw)
    console.print(f"已登录（{username}），token 已保存到 {CLI_TOKEN_FILE}")
    console.print(f"该 token 也可用于 REST API：Authorization: Bearer {access_key}:{secret_key[:8]}…")


@auth_app.command("logout", help="撤销当前 CLI 登录态（删除 API Key 并删除本地 token 文件）")
def auth_logout():
    """撤销当前 CLI 登录态（删除 API Key 并删除本地 token 文件）。"""
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
            auth.delete_api_key(key.id)
    finally:
        s.close()
    _clear_cli_token()
    console.print("logged out")


@auth_app.command("whoami", help="显示当前 CLI 登录态（校验本地 token 对应的 API Key 是否仍有效）")
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
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]错误：{e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()