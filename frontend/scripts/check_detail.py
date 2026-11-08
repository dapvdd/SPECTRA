from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("try { localStorage.setItem('spectra-theme', 'dark'); } catch (e) {}")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.click(".hardware-card-main >> nth=0")
    page.wait_for_selector(".hardware-detail", timeout=15000)
    page.wait_for_timeout(1500)
    m = page.evaluate(
        """() => ({
        readouts: document.querySelectorAll('.detail-readout').length,
        actionsDir: getComputedStyle(document.querySelector('.detail-header-actions')).flexDirection,
        overflow: document.documentElement.scrollWidth > window.innerWidth,
    })"""
    )
    print("cpu detail:", m)
    ctx.close()

    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("try { localStorage.setItem('spectra-theme', 'dark'); } catch (e) {}")
    page = ctx.new_page()
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.click(".filter-buttons-type button:has-text('GPU')")
    page.wait_for_timeout(3000)
    page.click(".hardware-card-main >> nth=0")
    page.wait_for_selector(".hardware-detail", timeout=15000)
    page.wait_for_timeout(1500)
    m = page.evaluate(
        """() => ({
        readouts: document.querySelectorAll('.detail-readout').length,
        overflow: document.documentElement.scrollWidth > window.innerWidth,
    })"""
    )
    print("gpu detail:", m)
    ctx.close()
    browser.close()
