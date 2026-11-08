"""Phase F build slot selected-state verification via real catalog records."""
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

    # Open the first CPU card's detail page
    page.click(".hardware-card-main >> nth=0")
    page.wait_for_selector(".hardware-detail", timeout=15000)
    page.wait_for_timeout(1200)

    # Add to build
    build_btn = page.locator(".detail-build-button").first
    print("build button label:", build_btn.inner_text().strip())
    build_btn.click()
    page.wait_for_timeout(1500)

    m = page.evaluate(
        """() => ({
        cards: [...document.querySelectorAll('.build-component-card')].map(c => ({
            state: c.getAttribute('data-state'),
            status: c.querySelector('.build-component-slot-status')?.textContent.trim() || null,
            name: c.querySelector('.build-component-head h3')?.textContent || null,
            specRows: c.querySelectorAll('.build-component-specs div').length,
            hasChange: !!c.querySelector('.build-action-button'),
            hasClear: !!c.querySelector('.build-clear-button'),
        })),
        intelHeadline: document.querySelector('.build-intelligence-headline')?.textContent || null,
        intelFacts: [...document.querySelectorAll('.build-intelligence-fact')].map(f => f.textContent.trim().replace(/\\s+/g,' ').slice(0,60)),
        overflow: document.documentElement.scrollWidth > window.innerWidth,
    })"""
    )
    import json
    print(json.dumps(m, indent=1)[:1600])
    print("errors:", errors[:3])
    ctx.close()
    browser.close()
