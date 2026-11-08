from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5173/", wait_until="domcontentloaded")
    pg.wait_for_timeout(2500)
    print("errors:", errs[:3])
    print("signal count:", pg.locator(".signal").count())
    print("hero count:", pg.locator(".hero").count())
    print("stage count:", pg.locator(".hero-stage").count())
    print("h1 count:", pg.locator(".hero h1").count())
    print("signal parent:", pg.evaluate("() => { const s = document.querySelector('.signal'); return s ? s.parentElement.className : 'MISSING'; }"))
    html_head = pg.evaluate("() => document.querySelector('main') ? document.querySelector('main').className : 'no main'")
    print("main class:", html_head)
    b.close()
