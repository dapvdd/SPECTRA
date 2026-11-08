"""Phase F build slot verification: states, visuals, boundary, overflow."""
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

    page.locator("#build").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    m = page.evaluate(
        """() => ({
        cards: [...document.querySelectorAll('.build-component-card')].map(c => ({
            state: c.getAttribute('data-state'),
            slotClass: c.querySelector('.build-component-slot-class')?.textContent || null,
            status: c.querySelector('.build-component-slot-status')?.textContent.trim() || null,
            hasArt: !!c.querySelector('.hwv-slot svg'),
            browseButtons: c.querySelectorAll('.build-component-select-button').length,
        })),
        boundary: [...document.querySelectorAll('.build-intelligence-boundary, .build-relationship span')]
            .map(el => el.textContent.trim().slice(0, 50)),
        intelHeadline: document.querySelector('.build-intelligence-headline')?.textContent || null,
        intelEmpty: document.querySelector('.build-intelligence-empty')?.textContent || null,
        overflow: document.documentElement.scrollWidth > window.innerWidth,
    })"""
    )
    print("build empty:", m)
    print("errors:", errors[:3])
    ctx.close()
    browser.close()
