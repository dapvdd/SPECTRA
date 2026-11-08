from playwright.sync_api import sync_playwright

METRICS_JS = """
() => {
  const hero = document.querySelector('.hero');
  const heroRect = hero ? hero.getBoundingClientRect() : null;
  const grid = document.querySelector('.hardware-grid');
  return {
    heroHeightPx: heroRect ? Math.round(heroRect.height) : null,
    heroDominates: heroRect ? (heroRect.height / window.innerHeight) > 0.85 : null,
    gridTopPx: grid ? Math.round(grid.getBoundingClientRect().top + window.scrollY) : null,
  };
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ["dark"]:
        for width, height, name in [(768, 1024, "tablet-768"), (390, 844, "mobile-390")]:
            ctx = browser.new_context(viewport={"width": width, "height": height})
            ctx.add_init_script(
                "try { localStorage.setItem('spectra-theme', '" + theme + "'); } catch (e) {}"
            )
            page = ctx.new_page()
            page.goto("http://localhost:5173/", wait_until="domcontentloaded")
            page.wait_for_selector(".hardware-card", timeout=20000)
            page.wait_for_timeout(1000)
            m = page.evaluate(METRICS_JS)
            print(name, m)
            ctx.close()
    browser.close()
