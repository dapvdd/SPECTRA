"""G5 verification: comparison kicker follows type; readout copy is de-duped."""

import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(
        "try { localStorage.setItem('spectra-theme', 'dark'); } catch (e) {}"
    )
    page = ctx.new_page()
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.wait_for_timeout(1200)

    out = {}

    # 1. Comparison type kickers (GPU comparison after picking two GPUs)
    out["readout_meta_all"] = page.locator(".catalog-readout-meta").inner_text()
    out["section_head_meta"] = page.locator(".section-head-meta").inner_text()
    out["sort_label"] = page.locator(".catalog-sort-label").inner_text()

    page.locator(".filter-buttons-type button", has_text="GPU").click()
    page.wait_for_timeout(1200)
    out["readout_meta_gpu"] = page.locator(".catalog-readout-meta").inner_text()

    # add two GPUs to compare
    for i in range(2):
        page.locator(".compare-button[aria-pressed='false']:not([disabled])").first.click()
        page.wait_for_timeout(400)
    page.wait_for_selector(".comparison-table", timeout=20000)
    page.wait_for_timeout(600)
    out["comparison_kickers"] = page.evaluate(
        """() => [...document.querySelectorAll('.comparison-header-type')].map(e => e.textContent)"""
    )
    out["comparison_names"] = page.evaluate(
        """() => [...document.querySelectorAll('.comparison-header span:not(.comparison-header-type)')].slice(0,2).map(e => e.textContent)"""
    )

    # manufacturer filter meta
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.wait_for_timeout(1000)
    page.locator(".filter-buttons button", has_text="AMD").first.click()
    page.wait_for_timeout(1200)
    out["readout_meta_amd"] = page.locator(".catalog-readout-meta").inner_text()

    print(json.dumps(out, indent=1))
    ok = (
        out["comparison_kickers"] == ["GPU", "GPU"]
        and "ALL MANUFACTURERS" not in out["readout_meta_all"].upper()
        and "AMD" in out["readout_meta_amd"].upper()
        and out["sort_label"].strip().upper() == "SORT"
        and out["section_head_meta"].strip().upper() in ("LIVE", "UPDATING")
    )
    print("G5-VERIFIED" if ok else "G5-FAILED")
    ctx.close()
    browser.close()
