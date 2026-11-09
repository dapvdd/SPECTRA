"""G5 audit probe: computed font-size/letter-spacing of micro-labels, both themes."""

import json
import sys

from playwright.sync_api import sync_playwright

JS = """() => {
  const probes = [
    ['build-chat-context-label', '.build-chat-context-label'],
    ['build-chat-analysis-title', '.build-chat-analysis-title'],
    ['comparison-overview-slot', '.comparison-overview-slot'],
    ['decision-fact dt', '.decision-fact dt'],
    ['build-intelligence-fact dt', '.build-intelligence-fact dt'],
    ['comparison-header::before', '.comparison-header span::before'],
    ['filter-group-label', '.filter-group-label'],
    ['eyebrow', '.hero .eyebrow'],
    ['detail-section-label', '.detail-section-label'],
    ['build-summary-label', '.build-summary-label'],
    ['hardware-card-kicker', '.hardware-card-kicker'],
  ];
  const out = [];
  for (const [name, sel] of probes) {
    const el = document.querySelector(sel);
    if (!el) { out.push({name, missing: true}); continue; }
    const cs = getComputedStyle(el);
    out.push({name, fs: cs.fontSize, ls: cs.letterSpacing,
              transform: cs.textTransform, family: cs.fontFamily.slice(0, 30)});
  }
  return out;
}"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    report = {}
    for theme in ("dark", "light"):
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script(
            "try { localStorage.setItem('spectra-theme', '%s'); } catch (e) {}" % theme
        )
        page = ctx.new_page()
        page.goto("http://localhost:5173/", wait_until="domcontentloaded")
        page.wait_for_selector(".hardware-card", timeout=20000)
        page.wait_for_timeout(800)
        report[theme] = {"catalog": page.evaluate(JS)}

        # build page
        page.goto("http://localhost:5173/build", wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        report[theme]["build"] = page.evaluate(JS)
        ctx.close()
    browser.close()

report_path = "docs/design/evidence/phase-g/g5_typography_probe.json"
import os
os.makedirs(os.path.dirname(report_path), exist_ok=True)
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=1)
print("saved", report_path)

issues = []
for theme in report:
    for screen in ("catalog", "build"):
        for row in report[theme][screen]:
            if row.get("missing"):
                continue
            fs = row["fs"]
            ls = float(row["ls"].replace("px", ""))
            # 2xs floor = 0.6875rem = 11px; eyebrows/section labels are exempt
            exempt = row["name"] in ("eyebrow", "detail-section-label",
                                     "build-summary-label", "hardware-card-kicker")
            if exempt:
                continue
            if fs not in ("11px",) or ls > 1.6:
                issues.append((theme, screen, row))
print("ISSUES:", json.dumps(issues, indent=1) if issues else "none")
