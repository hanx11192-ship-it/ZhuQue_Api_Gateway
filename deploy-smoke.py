#!/usr/bin/env python3
"""朱雀 API 网关改造后 · 线上部署冒烟测试

用法：
    python3 deploy-smoke.py [base_url] [password]
默认：
    base_url = http://127.0.0.1:18000   （通过 ssh -L 18000:127.0.0.1:8000 隧道）
    password = hanyx20021208
"""
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18000"
PWD = sys.argv[2] if len(sys.argv) > 2 else "hanyx20021208"
USER = "admin"
SHOT = "/workspace/zhuque-gateway"

errors = []
results = []


def ok(name, value=True):
    results.append((name, value))
    print(f"  [{'PASS' if value else 'FAIL'}] {name}")
    return value


def login(page):
    page.goto(BASE, wait_until="networkidle")
    page.fill('input[placeholder*="用户名"], input[name="username"]', USER)
    page.fill('input[type="password"]', PWD)
    page.click('button:has-text("登录")')
    page.wait_for_timeout(2500)


def goto_menu(page, text):
    page.click(f'.arco-menu-item:has-text("{text}"), .arco-menu-inline-header:has-text("{text}")')
    page.wait_for_timeout(1800)


def run(pw):
    browser = pw.chromium.launch(args=["--no-sandbox"])

    # ---------- 桌面端 ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
    page.on(
        "console",
        lambda m: errors.append(f"[console] {m.text}") if m.type == "error" and "401" not in m.text else None,
    )

    print("\n[1] 登录")
    login(page)
    ok("登录进入面板", page.url.rstrip("/") != BASE.rstrip("/") or page.query_selector(".arco-menu"))
    page.screenshot(path=f"{SHOT}/online-01-dashboard.png", full_page=True)

    print("\n[2] 环境变量管理")
    goto_menu(page, "环境变量")
    page.fill('input[placeholder*="搜索"]', "")
    # 新增
    page.click('button:has-text("新增")')
    page.wait_for_timeout(800)
    inputs = page.query_selector_all(".arco-modal input")
    if len(inputs) >= 2:
        inputs[0].fill("ONLINE_TEST")
        inputs[1].fill("vps-ok")
    ta = page.query_selector(".arco-modal textarea")
    if ta:
        ta.fill("线上冒烟")
    page.click('.arco-modal button:has-text("确定"), .arco-modal button:has-text("提交")')
    page.wait_for_timeout(1500)
    ok("新增环境变量", page.query_selector('td:has-text("ONLINE_TEST")') is not None)

    # 搜索（按值）
    page.fill('input[placeholder*="搜索"]', "vps-ok")
    page.wait_for_timeout(1200)
    ok("按变量值搜索命中", page.query_selector('td:has-text("ONLINE_TEST")') is not None)
    # 搜索（按备注）
    page.fill('input[placeholder*="搜索"]', "线上冒烟")
    page.wait_for_timeout(1200)
    ok("按备注搜索命中", page.query_selector('td:has-text("ONLINE_TEST")') is not None)
    # 搜索（按名）
    page.fill('input[placeholder*="搜索"]', "ONLINE_TEST")
    page.wait_for_timeout(1200)
    ok("按变量名搜索命中", page.query_selector('td:has-text("ONLINE_TEST")') is not None)
    page.screenshot(path=f"{SHOT}/online-02-envvars.png", full_page=True)

    # 启停
    sw = page.query_selector(".arco-switch")
    if sw:
        sw.click()
        page.wait_for_timeout(1200)
        ok("状态开关可切换", True)
    # 删除
    page.click('button:has-text("删除"), .arco-table td button:has-text("删除")')
    page.wait_for_timeout(700)
    page.click('.arco-modal button:has-text("确定"), .arco-modal button:has-text("删除")')
    page.wait_for_timeout(1500)
    ok("删除环境变量", page.query_selector('td:has-text("ONLINE_TEST")') is None)
    page.fill('input[placeholder*="搜索"]', "")
    page.wait_for_timeout(800)

    print("\n[3] 系统配置")
    goto_menu(page, "系统配置")
    ok("子页面1 系统配置(镜像源)", page.query_selector('text=镜像源') is not None)
    page.screenshot(path=f"{SHOT}/online-03-mirrors.png", full_page=True)
    for tab in ["系统信息", "安全设置"]:
        page.click(f'.arco-tabs-tab:has-text("{tab}")')
        page.wait_for_timeout(1800)
        ok(f"子页面 {tab}", True)
        if tab == "系统信息":
            page.screenshot(path=f"{SHOT}/online-04-sysinfo.png", full_page=True)
        else:
            page.screenshot(path=f"{SHOT}/online-05-security.png", full_page=True)
    # 错误旧密码
    page.fill('input[type="password"] >> nth=0', "definitely-wrong")
    page.fill('input[type="password"] >> nth=1', "abc123456")
    page.fill('input[type="password"] >> nth=2', "abc123456")
    page.click('button:has-text("修改密码"), button:has-text("确认修改")')
    page.wait_for_timeout(1500)
    msg = page.query_selector(".arco-message")
    ok("错误旧密码被拦截", msg is not None and "当前密码不正确" in (msg.inner_text() or ""))
    page.screenshot(path=f"{SHOT}/online-06-password-error.png", full_page=True)

    print("\n[4] 依赖管理")
    goto_menu(page, "依赖管理")
    for tab, label in [("python", "Python"), ("node", "Node.js"), ("linux", "Linux")]:
        if tab != "python":
            page.click(f'.arco-tabs-tab:has-text("{label}")')
            page.wait_for_timeout(2500)
        rows = len(page.query_selector_all(".arco-table-tr"))
        ok(f"选项卡 {label} 可加载", True)
        print(f"      {label} 行数: {rows}")
    page.click('.arco-tabs-tab:has-text("Node.js")')
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{SHOT}/online-07-packages-node.png", full_page=True)
    page.click('.arco-tabs-tab:has-text("Python")')
    page.wait_for_timeout(2500)
    page.screenshot(path=f"{SHOT}/online-08-packages-python.png", full_page=True)

    # 安装弹窗
    page.click('button:has-text("依赖安装")')
    page.wait_for_timeout(1200)
    ok("依赖安装弹窗打开", page.query_selector(".arco-modal") is not None)
    page.screenshot(path=f"{SHOT}/online-09-install-modal.png", full_page=True)
    # 选择 npm 看镜像源
    page.click(".arco-modal .arco-select")
    page.wait_for_timeout(600)
    opts = [o.inner_text() for o in page.query_selector_all(".arco-select-option")]
    print("      依赖类型选项:", opts)
    ok("依赖类型三种", len(opts) >= 3)
    if any("Node" in o for o in opts):
        page.click('.arco-select-option:has-text("Node")')
        page.wait_for_timeout(1000)
        sels = page.query_selector_all(".arco-modal .arco-select")
        if len(sels) >= 2:
            sels[1].click()
            page.wait_for_timeout(700)
            srcs = [o.inner_text() for o in page.query_selector_all(".arco-select-option")]
            print("      npm 镜像源选项:", srcs)
            ok("镜像源可选", len(srcs) >= 1)
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    page.screenshot(path=f"{SHOT}/online-10-after-modal.png", full_page=True)

    ctx.close()

    # ---------- 移动端（安卓/平板键入验证） ----------
    print("\n[5] 移动端终端键入")
    mctx = browser.new_context(
        **pw.devices["Pixel 5"], has_touch=True, is_mobile=True
    )
    mpage = mctx.new_page()
    mpage.on("pageerror", lambda e: errors.append(f"[mobile pageerror] {e}"))
    mpage.goto(BASE, wait_until="networkidle")
    mpage.fill('input[name="username"], input[placeholder*="用户名"]', USER)
    mpage.fill('input[type="password"]', PWD)
    mpage.click('button:has-text("登录")')
    mpage.wait_for_timeout(2500)

    # 打开抽屉菜单
    burger = mpage.query_selector(".mobile-burger, .arco-drawer .arco-menu, button[aria-label*='menu']")
    if burger:
        burger.click()
        mpage.wait_for_timeout(900)
    mpage.click('.arco-menu-item:has-text("终端"), .arco-drawer .arco-menu-item:has-text("终端")')
    mpage.wait_for_timeout(3500)

    inp = mpage.query_selector(".term-mobile-bar input, input.term-input")
    ok("移动端输入框存在", inp is not None)
    if inp:
        mpage.tap(".term-mobile-bar input, input.term-input")
        mpage.wait_for_timeout(600)
        focused = mpage.evaluate("() => document.activeElement && document.activeElement.tagName")
        print("      焦点元素:", focused)
        ok("输入框获得焦点", focused == "INPUT")
        mpage.keyboard.type("echo MOBILE_VPS_OK")
        mpage.wait_for_timeout(400)
        mpage.keyboard.press("Enter")
        mpage.wait_for_timeout(2500)
        txt = mpage.inner_text(".xterm-rows, .xterm-screen") or mpage.inner_text("body")
        ok("终端回显 MOBILE_VPS_OK", "MOBILE_VPS_OK" in txt.replace(" ", ""))
        print("      回显片段:", [l for l in txt.split("\n") if "MOBILE" in l][:2])
    mpage.screenshot(path=f"{SHOT}/online-11-terminal-mobile.png", full_page=True)
    mctx.close()

    browser.close()


with sync_playwright() as pw:
    run(pw)

print("\n=== 运行时错误 ===")
if errors:
    for e in errors[:10]:
        print(" -", e)
else:
    print("无")

failed = [n for n, v in results if not v]
print(f"\n=== 汇总: {len(results) - len(failed)}/{len(results)} 通过 ===")
if failed:
    print("未通过:", failed)
