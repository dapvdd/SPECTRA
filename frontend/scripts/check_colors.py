from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ["dark", "light"]:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script(
            "try { localStorage.setItem('spectra-theme', '" + theme + "'); } catch (e) {}"
        )
        page = ctx.new_page()
        page.goto("http://localhost:5173/", wait_until="domcontentloaded")
        page.wait_for_selector(".nav-link", timeout=20000)
        raw = page.evaluate(
            "() => [" +
            "getComputedStyle(document.querySelector('.nav-link')).color, " +
            "getComputedStyle(document.querySelector('.navbar')).backgroundColor, " +
            "getComputedStyle(document.querySelector('.logo')).color" +
            "]"
        )
        print(theme, raw)
        ctx.close()
    browser.close()
