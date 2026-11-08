"""SPECTRA Phase F — full evidence capture.

Captures the 7 required states across dark/light themes at desktop/tablet/
mobile viewports, with per-shot DOM metrics (overlap, overflow, console
errors). Run from the frontend/ directory with the dev server on :5173.

Usage: python scripts/capture_phase_f.py <outdir> [--label after]
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173/"
VIEWPORTS = [("desktop-1440", 1440, 900), ("tablet-768", 768, 1024), ("mobile-390", 390, 844)]
THEMES = ["dark", "light"]

METRICS_JS = """
() => {
  const doc = document.documentElement;
  const rect = (sel) => {
    const el = document.querySelector(sel);
    return el ? el.getBoundingClientRect() : null;
  };
  const overlap = (a, b) =>
    a && b && !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
  const h1 = rect('.hero h1');
  const stage = rect('.hero-stage-svg');
  const cards = [...document.querySelectorAll('.build-component-card')].map(c => ({
    state: c.getAttribute('data-state'),
    name: c.querySelector('.build-component-head h3')?.textContent.trim() || null,
  }));
  const slots = [...document.querySelectorAll('.comparison-slot')].map(s =>
    s.querySelector('.comparison-slot-index')?.textContent || null);
  return {
    horizontalOverflow: doc.scrollWidth > window.innerWidth,
    h1StageOverlap: overlap(h1, stage),
    buildStates: cards,
    comparisonSlots: slots,
    comparisonTable: document.querySelectorAll('.comparison-table').length,
    winnerCells: document.querySelectorAll('td.comparison-winner').length,
    theme: doc.getAttribute('data-theme'),
  };
}
"""


def shoot(page, outdir, label, name, errors):
    path = outdir / f"{label}--{name}.png"
    page.screenshot(path=str(path), full_page=True)
    metrics = page.evaluate(METRICS_JS)
    flat = {k: metrics[k] for k in ("horizontalOverflow", "h1StageOverlap", "buildStates", "comparisonSlots", "comparisonTable", "winnerCells")}
    print(f"saved {path.name} | {json.dumps(flat)[:220]}")
    return {"shot": path.name, "metrics": metrics, "errors": list(errors)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir")
    parser.add_argument("--label", default="after")
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    label = args.label
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Full matrix for the homepage: theme x viewport.
        for theme in THEMES:
            for name, width, height in VIEWPORTS:
                ctx = browser.new_context(viewport={"width": width, "height": height})
                ctx.add_init_script(
                    f"try {{ window.localStorage.setItem('spectra-theme', '{theme}'); }} catch (e) {{}}"
                )
                page = ctx.new_page()
                errors = []
                page.on("console", lambda msg, e=errors: e.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
                try:
                    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_selector(".hardware-card", timeout=20000)
                    page.wait_for_timeout(1500)
                    results.append(shoot(page, outdir, label, f"home--{theme}--{name}", errors))

                    if name == "desktop-1440":
                        # 2. Build empty
                        page.locator("#build").scroll_into_view_if_needed()
                        page.wait_for_timeout(700)
                        results.append(shoot(page, outdir, label, f"build-empty--{theme}--desktop-1440", errors))

                        # 3. Build with CPU selected: open first card, add to build
                        page.locator(".hardware-card-main >> nth=0").scroll_into_view_if_needed()
                        page.wait_for_timeout(400)
                        page.click(".hardware-card-main >> nth=0")
                        page.wait_for_selector(".hardware-detail", timeout=15000)
                        page.wait_for_timeout(1200)
                        page.click(".detail-build-button")
                        page.wait_for_timeout(1800)
                        page.locator("#build").scroll_into_view_if_needed()
                        page.wait_for_timeout(700)
                        results.append(shoot(page, outdir, label, f"build-cpu--{theme}--desktop-1440", errors))

                        # 4. Build with CPU+GPU: back to catalog, GPU filter, first GPU
                        page.click(".back-button")
                        page.wait_for_selector(".hardware-card", timeout=15000)
                        page.wait_for_timeout(600)
                        page.locator("#explore").scroll_into_view_if_needed()
                        page.click(".filter-buttons-type button:has-text('GPU')")
                        page.wait_for_timeout(1600)
                        page.click(".hardware-card-main >> nth=0")
                        page.wait_for_selector(".hardware-detail", timeout=15000)
                        page.wait_for_timeout(1200)
                        page.click(".detail-build-button")
                        page.wait_for_timeout(1800)
                        page.locator("#build").scroll_into_view_if_needed()
                        page.wait_for_timeout(700)
                        results.append(shoot(page, outdir, label, f"build-cpu-gpu--{theme}--desktop-1440", errors))

                        # 5. Comparison empty: clear build, fresh catalog
                        page.goto(BASE_URL, wait_until="domcontentloaded")
                        page.wait_for_selector(".hardware-card", timeout=20000)
                        page.evaluate("() => { try { sessionStorage.clear(); } catch (e) {} }")
                        page.goto(BASE_URL, wait_until="domcontentloaded")
                        page.wait_for_selector(".hardware-card", timeout=20000)
                        page.wait_for_timeout(1000)
                        page.locator("#compare").scroll_into_view_if_needed()
                        page.wait_for_timeout(700)
                        results.append(shoot(page, outdir, label, f"compare-empty--{theme}--desktop-1440", errors))

                        # 6. Comparison with one selected
                        btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
                        btns.nth(0).click()
                        page.wait_for_timeout(1200)
                        page.locator("#compare").scroll_into_view_if_needed()
                        page.wait_for_timeout(700)
                        results.append(shoot(page, outdir, label, f"compare-one--{theme}--desktop-1440", errors))

                        # 7. Comparison with two selected
                        btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
                        btns.nth(0).click()
                        page.wait_for_timeout(2500)
                        page.locator("#compare").scroll_into_view_if_needed()
                        page.wait_for_timeout(800)
                        results.append(shoot(page, outdir, label, f"compare-two--{theme}--desktop-1440", errors))
                except Exception as exc:
                    errors.append(f"capture failed: {exc}")
                    results.append({"shot": f"{label}--home--{theme}--{name} FAILED", "errors": errors})
                ctx.close()
        browser.close()

    (outdir / f"{label}--manifest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    shots = len([r for r in results if not r["shot"].endswith("FAILED")])
    total_errs = sum(len(r.get("errors", [])) for r in results)
    print(f"done: {shots} shots, {total_errs} console errors")


if __name__ == "__main__":
    import sys

    sys.exit(main())
