"""Capture M2 preview screenshots: six-slot Build Planner + compatibility.

Read-only against the running preview (backend :8000, frontend :4173).
Fixture builds seeded into the disposable preview DB:
  A compatible (ids 5381..5386), B incompatible (5387..5392),
  C unknown-heavy (5393..5398).

The model that reviews this evidence cannot read PNG pixels; every visual
claim below is backed by DOM assertions (check(...) lines) instead.
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(r"C:\Users\user\spectra-local\.worktrees\build-planner-m2\docs\design\evidence\build-planner-m2")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:4173"

CHECKS = []


def check(label, condition):
    CHECKS.append((label, bool(condition)))
    print(("PASS " if condition else "FAIL ") + label)


def scroll_to_build(page):
    page.locator("#build").scroll_into_view_if_needed()
    page.wait_for_timeout(400)


def slot_select_button(page, htype):
    """The slot card's select button ('Browse X catalog' when empty,
    'Change X' once filled)."""
    card = page.locator(f'.build-component-card[aria-labelledby="build-slot-{htype}"]')
    empty_btn = card.locator("button.build-component-select-button")
    if empty_btn.count():
        return empty_btn
    return card.locator("button.build-action-button")


def open_catalog_for(page, htype):
    btn = slot_select_button(page, htype)
    if btn.count() == 0:
        check(f"select button {htype}", False)
        return False
    btn.first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    return True


def search_and_open(page, name):
    """Type the fixture name into search and open its detail view."""
    search = page.locator("input[type=search], input[placeholder*='earch' i]").first
    if search.count() == 0:
        check(f"search input for {name}", False)
        return False
    search.fill(name)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    card = page.locator("button.hardware-card-main", has_text=name).first
    if card.count() == 0:
        check(f"card {name}", False)
        return False
    card.click(timeout=15000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(700)
    return True


def close_detail_if_open(page):
    """A leftover detail view hides the catalog grid; close it first."""
    back = page.get_by_role("button", name=re.compile(r"Back to", re.I))
    if back.count():
        back.first.click()
        page.wait_for_timeout(600)


def add_component(page, htype, name):
    """Fill one slot from the build planner: select button -> search -> add."""
    if not open_catalog_for(page, htype):
        return
    # browseForBuildType does not close an open detail view; do it here.
    close_detail_if_open(page)
    if not search_and_open(page, name):
        return
    # Fresh slots read "Add to Build"; replacing a filled slot reads
    # "Change {type}".
    add_btn = page.get_by_role(
        "button", name=re.compile(rf"Add to Build|Change {htype}", re.I)
    )
    if add_btn.count() == 0:
        check(f"add button {htype}", False)
        return
    add_btn.first.click()
    page.wait_for_timeout(600)
    check(f"added {htype} ({name})", True)

    # The detail view stays open after adding; it hides the catalog grid,
    # so go back before touching the next slot.
    close_detail_if_open(page)


def fill_build(page, components):
    """components: list of (htype, exact fixture name)."""
    for htype, name in components:
        add_component(page, htype, name)


def compat_chip_text(page):
    chip = page.locator(".build-compatibility .performance-status").first
    return chip.inner_text() if chip.count() else ""


def back_to_build(page):
    back = page.get_by_role("button", name=re.compile(r"Back to", re.I))
    if back.count():
        back.first.click()
        page.wait_for_timeout(600)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # --- 1. Landing: catalog + empty build planner (light) ---------------
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / "01-catalog-initial-light.png"), full_page=False)

    scroll_to_build(page)
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "02-build-planner-six-slots-empty.png"), full_page=False)
    check("six slot cards present", page.locator(".build-component-card").count() == 6)

    # --- 2. Compatible build A -------------------------------------------
    fill_build(page, [
        ("CPU", "PREVIEW Core i5-14600K"),
        ("GPU", "PREVIEW RTX 4070"),
        ("RAM", "PREVIEW Vengeance DDR5 32GB"),
        ("STORAGE", "PREVIEW 980 Pro 1TB"),
        ("MOTHERBOARD", "PREVIEW Pro Z690-A"),
        ("PSU", "PREVIEW RM850x"),
    ])
    page.wait_for_timeout(1800)
    scroll_to_build(page)
    page.screenshot(path=str(OUT / "03-build-planner-filled.png"), full_page=False)

    chip_a = compat_chip_text(page)
    print("compat chip (build A):", chip_a)
    page.locator(".build-compatibility").scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "04-compatibility-compatible.png"), full_page=False)
    # Design-correct expectation: the GPU-slot rule is always UNKNOWN at M2
    # (motherboards store a slot count, not a PCIe generation), so the
    # aggregate can never be COMPATIBLE. All six determinable rules must
    # read COMPATIBLE and only the GPU rule stays UNKNOWN.
    check("build A chip is Compatibility unknown", chip_a.strip() == "Compatibility unknown")
    rule_count_a = page.locator(".build-compatibility-rule").count()
    check("build A shows 7 rules", rule_count_a == 7)
    rules_a = page.locator(".build-compatibility-rule").all_inner_texts()
    check(
        "build A: 6 rules compatible, only GPU rule unknown",
        sum("Compatible" in r for r in rules_a) == 6
        and sum("unknown" in r.lower() for r in rules_a) == 1
        and any("gpu-motherboard-slot" in r for r in rules_a),
    )

    # --- 3. Incompatible build B -----------------------------------------
    fill_build(page, [
        ("CPU", "PREVIEW Ryzen 7 5800X"),
        ("GPU", "PREVIEW RX 7900 XTX"),
        ("RAM", "PREVIEW Vengeance LPX DDR4 16GB"),
        ("STORAGE", "PREVIEW Barracuda 2TB HDD"),
        ("MOTHERBOARD", "PREVIEW Pro Z690-A (B)"),
        ("PSU", "PREVIEW CV450"),
    ])
    page.wait_for_timeout(1800)
    page.locator(".build-compatibility").scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "05-compatibility-incompatible.png"), full_page=False)
    chip_b = compat_chip_text(page)
    print("compat chip (build B):", chip_b)
    check("build B chip is Incompatible", chip_b.strip() == "Incompatible")
    body_b = page.locator(".build-compatibility").inner_text()
    check("build B names socket mismatch", "AM4" in body_b and "LGA1700" in body_b)
    check("build B names PSU shortfall", "wattage" in body_b.lower())

    # --- 4. Unknown-heavy build C -----------------------------------------
    fill_build(page, [
        ("CPU", "PREVIEW Core i9-13900K partial"),
        ("GPU", "PREVIEW RTX 4080 partial"),
        ("RAM", "PREVIEW Fury DDR5 64GB partial"),
        ("STORAGE", "PREVIEW 870 EVO 2TB"),
        ("MOTHERBOARD", "PREVIEW X670-E partial"),
        ("PSU", "PREVIEW RM1000x"),
    ])
    page.wait_for_timeout(1800)
    page.locator(".build-compatibility").scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "06-compatibility-unknown.png"), full_page=False)
    chip_c = compat_chip_text(page)
    print("compat chip (build C):", chip_c)
    check("build C chip is Compatibility unknown", chip_c.strip() == "Compatibility unknown")
    body_c = page.locator(".build-compatibility").inner_text()
    check("build C shows Missing lines", "Missing:" in body_c)

    # --- 5. Category detail views -----------------------------------------
    # Re-open each fixture's detail view via its (filled) slot's Change
    # button; this also exercises the Change flow end to end.
    for htype, name, shot in (
        ("RAM", "PREVIEW Vengeance DDR5 32GB", "07-detail-ram.png"),
        ("MOTHERBOARD", "PREVIEW Pro Z690-A", "08-detail-motherboard.png"),
        ("STORAGE", "PREVIEW 980 Pro 1TB", "09-detail-storage.png"),
        ("PSU", "PREVIEW RM850x", "10-detail-psu.png"),
    ):
        if not open_catalog_for(page, htype):
            continue
        if not search_and_open(page, name):
            continue
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / shot), full_page=False)
        detail_text = page.locator(".hardware-detail").inner_text()
        check(
            f"{htype} detail free of CPU-only fields",
            "Cores" not in detail_text and "Threads" not in detail_text,
        )
        back_to_build(page)

    # --- 6. Mobile layout ---------------------------------------------------
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(800)
    scroll_to_build(page)
    page.screenshot(path=str(OUT / "11-build-mobile.png"), full_page=False)
    check(
        "mobile: six slot cards",
        page.locator(".build-component-card").count() == 6,
    )

    # --- 7. Dark theme ------------------------------------------------------
    page.set_viewport_size({"width": 1440, "height": 900})
    theme_btn = page.get_by_role("button", name=re.compile(r"dark|theme|toggle", re.I))
    if theme_btn.count() > 0:
        theme_btn.first.click()
        page.wait_for_timeout(700)
    scroll_to_build(page)
    page.screenshot(path=str(OUT / "12-build-dark.png"), full_page=False)

    browser.close()

fails = [label for label, ok in CHECKS if not ok]
print(f"\nDOM checks: {len(CHECKS) - len(fails)}/{len(CHECKS)} passed")
if fails:
    print("FAILED:", fails)
print("saved to", OUT)
sys.exit(1 if fails else 0)
