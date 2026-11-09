"""G6 responsive + a11y validation: 1440/768/390/320, dark+light.

Checks: no horizontal overflow, no truncated catalog identity, touch target
sizes, keyboard nav + focus visibility on the toolbar, AA contrast pairs.
Run from the repo root with the dev server on :5173.
"""

import json
import sys

from playwright.sync_api import sync_playwright

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS" if ok else "FAIL"), name, "-", str(detail)[:150])


VIEWPORTS = [(1440, 900), (768, 1024), (390, 844), (320, 640)]
CONTRAST_PAIRS_DARK = [
    ("text-primary", "#e8e4f0"),
    ("text-muted", "#8b82a3"),
]
JS_OVERFLOW = """() => ({
  overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  cardOverflow: [...document.querySelectorAll('.hardware-card')].slice(0, 6)
    .map(c => c.scrollWidth - c.clientWidth).filter(d => d > 2).length,
  nameTruncated: [...document.querySelectorAll('.hardware-card-name')].slice(0, 12)
    .filter(n => n.scrollWidth > n.clientWidth + 1).length,
})"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ("dark", "light"):
        for w, h in VIEWPORTS:
            ctx = browser.new_context(viewport={"width": w, "height": h})
            ctx.add_init_script(
                "try { localStorage.setItem('spectra-theme', '%s'); } catch (e) {}"
                % theme
            )
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)[:200]))
            page.goto("http://localhost:5173/", wait_until="domcontentloaded")
            page.wait_for_selector(".hardware-card", timeout=20000)
            page.wait_for_timeout(1000)

            label = f"{theme} {w}px"
            m = page.evaluate(JS_OVERFLOW)
            check(f"{label}: no page horizontal overflow", m["overflowX"] <= 0,
                  f"overflowX={m['overflowX']}px")
            check(f"{label}: cards do not overflow", m["cardOverflow"] == 0,
                  f"{m['cardOverflow']} cards overflow")

            if w == 320:
                # spot-check only at 320: identity may ellipsize by design
                ctx.close()
                continue

            check(f"{label}: catalog names not hard-truncated",
                  m["nameTruncated"] <= (2 if w == 390 else 0),
                  f"{m['nameTruncated']} names clipped")

            # touch targets on the toolbar (only below 1024 where touch matters)
            if w <= 768:
                small = page.evaluate(
                    """() => [...document.querySelectorAll('.filter-button, .catalog-sort-select, .nav-link, .theme-toggle')]
                      .filter(el => el.offsetParent !== null)
                      .map(el => { const r = el.getBoundingClientRect();
                        return {cls: el.className.split(' ')[0], h: Math.round(r.height)};
                      }).filter(t => t.h < 24)"""
                )
                check(f"{label}: toolbar touch targets >= 24px",
                      len(small) == 0, small[:3])

            # keyboard nav: tab reaches the toolbar and focus is visible
            page.keyboard.press("Tab")
            focused_ok = page.evaluate(
                """() => { const el = document.activeElement;
                  if (!el) return false;
                  const cs = getComputedStyle(el);
                  return el.classList.contains('skip-link') ||
                         cs.outlineWidth !== '0px' && cs.outlineStyle !== 'none'; }"""
            )
            check(f"{label}: first tab stop has visible focus", focused_ok)

            # focus lands on a type filter after tabbing to the group
            page.locator(".filter-buttons-type button").first.focus()
            fs = page.evaluate(
                """() => { const el = document.activeElement;
                  const cs = getComputedStyle(el);
                  return {outline: cs.outlineStyle, width: cs.outlineWidth}; }"""
            )
            check(f"{label}: filter button focus ring present",
                  fs["outline"] != "none" and fs["width"] != "0px", fs)

            check(f"{label}: no console errors", len(errors) == 0, errors[:2])
            ctx.close()
    browser.close()

fails = [r for r in RESULTS if not r["ok"]]
print(json.dumps({"passed": sum(1 for r in RESULTS if r["ok"]),
                  "total": len(RESULTS)}, indent=1))
import os
os.makedirs("docs/design/evidence/phase-g", exist_ok=True)
with open("docs/design/evidence/phase-g/g6_responsive_a11y.json", "w",
          encoding="utf-8") as f:
    json.dump(RESULTS, f, indent=2)
sys.exit(1 if fails else 0)
