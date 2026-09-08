"""思否探针 v12：标签搜索交互测试（搜索→点选→确认已选）。"""
import asyncio
import json

from publisher.browser import BrowserWorker, storage_state_path

STATE = storage_state_path("segmentfault", "segmentfault_default")


async def main():
    worker = BrowserWorker(headless=False)
    try:
        ctx = await worker.start(storage_state=str(STATE))
        page = await ctx.new_page()
        await page.goto("https://segmentfault.com/write", wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(3000)

        await page.locator("#tags-toggle").click()
        await page.wait_for_timeout(1000)

        # 搜索框信息
        sb = page.locator(".dropdown-menu.show input.form-control").first
        print("search placeholder:", await sb.get_attribute("placeholder"))

        # 输入关键词搜索
        await sb.click()
        await sb.fill("自动化")
        await page.wait_for_timeout(1500)

        results = await page.evaluate(
            """() => {
              const menu = document.querySelector('.dropdown-menu.show');
              const out = {mt2: [], searchVal: menu?.querySelector('input.form-control')?.value};
              const containers = [...menu.querySelectorAll('div')].filter(d => d.className.includes('mt-2'));
              containers.forEach(c => {
                [...c.children].forEach(ch => {
                  const r = ch.getBoundingClientRect();
                  out.mt2.push({tag: ch.tagName, cls: (ch.className||'').toString().slice(0,70), text: (ch.innerText||'').slice(0,60).replace(/\\n/g,'|'), visible: r.width>0, w: Math.round(r.width)});
                });
              });
              return out;
            }"""
        )
        print(json.dumps(results, ensure_ascii=False, indent=1))

        # 点第一个可见结果
        clicked = await page.evaluate(
            """() => {
              const menu = document.querySelector('.dropdown-menu.show');
              const containers = [...menu.querySelectorAll('div')].filter(d => d.className.includes('mt-2'));
              for (const c of containers) {
                for (const ch of c.children) {
                  const r = ch.getBoundingClientRect();
                  if (r.width > 0) { ch.click(); return (ch.innerText||'').slice(0,40); }
                }
              }
              return null;
            }"""
        )
        print("clicked tag:", clicked)
        await page.wait_for_timeout(1000)

        # 确认标签已选：tags-left 数量变化 + 已选标签区域
        after = await page.evaluate(
            """() => {
              const out = {};
              const left = document.querySelector('.tags-left');
              out.tagsLeft = left ? left.textContent.trim() : null;
              // 已选标签 chip
              const chips = [...document.querySelectorAll('[class*="badge"], .tag-chip, [class*="tag"]')].filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && el.children.length === 0;
              }).map(el => ({cls: (el.className||'').toString().slice(0,50), text: (el.textContent||'').trim().slice(0,20)}));
              out.chips = chips.slice(0, 10);
              return out;
            }"""
        )
        print(json.dumps(after, ensure_ascii=False, indent=1))
        await page.screenshot(path="/tmp/sf_tag_selected.png")
    finally:
        await worker.stop()


asyncio.run(main())
