"""M4 browser acceptance (Task 9/10 of the plan): drive the real UI against
a real backend serving the M3.3 snapshot copy.

Checks (evidence-gated expectations, matching the mission's no-fabrication
constraints):
  1. App root renders; primary nav present.
  2. Explore: hardware cards exist; open a CPU detail view.
  3. Detail: Scenario ratings panel renders; gaming stars > 0 for a
     benchmarked CPU; VALUE shows UNKNOWN text (no price data).
  4. Build: pick a CPU; Build Intelligence panel appears with
     M4-BUILD-v1.0 version tag, balance/power/compatibility cards.
  5. UNKNOWN-first rendering: unknown balance / missing slots are named,
    never papered over.

Writes PASS/FAIL lines to stdout; exit code 0 iff all checks pass.
"""
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

FRONTEND = "http://localhost:5173"
OUT = Path(__file__).parent / "m4_acceptance_out"
OUT.mkdir(exist_ok=True)

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, "PASS", ""))
    except Exception as exc:  # noqa: BLE001
        results.append((name, "FAIL", str(exc)[:300]))


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        errors = []
        page.on(
            "console",
            lambda msg: errors.append(msg.text) if msg.type == "error" else None,
        )

        # -- 1. app root + nav -------------------------------------------------
        page.goto(FRONTEND, wait_until="networkidle")
        check("app_renders", lambda: (_ for _ in ()).throw(
            AssertionError("main content missing")
        ) if not page.locator("main, #main-content, #build").count() else None)
        check("nav_present", lambda: (_ for _ in ()).throw(
            AssertionError("nav links missing")
        ) if page.locator(".nav-link").count() < 3 else None)

        # -- 2. explore: open a CPU detail ------------------------------------
        card = page.locator(".hardware-card").first
        check("explore_cards", lambda: (_ for _ in ()).throw(
            AssertionError("no hardware cards in explore view")
        ) if not card.count() else None)
        card.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)

        # -- 3. detail: scenario ratings panel --------------------------------
        ratings = page.locator(".scenario-ratings")
        ratings.wait_for(state="visible", timeout=8000)
        check("scenario_panel_visible", lambda: None)
        check(
            "gaming_stars_positive",
            lambda: (_ for _ in ()).throw(
                AssertionError(
                    f"gaming score text: "
                    f"{ratings.locator('.scenario-rating-score').first.inner_text()}"
                )
            )
            if ratings.locator(".scenario-rating-card").first.locator(
                ".scenario-rating-score"
            ).inner_text().strip() in ("", "0", "0.0") else None,
        )
        body_txt = ratings.inner_text()
        check(
            "value_unknown_rendered",
            lambda: (_ for _ in ()).throw(
                AssertionError("value UNKNOWN not visible in scenario panel")
            )
            if not (
                "unknown" in body_txt.lower() and "price" in body_txt.lower()
            )
            else None,
        )

        # screenshot for the record
        page.screenshot(path=str(OUT / "detail_scenario_ratings.png"), full_page=False)

        # -- 4. build view: add CPU -> build intelligence panel ---------------
        add_btn = page.locator(".detail-build-button")
        add_btn.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)

        panel = page.locator(".build-intelligence-panel")
        panel.wait_for(state="visible", timeout=8000)
        check("build_intelligence_panel_visible", lambda: None)
        check(
            "build_intelligence_version_shown",
            lambda: (_ for _ in ()).throw(
                AssertionError(
                    f"version text: {page.locator('.build-intelligence-version').inner_text()}"
                )
            )
            if "M4-BUILD" not in page.locator(
                ".build-intelligence-version"
            ).inner_text() else None,
        )
        for label in ("Balance", "Power reference", "Compatibility"):
            check(
                f"panel_card_{label.split()[0].lower()}",
                lambda lbl=label: (_ for _ in ()).throw(
                    AssertionError(f"card '{lbl}' missing")
                )
                if panel.locator(f'h4:has-text("{lbl}")').count() == 0
                else None,
            )
        body = panel.inner_text()
        check(
            "panel_names_missing_slots_or_unknown",
            lambda: None
            if ("unknown" in body.lower() or "missing" in body.lower())
            else (_ for _ in ()).throw(
                AssertionError(
                    "panel hides gaps; neither 'unknown' nor 'missing' visible"
                )
            ),
        )

        page.screenshot(path=str(OUT / "build_intelligence_panel.png"), full_page=False)

        # -- 5. console errors (ignoring known-benign 4xx/5xx fetch noise) -----
        real_errors = [
            e for e in errors
            if "Failed to load" not in e and "404" not in e and "400" not in e
        ]
        check(
            "no_unexpected_console_errors",
            lambda: (_ for _ in ()).throw(AssertionError("; ".join(real_errors[:3])))
            if real_errors else None,
        )

        browser.close()


run()

failed = [r for r in results if r[1] == "FAIL"]
for name, status, detail in results:
    line = f"{status}  {name}" + (f"  — {detail}" if detail else "")
    print(line)

sys.exit(1 if failed else 0)
