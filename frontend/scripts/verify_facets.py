"""Verify hero quick-path counts stay stable across type filter changes."""

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
    page.wait_for_timeout(1500)

    def read_counts():
        return page.evaluate(
            """() => [...document.querySelectorAll('.hero-quick-path')].map(a => ({
                 label: a.querySelector('.hero-quick-path-class')?.textContent,
                 count: a.querySelector('.hero-quick-path-count')?.textContent,
               }))"""
        )

    results = {"initial": read_counts()}
    page.click(".filter-buttons-type button:has-text('GPU')")
    page.wait_for_timeout(1500)
    results["gpu_active"] = read_counts()
    page.click(".filter-buttons-type button:has-text('CPU')")
    page.wait_for_timeout(1500)
    results["cpu_active"] = read_counts()
    page.click(".filter-buttons-type button:has-text('All hardware')")
    page.wait_for_timeout(1500)
    results["back_to_all"] = read_counts()

    print(json.dumps(results, indent=2))

    ok = all(
        all(v["count"] for v in state) for state in results.values()
    )
    print("STABLE" if ok else "STILL VANISHING")
    ctx.close()
    browser.close()
