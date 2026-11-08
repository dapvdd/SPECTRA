"""Phase E3 verification: spec-strip states on CPU and GPU cards."""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("try { localStorage.setItem('spectra-theme', 'dark'); } catch (e) {}")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")
    page.wait_for_selector(".hardware-card", timeout=20000)
    page.wait_for_timeout(1500)

    # Default page: all CPU -> identity strips, zero 'Loading...'
    pending = page.evaluate("() => document.querySelectorAll('.hardware-card-specs-pending').length")
    identity = page.evaluate("() => document.querySelectorAll('.hardware-card-specs-identity').length")
    loading_text = page.evaluate(
        "() => [...document.querySelectorAll('.hardware-card-specs strong')].some(el => el.textContent.trim() === 'Loading…')"
    )
    print(f"CPU page: pending={pending} identity={identity} 'Loading…' text={loading_text}")

    # GPU page: all loaded -> spec strips, zero pending
    page.click(".filter-buttons-type button:has-text('GPU')")
    page.wait_for_timeout(3500)
    pending = page.evaluate("() => document.querySelectorAll('.hardware-card-specs-pending').length")
    failed = page.evaluate("() => document.querySelectorAll('.hardware-card-specs-failed').length")
    loaded = page.evaluate("() => document.querySelectorAll('.hardware-card-specs:not(.hardware-card-specs-pending):not(.hardware-card-specs-failed):not(.hardware-card-specs-identity)').length")
    empty = page.evaluate(
        "() => [...document.querySelectorAll('.hardware-card-specs strong')].filter(el => el.textContent.trim() === 'No spec data').length"
    )
    print(f"GPU page: pending={pending} failed={failed} loaded={loaded} empty={empty} errors={errors[:3]}")
    ctx.close()
    browser.close()
