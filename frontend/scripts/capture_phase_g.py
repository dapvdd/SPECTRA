"""SPECTRA Phase G — full evidence capture.

Extends capture_phase_f.py with the G-phase catalog states (default,
GPU-filtered, missing-spec row, hover/focus, 320 spot-check, GPU-pair
comparison). Captures before/after across dark/light, with per-shot DOM
metrics, filter state, selected ids and console errors.

NOTE: the working model cannot visually inspect PNG files; this harness
records structural metrics only. Aesthetic review is a human step.

Usage (from repo root):
  python frontend/scripts/capture_phase_g.py <outdir> [--label after]
      [--base-url http://localhost:5173/]
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = [
    ("desktop-1440", 1440, 900),
    ("tablet-768", 768, 1024),
    ("mobile-390", 390, 844),
]
SPOT_VIEWPORT = ("mobile-320", 320, 640)
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
  const kickers = [...document.querySelectorAll('.comparison-header-type')].map(
    k => k.textContent.trim());
  const rowCards = [...document.querySelectorAll('.hardware-card')].slice(0, 12).map(c => ({
    name: c.querySelector('.hardware-card-name, .hardware-card-main h3')?.textContent.trim() || null,
    specCount: c.querySelectorAll('.hardware-card-specs span').length,
  }));
  return {
    horizontalOverflow: doc.scrollWidth > window.innerWidth,
    cardOverflowCount: [...document.querySelectorAll('.hardware-card')]
      .map(c => c.scrollWidth - c.clientWidth).filter(d => d > 2).length,
    h1StageOverlap: overlap(h1, stage),
    buildStates: cards,
    comparisonSlots: slots,
    comparisonTable: document.querySelectorAll('.comparison-table').length,
    winnerCells: document.querySelectorAll('td.comparison-winner').length,
    comparisonKickers: kickers,
    catalogRows: rowCards,
    typeFilter: document.querySelector('.filter-buttons-type .filter-button.active')
      ?.textContent.trim() || null,
    manufacturerFilter: [...document.querySelectorAll('.filter-buttons:not(.filter-buttons-type) .filter-button')]
      .find(b => b.classList.contains('active'))?.textContent.trim() || null,
    theme: doc.getAttribute('data-theme'),
    viewport: {w: window.innerWidth, h: window.innerHeight},
  };
}
"""


def shoot(page, outdir, label, name, errors, extra=None):
    path = outdir / f"{label}--{name}.png"
    page.screenshot(path=str(path), full_page=True)
    metrics = page.evaluate(METRICS_JS)
    if extra:
        metrics.update(extra)
    flat = {
        k: metrics.get(k)
        for k in (
            "horizontalOverflow", "cardOverflowCount", "h1StageOverlap",
            "typeFilter", "manufacturerFilter", "comparisonKickers",
            "comparisonTable",
        )
    }
    print(f"saved {path.name} | {json.dumps(flat)[:230]}")
    return {"shot": path.name, "metrics": metrics, "errors": list(errors)}


def capture_catalog_states(page, outdir, label, theme, errors, results, vp):
    """Catalog states shared by the full matrix and the 320 spot-check."""
    # default catalog
    results.append(shoot(page, outdir, label,
                         f"catalog-default--{theme}--{vp}", errors))

    # GPU-filtered catalog
    page.locator(".filter-buttons-type button", has_text="GPU").click()
    page.wait_for_timeout(1400)
    results.append(shoot(page, outdir, label, f"catalog-gpu--{theme}--{vp}",
                         errors,
                         extra={"note": "missing-spec rows visible among GPUs"}))

    # hover and focus states on a catalog row (desktop only)
    if page.viewport_size["width"] >= 1024:
        row = page.locator(".hardware-card-main").first
        row.hover()
        page.wait_for_timeout(450)
        results.append(shoot(page, outdir, label,
                             f"catalog-row-hover--{theme}--{vp}", errors))
        page.locator(".compare-button").first.focus()
        page.wait_for_timeout(450)
        results.append(shoot(page, outdir, label,
                             f"catalog-row-focus--{theme}--{vp}", errors))


