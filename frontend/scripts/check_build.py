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
    page.wait_for_timeout(800)

    # Build section: empty slot + browse affordance
    page.locator("#build").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    m = page.evaluate(
        """() => ({
        emptySlots: document.querySelectorAll('.build-component-empty').length,
        browseButtons: document.querySelectorAll('.build-component-select-button').length,
        boundary: [...document.querySelectorAll('.build-intelligence-boundary, .build-relationship span')]
            .map(el => el.textContent.trim().slice(0, 60)),
        overflow: document.documentElement.scrollWidth > window.innerWidth,
    })"""
    )
    print("build:", m)

    # Comparison empty state
    page.locator(".comparison-section").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    m = page.evaluate(
        """() => ({
        empty: document.querySelectorAll('.comparison-empty').length,
        wash: getComputedStyle(document.querySelector('.comparison-empty'), '::before').backgroundImage.slice(0, 60),
        overflow: document.documentElement.scrollWidth > window.innerWidth,
    })"""
    )
    print("comparison empty:", m, "errors:", errors[:3])
    ctx.close()
    browser.close()
