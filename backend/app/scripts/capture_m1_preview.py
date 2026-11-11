"""Capture M1 preview screenshots: catalog with new type filters + RAM detail.

Read-only against the running preview (backend :8000, frontend :4173).
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(r"C:\Users\user\spectra-local\.worktrees\build-planner-m1\docs\design\evidence\m1-preview")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:4173"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # --- 1. Catalog page, light + dark ---
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(800)

    # Discover filter buttons and their labels
    buttons = page.locator("button").all_inner_texts()
    print("buttons:", [b for b in buttons if b.strip()][:24])

    page.screenshot(path=str(OUT / "01-catalog-initial.png"), full_page=False)

    # --- 2. Click RAM filter if present ---
    ram_btn = page.get_by_role("button", name=re.compile(r"^RAM$", re.I))
    if ram_btn.count() == 0:
        # maybe a select element
        selects = page.locator("select").all()
        print("selects found:", len(selects))
    if ram_btn.count() > 0:
        ram_btn.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "02-catalog-ram-filter.png"), full_page=False)
        rows = page.locator("table tbody tr, [role=row], li").count()
        print("ram rows visible:", rows)

    # --- 3. Open first RAM item detail via its card button ---
    try:
        card_btn = page.locator("button.hardware-card-main").first
        card_btn.click(timeout=10000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / "03-ram-detail.png"), full_page=False)
        print("detail heading:", page.locator("h1, h2").first.inner_text())
    except Exception as exc:
        print("detail nav skipped:", exc)

    # --- 4. Dark theme on catalog RAM ---
    page.go_back(wait_until="networkidle")
    page.wait_for_timeout(500)
    theme_btn = page.get_by_role("button", name=re.compile(r"dark|theme|toggle", re.I))
    if theme_btn.count() > 0:
        theme_btn.first.click()
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "04-catalog-ram-dark.png"), full_page=False)

    browser.close()

print("saved to", OUT)