def capture_flow_states(page, outdir, label, theme, errors, results, base_url):
    """Build + comparison flows (desktop-1440 only, per Phase F discipline)."""
    # The catalog-states pass may have left a type filter active; the build
    # flow must start from the unfiltered default (CPU cards first), matching
    # the Phase F evidence contract (build-cpu fills the CPU slot).
    page.locator(".filter-buttons-type button", has_text="All hardware").click()
    page.wait_for_timeout(1500)

    # build empty
    page.locator("#build").scroll_into_view_if_needed()
    page.wait_for_timeout(700)
    results.append(shoot(page, outdir, label, f"build-empty--{theme}", errors))

    # build with CPU
    page.locator(".hardware-card-main >> nth=0").scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    page.locator(".hardware-card-main >> nth=0").click()
    page.wait_for_selector(".hardware-detail", timeout=15000)
    page.wait_for_timeout(1200)
    results.append(shoot(page, outdir, label, f"detail-cpu--{theme}", errors))
    detail_name = page.locator(".hardware-detail h2").first.inner_text()
    page.click(".detail-build-button")
    page.wait_for_timeout(1800)
    page.locator("#build").scroll_into_view_if_needed()
    page.wait_for_timeout(700)
    results.append(shoot(page, outdir, label, f"build-cpu--{theme}", errors,
                         extra={"selectedIds": [detail_name]}))

    # build with CPU+GPU
    page.click(".back-button")
    page.wait_for_selector(".hardware-card", timeout=15000)
    page.wait_for_timeout(600)
    page.locator("#explore").scroll_into_view_if_needed()
    page.locator(".filter-buttons-type button", has_text="GPU").click()
    page.wait_for_timeout(1600)
    page.locator(".hardware-card-main >> nth=0").click()
    page.wait_for_selector(".hardware-detail", timeout=15000)
    page.wait_for_timeout(1200)
    gpu_name = page.locator(".hardware-detail h2").first.inner_text()
    page.click(".detail-build-button")
    page.wait_for_timeout(1800)
    page.locator("#build").scroll_into_view_if_needed()
    page.wait_for_timeout(700)
    results.append(shoot(page, outdir, label, f"build-cpu-gpu--{theme}", errors,
                         extra={"selectedIds": [detail_name, gpu_name]}))

    # comparison empty
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.evaluate("() => { try { sessionStorage.clear(); } catch (e) {} }")
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.wait_for_timeout(1000)
    page.locator("#compare").scroll_into_view_if_needed()
    page.wait_for_timeout(700)
    results.append(shoot(page, outdir, label, f"compare-empty--{theme}", errors))

    # comparison one selected (CPU-first: parity with Phase F evidence)
    btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
    btns.nth(0).click()
    page.wait_for_timeout(1200)
    page.locator("#compare").scroll_into_view_if_needed()
    page.wait_for_timeout(700)
    results.append(shoot(page, outdir, label, f"compare-one--{theme}", errors))

    # comparison two selected
    btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
    btns.nth(0).click()
    page.wait_for_selector(".comparison-table", timeout=20000)
    page.wait_for_timeout(1500)
    page.locator("#compare").scroll_into_view_if_needed()
    page.wait_for_timeout(800)
    results.append(shoot(page, outdir, label, f"compare-two-cpu--{theme}", errors))

    # GPU-pair comparison (G5 regression state: kickers must read GPU/GPU).
    # The build flow above stores a CPU+GPU build in sessionStorage, which the
    # baseline reads as a "loaded pair" and feeds the (crashing) GPU verdict
    # effect. Clear session storage and reload so only the compare list drives
    # this state.
    page.evaluate("() => { try { sessionStorage.clear(); } catch (e) {} }")
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.wait_for_timeout(1000)
    page.locator(".filter-buttons-type button", has_text="GPU").click()
    page.wait_for_timeout(1500)
    btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
    btns.nth(0).click()
    page.wait_for_timeout(400)
    btns = page.locator(".compare-button[aria-pressed='false']:not([disabled])")
    btns.nth(0).click()
    page.wait_for_selector(".comparison-table", timeout=20000)
    page.wait_for_timeout(1500)
    page.locator("#compare").scroll_into_view_if_needed()
    page.wait_for_timeout(800)
    results.append(shoot(page, outdir, label, f"compare-two-gpu--{theme}", errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir")
    parser.add_argument("--label", default="after")
    parser.add_argument("--base-url", default="http://localhost:5173/")
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    label = args.label
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Full matrix for the catalog: theme x viewport (incl. 320 spot-check).
        for theme in THEMES:
            for name, width, height in VIEWPORTS + [SPOT_VIEWPORT]:
                ctx = browser.new_context(viewport={"width": width, "height": height})
                ctx.add_init_script(
                    f"try {{ window.localStorage.setItem('spectra-theme', '{theme}'); }} catch (e) {{}}"
                )
                page = ctx.new_page()
                errors = []
                page.on("console", lambda msg, e=errors: e.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
                try:
                    page.goto(args.base_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_selector(".hardware-card", timeout=20000)
                    page.wait_for_timeout(1500)
                    capture_catalog_states(page, outdir, label, theme, errors,
                                           results, name)

                    if name == "desktop-1440":
                        capture_flow_states(page, outdir, label, theme, errors,
                                            results, args.base_url)
                except Exception as exc:
                    errors.append(f"capture failed: {exc}")
                    results.append({"shot": f"{label}--{theme}--{name} FAILED",
                                    "errors": errors})
                ctx.close()
        browser.close()

    manifest = {
        "label": label,
        "tool": "playwright chromium, full-page screenshots",
        "note": ("PNGs are structural evidence only; the working model cannot "
                 "visually inspect them. Aesthetic review is a human step."),
        "known_baseline_failure": (
            "At the before capture (baseline 264e826) the compare-two-gpu "
            "state legitimately crashes with 'requestGpuComparison is not "
            "defined' and unmounts the app — this is the pre-existing Phase F "
            "defect that G5 fixes, reproduced by the capture flow itself. "
            "Any 'FAILED' desktop-1440 entries on the before side record that "
            "crash, not a harness error. The after side must show the table "
            "with zero console errors."
        ) if label == "before" else None,
        "states": [
            "catalog-default", "catalog-gpu", "catalog-row-hover",
            "catalog-row-focus", "build-empty", "detail-cpu", "build-cpu",
            "build-cpu-gpu", "compare-empty", "compare-one",
            "compare-two-cpu", "compare-two-gpu", "mobile-320 spot-check",
        ],
        "shots": results,
    }
    (outdir / f"{label}--manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    shots = len([r for r in results if not str(r["shot"]).endswith("FAILED")])
    total_errs = sum(len(r.get("errors", [])) for r in results)
    overflows = [
        r["shot"] for r in results
        if r.get("metrics", {}).get("horizontalOverflow")
        or r.get("metrics", {}).get("cardOverflowCount")
    ]
    print(f"done: {shots} shots, {total_errs} console errors, "
          f"{len(overflows)} overflow shots")
    if overflows:
        print("OVERFLOW SHOTS:", overflows)
    if total_errs:
        print("CONSOLE ERRORS PRESENT — required: 0")
    # The before capture is expected to report the baseline compare-two-gpu
    # crash (see known_baseline_failure); only the after capture gates on
    # zero console errors.
    expected_before_failure = label == "before" and shots >= 34
    return 0 if (shots and not overflows
                 and (not total_errs or expected_before_failure)) else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
