from playwright.sync_api import sync_playwright

METRICS_JS = """
() => {
  const doc = document.documentElement;
  const h1 = document.querySelector('h1');
  const hero = document.querySelector('.hero');
  const heroRect = hero ? hero.getBoundingClientRect() : null;
  const grid = document.querySelector('.hardware-grid');
  const gridTop = grid ? Math.round(grid.getBoundingClientRect().top + window.scrollY) : null;
  return {
    horizontalOverflow: doc.scrollWidth > window.innerWidth,
    h1FontSize: h1 ? getComputedStyle(h1).fontSize : null,
    heroHeightPx: heroRect ? Math.round(heroRect.height) : null,
    heroDominates: heroRect ? (heroRect.height / window.innerHeight) > 0.85 : null,
    gridTopPx: gridTop,
    cards: document.querySelectorAll('.hardware-card').length,
    hasCommand: !!document.querySelector('.catalog-command'),
    hasSort: !!document.querySelector('.catalog-sort-select'),
    hasQuickPaths: !!document.querySelector('.hero-quick-path'),
    theme: doc.getAttribute('data-theme'),
  };
}
"""

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
        page.wait_for_timeout(1200)
        m = page.evaluate(METRICS_JS)
        print(theme, m)
        ctx.close()
    browser.close()
