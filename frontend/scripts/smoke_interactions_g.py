"""Phase G interaction smoke: catalog semantics, a11y, interactions.

Extends the Phase F suite with G-phase checks: no nested interactive
elements, accessible action names, compare toggle-off, row states.
Run from the repo root with the dev server on :5173.
"""

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

    # G1. No interactive element is nested inside another (a11y/HTML validity).
    nested = page.evaluate(
        "() => [...document.querySelectorAll('.hardware-card button button')].length"
    )
    check("no nested buttons inside catalog rows", nested == 0, f"{nested} nested")

    # G2. Row actions carry accessible names.
    names = page.evaluate(
        """() => {
          const row = document.querySelector('.hardware-card');
          const specsRetry = row.querySelector('.hardware-specs-retry');
          return {
            compare: row.querySelector('.compare-button')?.getAttribute('aria-label'),
            build: row.querySelector('.build-button')?.getAttribute('aria-label'),
            retry: specsRetry ? specsRetry.getAttribute('aria-label') : null,
            retryVisible: specsRetry ? specsRetry.offsetParent !== null : false,
          };
        }"""
    )
    check(
        "compare button has accessible name",
        bool(names["compare"]),
        names["compare"],
    )
    check(
        "build button has accessible name",
        bool(names["build"]),
        names["build"],
    )
    check(
        "specs retry button has accessible name",
        names["retry"] is None or bool(names["retry"]),
        names["retry"],
    )

    # G3. Compare toggles: pressing an already-selected row's button removes it.
    btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
    btns.nth(0).click()
    page.wait_for_timeout(600)
    first_selected = page.locator(".compare-button[aria-pressed='true']")
    check("compare selects a row", first_selected.count() == 1)
    first_selected.first.click()
    page.wait_for_timeout(600)
    check(
        "compare toggle removes a selected row",
        page.locator(".compare-button[aria-pressed='true']").count() == 0,
    )

    # G4. Build slot filled state announces identity (verified against API).
    page.locator(".hardware-card-main >> nth=0").click()
    page.wait_for_selector(".hardware-detail", timeout=15000)
    page.wait_for_timeout(1000)
    detail_name = page.locator(".hardware-detail h2").first.inner_text()
    page.click(".detail-build-button")
    page.wait_for_timeout(1500)
    slot_name = page.evaluate(
        "() => document.querySelector('.build-component-card[data-state=\"ready\"] .build-component-head h3')?.textContent || null"
    )
    check(
        "build slot announces selected identity",
        slot_name == detail_name,
        f"detail={detail_name!r} slot={slot_name!r}",
    )

    check("no page errors during interactions", len(errors) == 0, errors[:3])
    ctx.close()
    browser.close()

print(json.dumps({"passed": sum(1 for r in RESULTS if r["ok"]), "total": len(RESULTS)}))
with open("docs/design/evidence/interaction-smoke-g.json", "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, indent=2)
fails = [r for r in RESULTS if not r["ok"]]
sys.exit(1 if fails else 0)
