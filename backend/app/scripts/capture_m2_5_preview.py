"""Capture M2.5 preview evidence: unified six-slot Build Planner.

Read-only against a disposable local preview (backend :8010 with a temp DB
seeded by seed_m2_5_preview.py, frontend :4180 serving the built dist with
VITE_API_BASE_URL=http://127.0.0.1:8010). Production and the M2 staging
containers/DB are never contacted.

The reviewing model cannot read PNG pixels, so every visual claim is backed by
a DOM assertion (check(...)); the same assertions are written to
dom-checks.json next to the screenshots.

Usage: run the seed script first, start the backend on :8010 with
SPECTRA_DATABASE_URL pointing at the seeded DB, serve the built frontend on
:4180, then run this script from the repository root (PYTHONPATH includes
the root).
"""

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Output lands in the M2.5 evidence folder of the checkout this script is run
# from (resolved relative to the script location, so it works from any
# checkout/worktree with the same layout).
_REPO_ROOT = Path(__file__).resolve().parents[3]
OUT = _REPO_ROOT / "docs" / "design" / "evidence" / "m2-5"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:4180"
API = "http://127.0.0.1:8010"

CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append({"label": label, "ok": bool(condition), "detail": str(detail)})
    print(("PASS " if condition else "FAIL ") + label + (f"  [{detail}]" if detail else ""))


