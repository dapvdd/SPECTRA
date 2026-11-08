"""Phase F hero verification: overlap, structure, console errors."""
from playwright.sync_api import sync_playwright

CHECK_JS = """
() => {
  const r = (el) => el ? el.getBoundingClientRect() : null;
  const h1 = r(document.querySelector('.hero h1'));
  const stage = r(document.querySelector('.hero-stage-svg'));
  const signal = document.querySelector('.signal');
  const hero = document.querySelector('.hero');
  const sig = r(signal);
  const overlapH1Stage = h1 && stage &&
    !(h1.right <= stage.left || stage.right <= h1.left || h1.bottom <= stage.top || stage.bottom <= h1.top);
  const signalParent = signal ? (signal.parentElement ? signal.parentElement.className : 'NO-PARENT') : 'NO-SIGNAL';
  return {
    overlapH1Stage: !!overlapH1Stage,
    signalParent,
    signalBelowHero: sig && hero ? Math.round(sig.top - hero.getBoundingClientRect().bottom) : null,
    overflow: document.documentElement.scrollWidth > window.innerWidth,
    heroHeight: hero ? Math.round(hero.getBoundingClientRect().height) : null,
    h1Right: h1 ? Math.round(h1.right) : null,
    stageLeft: stage ? Math.round(stage.left) : null,
  };
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ["dark", "light"]:
        for w, h, name in [(1440, 900, "desktop"), (768, 1024, "tablet"), (390, 844, "mobile")]:
            ctx = browser.new_context(viewport={"width": w, "height": h})
            ctx.add_init_script(f"try {{ localStorage.setItem('spectra-theme', '{theme}'); }} catch (e) {{}}")
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
            page.goto("http://localhost:5173/", wait_until="domcontentloaded")
            page.wait_for_selector(".hardware-card", timeout=20000)
            page.wait_for_timeout(900)
            try:
                m = page.evaluate(CHECK_JS)
                print(f"{theme}/{name}: overlap={m['overlapH1Stage']} sigParent={m['signalParent']} "
                      f"sigGap={m['signalBelowHero']}px overflow={m['overflow']} heroH={m['heroHeight']} "
                      f"h1R={m['h1Right']} stageL={m['stageLeft']} errors={errors[:2]}")
            except Exception as exc:
                print(f"{theme}/{name}: EVAL FAILED {str(exc)[:120]} errors={errors[:3]}")
            ctx.close()
    browser.close()
