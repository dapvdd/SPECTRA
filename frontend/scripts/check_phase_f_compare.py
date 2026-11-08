"""Phase F comparison progression verification: empty -> one -> two."""
import json
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

    # Empty state
    page.locator("#compare").scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    empty = page.evaluate(
        """() => ({
        slots: [...document.querySelectorAll('.comparison-slot')].map(s => ({
            index: s.querySelector('.comparison-slot-index')?.textContent,
            status: s.querySelector('.comparison-slot-status')?.textContent.trim(),
            hasArt: !!s.querySelector('.hwv-slot svg'),
            action: s.querySelector('.comparison-slot-action')?.textContent.trim() || null,
        })),
        note: document.querySelector('.comparison-empty-note')?.textContent.trim() || null,
        overflow: document.documentElement.scrollWidth > window.innerWidth,
    })"""
    )
    print("EMPTY:", json.dumps(empty))

    # Select two different hardware for comparison
    btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
    btns.nth(0).click()
    page.wait_for_timeout(900)
    one = page.evaluate(
        """() => ({
        selectionItems: document.querySelectorAll('.comparison-selection-item').length,
        instruction: document.querySelector('.comparison-instruction')?.textContent.trim() || null,
        emptyGone: document.querySelectorAll('.comparison-empty').length,
        overflow: document.documentElement.scrollWidth > window.innerWidth,
    })"""
    )
    print("ONE:", json.dumps(one))

    btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
    btns.nth(0).click()
    page.wait_for_timeout(2200)
    two = page.evaluate(
        """() => ({
        table: document.querySelectorAll('.comparison-table').length,
        winnerCells: document.querySelectorAll('td.comparison-winner').length,
        headerNames: [...document.querySelectorAll('.comparison-header span')].map(s => s.textContent.trim()).slice(0,2),
        overflow: document.documentElement.scrollWidth > window.innerWidth,
    })"""
    )
    print("TWO:", json.dumps(two))
    print("errors:", errors[:3])
    ctx.close()
    browser.close()