def wait_for(url, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(1)
    return False


def scroll_to(page, selector):
    page.locator(selector).scroll_into_view_if_needed()
    page.wait_for_timeout(400)


def slot_card(page, htype):
    return page.locator(f'.build-component-card[aria-labelledby="build-slot-{htype}"]')


def slot_select_button(page, htype):
    card = slot_card(page, htype)
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
    page.wait_for_timeout(700)
    return True


def search_and_open(page, name):
    search = page.locator("input[type=search], input[placeholder*='earch' i]").first
    if search.count() == 0:
        check(f"search input for {name}", False)
        return False
    search.fill(name)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(900)

    card = page.locator("button.hardware-card-main", has_text=name).first
    if card.count() == 0:
        check(f"card {name}", False)
        return False
    card.click(timeout=15000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)
    return True


def close_detail_if_open(page):
    back = page.get_by_role("button", name=re.compile(r"Back to", re.I))
    if back.count():
        back.first.click()
        page.wait_for_timeout(500)


def add_component(page, htype, name):
    if not open_catalog_for(page, htype):
        return
    close_detail_if_open(page)
    if not search_and_open(page, name):
        return
    add_btn = page.get_by_role(
        "button", name=re.compile(rf"Add to Build|Change {htype}", re.I)
    )
    if add_btn.count() == 0:
        check(f"add button {htype}", False)
        return
    add_btn.first.click()
    page.wait_for_timeout(500)
    check(f"added {htype} ({name})", True)
    close_detail_if_open(page)


def fill_build(page, components):
    for htype, name in components:
        add_component(page, htype, name)


def compat_chip_text(page):
    chip = page.locator(".build-compatibility .performance-status").first
    return chip.inner_text() if chip.count() else ""


BUILD_A = [
    ("CPU", "PREVIEW M25 Core i5-14600K"),
    ("GPU", "PREVIEW M25 RTX 4070"),
    ("RAM", "PREVIEW M25 Vengeance DDR5 32GB"),
    ("STORAGE", "PREVIEW M25 980 Pro 1TB"),
    ("MOTHERBOARD", "PREVIEW M25 Pro Z690-A"),
    ("PSU", "PREVIEW M25 RM850x"),
]
BUILD_B = [
    ("CPU", "PREVIEW M25 Ryzen 7 5800X"),
    ("GPU", "PREVIEW M25 RX 7900 XTX"),
    ("RAM", "PREVIEW M25 Vengeance LPX DDR4 16GB"),
    ("STORAGE", "PREVIEW M25 Barracuda 2TB HDD"),
    ("MOTHERBOARD", "PREVIEW M25 Pro Z690-A (B)"),
    ("PSU", "PREVIEW M25 CV450"),
]
BUILD_C = [
    ("CPU", "PREVIEW M25 Core i9-13900K partial"),
    ("GPU", "PREVIEW M25 RTX 4080 partial"),
    ("RAM", "PREVIEW M25 Fury DDR5 64GB partial"),
    ("STORAGE", "PREVIEW M25 870 EVO 2TB"),
    ("MOTHERBOARD", "PREVIEW M25 X670-E partial"),
    ("PSU", "PREVIEW M25 RM1000x"),
]

assert wait_for(f"{API}/health"), "backend did not become healthy"
assert wait_for(BASE), "frontend preview did not become reachable"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # --- 1. Empty planner (light) ----------------------------------------
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / "01-landing-light.png"))

    scroll_to(page, "#build")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "02-build-planner-six-slots-empty-light.png"))
    check("six slot cards present", page.locator(".build-component-card").count() == 6)

    chip_empty = compat_chip_text(page)
    note_empty = page.locator(".build-compatibility-note").inner_text()
    check("empty build: compatibility is unknown", chip_empty.strip() == "Compatibility unknown", chip_empty)
    check("empty build: note counts 0 of 6 slots", "0 of 6 slots filled" in note_empty)
    check("empty build: no rule results (no POST)", page.locator(".build-compatibility-rule").count() == 0)
    scroll_to(page, ".build-compatibility")
    page.screenshot(path=str(OUT / "03-compatibility-empty-light.png"))

    # --- 2. Build A: every determinable rule compatible -------------------
    fill_build(page, BUILD_A)
    page.wait_for_timeout(1600)
    scroll_to(page, "#build")
    page.screenshot(path=str(OUT / "04-build-full-compatible-light.png"))

    chip_a = compat_chip_text(page)
    check("build A chip is Compatibility unknown", chip_a.strip() == "Compatibility unknown", chip_a)
    rules_a = page.locator(".build-compatibility-rule").all_inner_texts()
    check("build A shows 7 rules", len(rules_a) == 7, str(len(rules_a)))
    # M2.5 power semantics: a PSU at/above the TDP reference is UNKNOWN
    # (advisory, non-authoritative), never COMPATIBLE. The GPU-slot rule is
    # always UNKNOWN (no stored PCIe generation). So build A is 5 compatible
    # + 2 unknown, aggregate UNKNOWN.
    check(
        "build A: 5 compatible, PSU and GPU-slot rules unknown",
        sum("Compatible" in r for r in rules_a) == 5
        and sum("unknown" in r.lower() for r in rules_a) == 2
        and any("gpu-motherboard-slot" in r for r in rules_a)
        and any("psu-build-wattage" in r for r in rules_a),
        f"compatible={sum('Compatible' in r for r in rules_a)} unknown={sum('unknown' in r.lower() for r in rules_a)}",
    )
    body_a = page.locator(".build-compatibility").inner_text().lower()
    check("build A copy avoids 'draw' / 'covers'", "draw" not in body_a and "covers" not in body_a)
    check("build A copy marks PSU estimate non-authoritative", "non-authoritative" in body_a)
    scroll_to(page, ".build-compatibility")
    page.screenshot(path=str(OUT / "05-compatibility-compatible-light.png"))

    # --- 3. Build B: incompatible -----------------------------------------
    fill_build(page, BUILD_B)
    page.wait_for_timeout(1600)
    chip_b = compat_chip_text(page)
    check("build B chip is Incompatible", chip_b.strip() == "Incompatible", chip_b)
    body_b = page.locator(".build-compatibility").inner_text()
    check("build B names socket mismatch", "AM4" in body_b and "FCLGA1700" in body_b)
    check("build B names PSU shortfall", "wattage" in body_b.lower())
    check("build B never claims ready", "ready to build" not in body_b.lower() and "ready to use" not in body_b.lower())
    scroll_to(page, ".build-compatibility")
    page.screenshot(path=str(OUT / "06-compatibility-incompatible-light.png"))

    # --- 4. Build C: unknown-heavy ----------------------------------------
    fill_build(page, BUILD_C)
    page.wait_for_timeout(1600)
    chip_c = compat_chip_text(page)
    check("build C chip is Compatibility unknown", chip_c.strip() == "Compatibility unknown", chip_c)
    body_c = page.locator(".build-compatibility").inner_text()
    check("build C reports Missing lines", "Missing:" in body_c)
    scroll_to(page, ".build-compatibility")
    page.screenshot(path=str(OUT / "07-compatibility-unknown-light.png"))

    # --- 5. Reading order (Task 7 hierarchy) ------------------------------
    order_selectors = [
        (".build-head", "overview"),
        (".build-compatibility", "compatibility"),
        (".build-configuration", "configuration"),
        (".build-facts", "detail"),
        (".build-column-intelligence", "intelligence"),
        (".build-conversation", "assistant"),
    ]
    # Absolute document offsets, so the order check does not depend on the
    # current scroll position.
    tops = page.evaluate(
        "sels => sels.map(s => { const el = document.querySelector(s);"
        " return el ? Math.round(el.getBoundingClientRect().top + window.scrollY) : -1; })",
        [selector for selector, _ in order_selectors],
    )
    check(
        "build sections read in the documented order",
        all(t >= 0 for t in tops) and tops == sorted(tops),
        str(tops),
    )
    check("dissolved wrappers absent", page.locator(".build-workspace, .build-lower").count() == 0)
    page.screenshot(path=str(OUT / "08-build-reading-order-light.png"), full_page=True)

    # --- 6. Six-slot detail views -----------------------------------------
    for htype, name, shot in (
        ("RAM", "PREVIEW M25 Vengeance DDR5 32GB", "09-detail-ram-light.png"),
        ("MOTHERBOARD", "PREVIEW M25 Pro Z690-A", "10-detail-motherboard-light.png"),
        ("STORAGE", "PREVIEW M25 980 Pro 1TB", "11-detail-storage-light.png"),
        ("PSU", "PREVIEW M25 RM850x", "12-detail-psu-light.png"),
    ):
        if not open_catalog_for(page, htype):
            continue
        if not search_and_open(page, name):
            continue
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / shot))
        detail_text = page.locator(".hardware-detail").inner_text()
        check(
            f"{htype} detail free of CPU-only fields",
            "Cores" not in detail_text and "Threads" not in detail_text,
        )
        close_detail_if_open(page)

    # --- 7. Mobile ---------------------------------------------------------
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(800)
    scroll_to(page, "#build")
    page.screenshot(path=str(OUT / "13-build-mobile-390.png"))
    check("mobile: six slot cards", page.locator(".build-component-card").count() == 6)
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check("mobile: no horizontal overflow", overflow <= 1, f"overflow={overflow}px")
    page.screenshot(path=str(OUT / "14-build-mobile-390-full.png"), full_page=True)

    # --- 8. Dark theme -----------------------------------------------------
    # The theme control is a segmented group (System / Dark / Light); the
    # explicit "Dark theme" button is the only reliable way to force dark.
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(700)
    dark_btn = page.get_by_role("button", name="Dark theme")
    check("dark theme control present", dark_btn.count() == 1, str(dark_btn.count()))
    if dark_btn.count():
        dark_btn.first.click()
        page.wait_for_timeout(800)
    resolved = page.evaluate("document.documentElement.dataset.theme")
    check("dark theme applied to document", resolved == "dark", str(resolved))
    scroll_to(page, "#build")
    page.screenshot(path=str(OUT / "15-build-planner-dark.png"))

    browser.close()

fails = [c["label"] for c in CHECKS if not c["ok"]]
summary = {
    "base": BASE,
    "api": API,
    "checks": CHECKS,
    "passed": len(CHECKS) - len(fails),
    "total": len(CHECKS),
    "failed": fails,
}
(OUT / "dom-checks.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

print(f"\nDOM checks: {len(CHECKS) - len(fails)}/{len(CHECKS)} passed")
if fails:
    print("FAILED:", fails)
print("saved to", OUT)
sys.exit(1 if fails else 0)
