"""Phase 10 interaction smoke: search, filter, sort, detail, compare, modal."""

import json
import sys

from playwright.sync_api import sync_playwright

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": str(detail)[:200]})
    print(("PASS" if ok else "FAIL"), name, "-", str(detail)[:120])


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(
        "try { localStorage.setItem('spectra-theme', 'dark'); } catch (e) {}"
    )
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.wait_for_timeout(800)

    # 0. Keyboard: skip link is the first tab stop on a fresh page
    page.keyboard.press("Tab")
    focused = page.evaluate("() => document.activeElement?.className || ''")
    check("skip link is first tab stop", "skip-link" in focused, focused)

    # 1. Search narrows results
    page.fill("#catalog-search", "ryzen")
    page.wait_for_timeout(700)
    cards = page.locator(".hardware-card")
    count = cards.count()
    names = [cards.nth(i).locator("h3").inner_text().lower() for i in range(min(count, 5))]
    check("search narrows to ryzen", count > 0 and all("ryzen" in n for n in names), f"{count} cards: {names[:3]}")

    # 2. Clear search restores
    page.click(".clear-search-icon")
    page.wait_for_timeout(700)
    check("clear search restores", page.locator(".hardware-card").count() == 12)

    # 3. Type filter CPU with facet count
    page.click(".filter-buttons-type button:has-text('CPU')")
    page.wait_for_timeout(1200)
    kickers = page.locator(".hardware-card-kicker")
    n = kickers.count()
    vals = {kickers.nth(i).inner_text().strip() for i in range(min(n, 8))}
    check("CPU filter shows only CPUs", vals <= {"CPU"}, f"{vals} across {n} cards")

    # 4. Sort newest puts 2026 first (server dates exist through 2026)
    page.click(".filter-buttons-type button:has-text('All hardware')")
    page.wait_for_timeout(900)
    page.select_option(".catalog-sort-select", "newest")
    page.wait_for_timeout(700)
    first_name = page.locator(".hardware-card h3").first.inner_text()
    dates = page.evaluate(
        "() => fetch('http://127.0.0.1:8000/hardware').then(r => r.json())"
    )
    newest = sorted(
        [d["release_date"] for d in dates if d.get("release_date")],
        reverse=True,
    )[0]
    expected = [d["name"] for d in dates if d.get("release_date") == newest]
    check("sort newest puts newest-dated first", first_name in expected, f"{first_name!r} in {expected[:3]}")
    page.select_option(".catalog-sort-select", "default")
    page.wait_for_timeout(500)

    # 5. Detail open -> readout strip -> back
    page.click(".hardware-card-main >> nth=0")
    page.wait_for_selector(".hardware-detail", timeout=15000)
    page.wait_for_timeout(1200)
    readouts = page.locator(".detail-readout")
    check("detail opens with readout strip", readouts.count() > 0, f"{readouts.count()} readouts")
    page.click(".back-button")
    page.wait_for_timeout(700)
    check("back returns to catalog", page.locator(".hardware-card").count() == 12)

    # 6. Compare flow: two DIFFERENT cards -> jump link -> table
    btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
    btns.nth(0).click()
    page.wait_for_timeout(600)
    btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
    btns.nth(0).click()
    page.wait_for_timeout(2500)
    check("comparison selection badge", page.locator(".comparison-selection").count() == 1)
    check("two slots filled", page.locator(".comparison-selection-item").count() == 2)
    page.click(".comparison-jump-link")
    page.wait_for_timeout(1200)
    check("comparison table renders", page.locator(".comparison-table").count() == 1)
    winners = page.locator("td.comparison-winner")
    print("  winner cells:", winners.count())

    # 7b. Fit modal opens, drawer animation, ESC closes
    page.click(".hardware-card-main >> nth=0")
    page.wait_for_selector(".hardware-detail", timeout=15000)
    page.wait_for_timeout(800)
    page.click(".hardware-fit-btn")
    page.wait_for_selector(".hardware-fit-modal", timeout=10000)
    page.wait_for_timeout(500)
    check("fit modal opens", True, "panel visible")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    check("ESC closes fit modal", page.locator(".hardware-fit-modal").count() == 0)

    check("no page errors during interactions", len(errors) == 0, errors[:3])
    ctx.close()
    browser.close()

print(json.dumps({"passed": sum(1 for r in RESULTS if r["ok"]), "total": len(RESULTS)}))
with open("docs/design/evidence/interaction-smoke.json", "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, indent=2)
fails = [r for r in RESULTS if not r["ok"]]
sys.exit(1 if fails else 0)
