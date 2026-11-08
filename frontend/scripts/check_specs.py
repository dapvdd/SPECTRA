import sys

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("try { localStorage.setItem('spectra-theme', 'dark'); } catch (e) {}")
    page = ctx.new_page()
    errors, responses = [], []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on(
        "response",
        lambda r: responses.append((r.url.split("/")[-2:], r.status))
        if "/hardware/" in r.url and "/facets" not in r.url else None,
    )
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.wait_for_timeout(3000)
    kickers = page.locator(".hardware-card-kicker")
    types = [kickers.nth(i).inner_text().strip() for i in range(kickers.count())]
    print("card types:", types)
    print("spec responses:", responses[:15])
    print("errors:", errors[:5])
    ctx.close()
    browser.close()
