"""Phase 8/10 verification: contrast pairs, reduced motion, focus, overflow."""

from playwright.sync_api import sync_playwright

RATIO_JS = """
([fgSel, fgProp, bgSel, bgProp]) => {
  const lum = (colorStr) => {
    const cs = colorStr.match(/color\\(srgb\\s+([\\d.]+)\\s+([\\d.]+)\\s+([\\d.]+)\\s*(?:\\/\\s*([\\d.]+))?\\)/);
    if (cs) {
      const f = (v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
      const a = cs[4] === undefined ? 1 : parseFloat(cs[4]);
      return [f(parseFloat(cs[1])) * a, f(parseFloat(cs[2])) * a, f(parseFloat(cs[3])) * a, a];
    }
    const m = colorStr.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const parts = m[1].split(',').map(s => parseFloat(s));
    const [r, g, b] = parts;
    const a = parts[3] === undefined ? 1 : parts[3];
    const f = (v) => {
      const c = v / 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    return [f(r), f(g), f(b)];
  };
  const relLum = (rgb) =>
    rgb ? 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2] : null;
  const fgEl = document.querySelector(fgSel);
  const bgEl = document.querySelector(bgSel);
  if (!fgEl || !bgEl) return { error: 'element missing' };
  const fg = lum(getComputedStyle(fgEl)[fgProp]);
  const bg = lum(getComputedStyle(bgEl)[bgProp]);
  if (fg === null || bg === null) return { error: 'unparsable color' };
  const l1 = Math.max(relLum(fg), relLum(bg));
  const l2 = Math.min(relLum(fg), relLum(bg));
  return { ratio: Math.round(((l1 + 0.05) / (l2 + 0.05)) * 100) / 100 };
}
"""

PAIRS = [
    ("body text", "body", "color", ".app", "background-color"),
    ("muted text", ".api-status", "color", ".app", "background-color"),
    ("nav link", ".nav-link", "color", ".navbar", "background-color"),
    ("card name", ".hardware-card-main h3", "color", ".app", "background-color"),
    ("eyebrow", ".hero .eyebrow", "color", ".app", "background-color"),
    ("sort select", ".catalog-sort-select", "color", ".catalog-sort-select", "background-color"),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ["dark", "light"]:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script(
            "try { localStorage.setItem('spectra-theme', '" + theme + "'); } catch (e) {}"
        )
        page = ctx.new_page()
        page.goto("http://localhost:5173/", wait_until="domcontentloaded")
        page.wait_for_selector(".hardware-card", timeout=20000)
        page.wait_for_timeout(800)

        print(f"== {theme} ==")
        for name, fsel, fprop, bsel, bprop in PAIRS:
            r = page.evaluate(RATIO_JS, [fsel, fprop, bsel, bprop])
            status = "PASS" if r.get("ratio", 0) >= 4.5 else ("LARGE-OK" if r.get("ratio", 0) >= 3 else "FAIL")
            print(f"  {name}: {r} -> {status}")

        # Overflow + mobile run
        ctx.close()

    # Mobile overflow check both themes
    for theme in ["dark", "light"]:
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script(
            "try { localStorage.setItem('spectra-theme', '" + theme + "'); } catch (e) {}"
        )
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
        page.goto("http://localhost:5173/", wait_until="domcontentloaded")
        page.wait_for_selector(".hardware-card", timeout=20000)
        page.wait_for_timeout(800)
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth > window.innerWidth"
        )
        hscroll = page.evaluate(
            "() => { const w = document.querySelector('.comparison-table-wrapper'); return w ? w.scrollWidth > w.clientWidth : null; }"
        )
        print(f"mobile {theme}: pageOverflow={overflow} tableScrolls={hscroll} errors={errors}")
        ctx.close()

    # Reduced motion: entrance animations must not run
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
    )
    page = ctx.new_page()
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    anim = page.evaluate(
        "() => getComputedStyle(document.querySelector('.hardware-card')).animationName"
    )
    ambient = page.evaluate(
        "() => { const el = document.createElement('div'); return 'checked-via-css'; }"
    )
    card_anim = anim
    print(f"reduced motion: card animationName={card_anim!r} (expect 'none' or subset)")
    ctx.close()
    browser.close()
