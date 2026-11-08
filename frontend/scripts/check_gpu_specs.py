from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("try { localStorage.setItem('spectra-theme', 'dark'); } catch (e) {}")
    page = ctx.new_page()
    errors, responses = [], []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on(
        "response",
        lambda r: responses.append((r.url.rsplit('/', 1)[-1], r.status))
        if "/hardware/" in r.url and "/facets" not in r.url and "/sources" not in r.url else None,
    )
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.click(".filter-buttons-type button:has-text('GPU')")
    page.wait_for_timeout(3500)
    pending = page.evaluate("() => document.querySelectorAll('.hardware-card-specs-pending').length")
    loaded = page.evaluate("() => document.querySelectorAll('.hardware-card-specs:not(.hardware-card-specs-pending)').length")
    print("GPU page: pending =", pending, "| loaded =", loaded)
    print("responses:", responses[:14])
    print("errors:", errors[:4])
    ctx.close()
    browser.close()
