"""SPECTRA V3 Phase D - screenshots + structural verification.

Usage: python capture_screens.py <outdir> [--label before|after]
"""

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173/"
VIEWPORTS = [("desktop-1440", 1440, 900), ("tablet-768", 768, 1024), ("mobile-390", 390, 844)]
THEMES = ["dark", "light"]

METRICS_JS = """
() => {
  const doc = document.documentElement;
  const h1 = document.querySelector('h1');
  const hero = document.querySelector('.hero');
  const nav = document.querySelector('.navbar');
  const heroRect = hero ? hero.getBoundingClientRect() : null;
  const grid = document.querySelector('.hardware-grid');
  return {
    horizontalOverflow: doc.scrollWidth > window.innerWidth,
    h1FontSize: h1 ? getComputedStyle(h1).fontSize : null,
    heroHeightPx: heroRect ? Math.round(heroRect.height) : null,
    heroDominatesViewport: heroRect ? (heroRect.height / window.innerHeight) > 0.85 : null,
    navHeightPx: nav ? Math.round(nav.getBoundingClientRect().height) : null,
    cardCount: document.querySelectorAll('.hardware-card').length,
    firstCardWidth: grid && grid.firstElementChild ? Math.round(grid.firstElementChild.getBoundingClientRect().width) : null,
    bodyFont: getComputedStyle(document.body).fontFamily.split(',')[0],
    h1Font: h1 ? getComputedStyle(h1).fontFamily.split(',')[0] : null,
    theme: doc.getAttribute('data-theme'),
  };
}
"""


def shoot(page, outdir, label, name, errors, api_calls):
    path = outdir / f"{label}--{name}.png"
    page.screenshot(path=str(path), full_page=True)
    metrics = page.evaluate(METRICS_JS)
    print(f"saved {path.name} | overflow={metrics['horizontalOverflow']} "
          f"h1={metrics['h1FontSize']} hero={metrics['heroHeightPx']}px "
          f"dominates={metrics['heroDominatesViewport']} cards={metrics['cardCount']}")
    return {"shot": path.name, "metrics": metrics, "errors": errors, "api": api_calls}


def collect(page, errors, api_calls):
    page.on("console", lambda msg, e=errors: e.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
    page.on("response", lambda r, a=api_calls: a.append({"url": r.url, "status": r.status})
            if "/hardware/" in r.url or "/sources" in r.url else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir")
    parser.add_argument("--label", default="before")
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    label = args.label
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in THEMES:
            for name, width, height in VIEWPORTS:
                ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
                ctx.add_init_script(
                    f"try {{ window.localStorage.setItem('spectra-theme', '{theme}'); }} catch (e) {{}}"
                )
                page = ctx.new_page()
                errors, api_calls = [], []
                collect(page, errors, api_calls)
                key = f"{theme}--{name}"
                try:
                    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_selector(".hardware-card", timeout=20000)
                    page.wait_for_timeout(1500)
                    results.append(shoot(page, outdir, label, f"home--{key}", errors, api_calls))

                    if name == "desktop-1440":
                        errs2, api2 = [], []
                        collect(page, errs2, api2)
                        try:
                            page.click(".hardware-card-main >> nth=0", timeout=5000)
                            page.wait_for_selector(".hardware-detail", timeout=15000)
                            page.wait_for_timeout(1800)
                            results.append(shoot(page, outdir, label, f"detail--{key}", errs2, api2))
                        except Exception as exc:
                            errs2.append(f"detail failed: {exc}")
                            results.append({"shot": f"detail--{key} FAILED", "errors": errs2})

                        errs3, api3 = [], []
                        collect(page, errs3, api3)
                        try:
                            page.goto(BASE_URL, wait_until="domcontentloaded")
                            page.wait_for_selector(".hardware-card", timeout=20000)
                            btns = page.locator(".compare-button:not([disabled])")
                            if btns.count() >= 2:
                                btns.nth(0).click()
                                page.wait_for_timeout(500)
                                btns = page.locator(".compare-button:not([disabled])")
                                btns.nth(0).click()
                                page.wait_for_timeout(2500)
                                page.click(".comparison-jump-link", timeout=5000)
                                page.wait_for_timeout(1000)
                                results.append(shoot(page, outdir, label, f"compare--{key}", errs3, api3))
                            else:
                                errs3.append(f"only {btns.count()} compare buttons available")
                                results.append({"shot": f"compare--{key} SKIPPED", "errors": errs3})
                        except Exception as exc:
                            errs3.append(f"compare failed: {exc}")
                            results.append({"shot": f"compare--{key} FAILED", "errors": errs3})
                except Exception as exc:
                    errors.append(f"load failed: {exc}")
                    results.append({"shot": f"home--{key} FAILED", "errors": errors})
                ctx.close()
        browser.close()

    (outdir / f"{label}--manifest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    shots = len([r for r in results if not r["shot"].endswith(("FAILED", "SKIPPED"))])
    total_errs = sum(len(r.get("errors", [])) for r in results)
    print(f"done: {shots} shots, {total_errs} console errors")


if __name__ == "__main__":
    sys.exit(main())
