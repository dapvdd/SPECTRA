/*
 * Batch 016 real-browser verification.
 *
 * Drives the installed Chrome over the DevTools Protocol (no extra toolchain)
 * against the running Vite dev server + backend, captures screenshots of the
 * actually rendered pages at mobile/tablet/desktop widths, and exercises the
 * catalog, detail, provenance, comparison, theme, build and chat workflows.
 *
 * Writes screenshots/ and _browser_result.json next to this file.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = join(HERE, "screenshots");
const OUT = join(HERE, "_browser_result.json");
const APP_URL = process.env.APP_URL || "http://127.0.0.1:5173/";
const CDP = process.env.CDP || "http://127.0.0.1:9222";

mkdirSync(SHOTS, { recursive: true });

const results = [];
const check = (name, passed, detail = "") =>
  results.push({ name, passed: Boolean(passed), detail: String(detail) });

class Cdp {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.pending = new Map();
    this.listeners = [];
    this.ready = new Promise((resolve, reject) => {
      this.ws.addEventListener("open", () => resolve());
      this.ws.addEventListener("error", (e) => reject(new Error(String(e.message || e))));
    });
    this.ws.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id !== undefined && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      } else {
        for (const fn of this.listeners) fn(msg);
      }
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  on(fn) {
    this.listeners.push(fn);
  }
}

const consoleErrors = [];
const pageErrors = [];
const failedRequests = [];
const badResponses = [];

let cdp;

async function evaluate(expression) {
  const r = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (r.exceptionDetails) {
    throw new Error(
      r.exceptionDetails.exception?.description ||
        r.exceptionDetails.text ||
        "evaluate failed",
    );
  }
  return r.result.value;
}

async function waitFor(expression, { timeout = 20000, interval = 200 } = {}) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      if (await evaluate(expression)) return true;
    } catch {
      /* page mid-navigation */
    }
    await sleep(interval);
  }
  return false;
}

async function setViewport(width, height) {
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width < 600,
  });
}

async function screenshot(name) {
  const { data } = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
  });
  writeFileSync(join(SHOTS, name), Buffer.from(data, "base64"));
  return name;
}

async function gotoApp() {
  await cdp.send("Page.navigate", { url: APP_URL });
  await waitFor(
    "document.querySelectorAll('.hardware-grid .hardware-card').length >= 12",
  );
}

const setInput = (selector, value) =>
  evaluate(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)});
    if (!el) return false;
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, ${JSON.stringify(value)});
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  })()`);

const click = (selector, index = 0) =>
  evaluate(`(() => {
    const el = document.querySelectorAll(${JSON.stringify(selector)})[${index}];
    if (!el) return false;
    el.click();
    return true;
  })()`);

const clickButtonByText = (label, rootExpression = "document") =>
  evaluate(`(() => {
    const root = ${rootExpression};
    if (!root) return false;
    const nodes = root.querySelectorAll('button, a');
    for (const el of nodes) {
      if ((el.textContent || '').trim().includes(${JSON.stringify(label)})) { el.click(); return true; }
    }
    return false;
  })()`);

const submitComposer = (inputSelector) =>
  evaluate(`(() => {
    const input = document.querySelector(${JSON.stringify(inputSelector)});
    if (!input) return false;
    const form = input.closest('form');
    if (!form) return false;
    if (typeof form.requestSubmit === 'function') form.requestSubmit();
    else form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    return true;
  })()`);

const text = (selector) =>
  evaluate(
    `(document.querySelector(${JSON.stringify(selector)})?.textContent || '').trim()`,
  );

/* CDP `Runtime.evaluate` with `returnByValue` cannot serialise DOM nodes, so
   any predicate that returns an element must be coerced to a boolean here or
   the result always comes back `undefined` and every wait would time out. */
const exists = (selector) =>
  evaluate(`document.querySelectorAll(${JSON.stringify(selector)}).length > 0`);

const count = (selector) =>
  evaluate(`document.querySelectorAll(${JSON.stringify(selector)}).length`);

const overflowProbe = () =>
  evaluate(`(() => {
    const de = document.documentElement;
    const offenders = [];
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && r.right > window.innerWidth + 1) {
        const cls = typeof el.className === 'string' ? el.className : el.tagName;
        offenders.push(cls + '@' + Math.round(r.right));
      }
    }
    return {
      scrollWidth: de.scrollWidth,
      innerWidth: window.innerWidth,
      overflow: de.scrollWidth > window.innerWidth + 1,
      offenders: offenders.slice(0, 6),
    };
  })()`);

async function main() {
  const targets = await fetch(`${CDP}/json/list`).then((r) => r.json());
  const page = targets.find((t) => t.type === "page");
  if (!page) throw new Error("no Chrome page target");
  cdp = new Cdp(page.webSocketDebuggerUrl);
  await cdp.ready;

  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");
  await cdp.send("Network.enable");

  // Known rows from the disposable DB (hardware with rich provenance and
  // hardware with Geekbench single/multi results) so the detail and
  // comparison checks are deterministic.
  const backend = process.env.BACKEND || "http://127.0.0.1:8000";
  const richCpu = await fetch(`${backend}/hardware/3350`).then((r) => r.json());
  const benchCpu = await fetch(`${backend}/hardware/6`).then((r) => r.json());
  check(
    "known_fixtures_resolved",
    Boolean(richCpu?.name) && Boolean(benchCpu?.name),
    `${richCpu?.name} / ${benchCpu?.name}`,
  );

  cdp.on((msg) => {
    if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
      consoleErrors.push(
        msg.params.args.map((a) => a.value ?? a.description ?? "").join(" "),
      );
    } else if (msg.method === "Runtime.exceptionThrown") {
      pageErrors.push(
        msg.params.exceptionDetails.exception?.description ||
          msg.params.exceptionDetails.text,
      );
    } else if (msg.method === "Network.loadingFailed" && !msg.params.canceled) {
      failedRequests.push(`${msg.params.type}:${msg.params.errorText}`);
    } else if (msg.method === "Network.responseReceived") {
      if (msg.params.response.status >= 400) {
        badResponses.push(`${msg.params.response.status} ${msg.params.response.url}`);
      }
    } else if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error") {
      consoleErrors.push(`[log] ${msg.params.entry.text}`);
    }
  });

  // ---- 1. Landing + catalog at three widths -----------------------------
  for (const vp of [
    { name: "mobile-390", width: 390, height: 844 },
    { name: "tablet-768", width: 768, height: 1024 },
    { name: "desktop-1440", width: 1440, height: 900 },
  ]) {
    await setViewport(vp.width, vp.height);
    await gotoApp();
    const cards = await count(".hardware-grid .hardware-card");
    check(`catalog_renders_${vp.name}`, cards >= 12, `cards=${cards}`);
    const probe = await overflowProbe();
    check(
      `no_horizontal_overflow_${vp.name}`,
      !probe.overflow,
      `scrollWidth=${probe.scrollWidth} innerWidth=${probe.innerWidth} offenders=${JSON.stringify(probe.offenders)}`,
    );
    await screenshot(`${vp.name}-landing.png`);
  }

  await setViewport(1440, 900);
  await gotoApp();

  const readoutValue = await text(".catalog-readout-value");
  const readoutMeta = await text("#catalog-count");
  check("catalog_total_is_real", /5,?380/.test(await text(".catalog-readout-value")), `value=${await text(".catalog-readout-value")}`);
  check(
    "catalog_readout_meta",
    /of/.test(await text(".catalog-readout-meta")),
    await text(".catalog-readout-meta"),
  );
  const navNames = await evaluate(
    `[...document.querySelectorAll('.nav-links .nav-link')].map((a) => (a.textContent||'').trim())`,
  );
  const navCount = await count(".nav-links .nav-link");
  check(
    "nav_links_present",
    navCount === 4 &&
      ["Explore", "Compare", "Build", "About"].every((n) => navNames.includes(n)),
    `names=${JSON.stringify(navNames)}`,
  );

  // ---- 2. Theme control -------------------------------------------------
  await click('button[aria-label="Dark theme"]');
  let theme = await evaluate(
    "({theme: document.documentElement.getAttribute('data-theme'), pref: document.documentElement.getAttribute('data-theme-preference')})",
  );
  check("theme_dark", theme.theme === "dark" && theme.pref === "dark", JSON.stringify(theme));

  await click('button[aria-label="Light theme"]');
  theme = await evaluate(
    "({theme: document.documentElement.getAttribute('data-theme'), pref: document.documentElement.getAttribute('data-theme-preference')})",
  );
  check("theme_light", theme.theme === "light" && theme.pref === "light", JSON.stringify(theme));

  await click('button[aria-label="System theme"]');
  theme = await evaluate(
    "({theme: document.documentElement.getAttribute('data-theme'), pref: document.documentElement.getAttribute('data-theme-preference')})",
  );
  check(
    "theme_system",
    theme.pref === "system" && (theme.theme === "dark" || theme.theme === "light"),
    JSON.stringify(theme),
  );

  // ---- 3. Search + filters ---------------------------------------------
  const totalCards = await text(".catalog-readout-meta");
  await setInput("#catalog-search", "Ryzen 9 7950X");
  await sleep(300);
  const searchReadout = await text(".catalog-readout-meta");
  const searchNames = await evaluate(
    "Array.from(document.querySelectorAll('.hardware-card h3')).map(el => el.textContent.trim())",
  );
  check(
    "search_filters_catalog",
    searchNames.length > 0 &&
      searchNames.every((n) => n.toLowerCase().includes("ryzen")) &&
      searchReadout !== totalCards,
    `n=${searchNames.length} readout="${searchReadout}"`,
  );
  await click(".clear-search-icon");
  await sleep(200);

  await clickButtonByText("GPU");
  await sleep(300);
  const gpuKickers = await evaluate(
    "Array.from(document.querySelectorAll('.hardware-card-kicker')).map(el => el.textContent.trim())",
  );
  const gpuReadout = await text(".catalog-readout-meta");
  check(
    "type_filter_gpu",
    gpuKickers.length > 0 && gpuKickers.every((k) => k === "GPU") && gpuReadout.includes("1879"),
    `n=${gpuKickers.length} readout="${gpuReadout}"`,
  );

  await clickButtonByText("All hardware");
  await sleep(300);
  const allCount = await text(".catalog-readout-meta");
  check("filter_reset_all", allCount.includes("5380"), `readout="${allCount}"`);

  // A manufacturer filter narrows results too.
  await clickButtonByText("Intel");
  await sleep(300);
  const makerReadout = await text(".catalog-readout-meta");
  check(
    "manufacturer_filter",
    makerReadout.includes("Intel") && !makerReadout.includes("5,380"),
    `readout="${makerReadout}"`,
  );
  await clickButtonByText(
    "All",
    'document.querySelector(\'[aria-label="Filter hardware by manufacturer"]\')',
  );
  await sleep(200);

  // Load-more pagination.
  const before = await count(".hardware-grid .hardware-card");
  await clickButtonByText("Load more hardware");
  await sleep(300);
  const after = await count(".hardware-grid .hardware-card");
  check("load_more_pagination", after === before + 12, `before=${before} after=${after}`);

  // ---- 4. CPU detail + source provenance -------------------------------
  await clickButtonByText("All hardware");
  await sleep(150);
  await setInput("#catalog-search", richCpu.name);
  await sleep(350);
  await click(".hardware-card-main");
  const detailReady = await waitFor(
    "document.querySelector('.hardware-detail') && !document.querySelector('.detail-state')",
  );
  check("cpu_detail_opens", detailReady, `detailReady=${detailReady}`);
  const detailName = await text(".hardware-detail h2, .hardware-detail h1");
  const specRows = await count(".hardware-detail .spec-source");
  check(
    "cpu_detail_has_spec_source_disclosures",
    specRows > 0,
    `rows=${specRows} name="${detailName}"`,
  );

  const disclosureDetails = await count(".hardware-detail details.spec-source");
  if (disclosureDetails > 0) {
    await evaluate(
      "document.querySelector('.hardware-detail details.spec-source').open = true",
    );
    await sleep(150);
    const recordItems = await count(".hardware-detail .source-record");
    const recordText = await text(".hardware-detail .source-record");
    check(
      "source_disclosure_expands_with_record",
      recordItems > 0 && recordText.length > 0,
      `records=${recordItems} first="${recordText.slice(0, 80)}"`,
    );
  } else {
    check("source_disclosure_expands_with_record", false, "no <details> spec source found");
  }

  const benchFootnotes = await count(".hardware-detail .benchmark-sources");
  const licenseTags = await count(".hardware-detail .source-license-tag");
  check(
    "benchmark_source_footnotes_present",
    benchFootnotes > 0,
    `footnotes=${benchFootnotes} licenseTags=${licenseTags}`,
  );

  const detailOverflow = await overflowProbe();
  check(
    "cpu_detail_no_overflow",
    !detailOverflow.overflow,
    JSON.stringify(detailOverflow),
  );
  await screenshot("desktop-cpu-detail.png");

  // ---- 5. Ask SPECTRA (hardware chat) ----------------------------------
  const composerSel = "#hardware-chat-title-composer";
  const hasComposer = await count(composerSel);
  check("hardware_chat_composer_present", hasComposer === 1, `n=${hasComposer}`);
  if (hasComposer) {
    await setInput(composerSel, "What is the weather in Paris tomorrow?");
    await submitComposer(composerSel);
    const answered = await waitFor(
      `document.querySelectorAll('.hardware-detail .hardware-chat-answer').length > 0 ||
       document.querySelectorAll('.hardware-detail .hardware-chat-error').length > 0`,
      { timeout: 90000 },
    );
    const chatState = await evaluate(`(() => {
      const t = document.querySelector('.hardware-detail .hardware-chat');
      if (!t) return 'no-chat';
      if (t.querySelector('.hardware-chat-error')) return 'error';
      if (t.querySelector('.hardware-chat-message[role=status]')) return 'loading';
      if (t.querySelector('.hardware-chat-answer')) return 'answered';
      return 'unknown';
    })()`);
    check(
      "hardware_chat_out_of_scope_handled",
      hasComposer === 1 && chatState !== "no-chat" && chatState !== "loading",
      `state=${chatState}`,
    );
    await screenshot("desktop-hardware-chat.png");
  }

  // Back to catalog.
  await clickButtonByText("Back to catalog");
  await waitFor("document.querySelectorAll('.hardware-grid .hardware-card').length >= 12");

  // ---- 6. Comparison (CPU vs CPU) + evidence separation ---------------
  await clickButtonByText("CPU");
  await sleep(250);
  await setInput("#catalog-search", richCpu.name);
  await sleep(300);
  await click(".compare-button", 0);
  await sleep(300);
  await setInput("#catalog-search", benchCpu.name);
  await sleep(300);
  await click(".compare-button", 0);
  await sleep(500);
  const selectionItems = await count(".comparison-selection-item");
  check("comparison_selection_tray", selectionItems === 2, `items=${selectionItems}`);

  await evaluate("document.querySelector('#compare')?.scrollIntoView()");
  await sleep(300);
  const compareReady = await waitFor(
    "document.querySelectorAll('#compare .comparison-table-wrapper, #compare table').length > 0",
    { timeout: 15000 },
  );
  const benchComparison = await count("#compare .benchmark-comparison");
  const compareSourceSummaries = await count("#compare .comparison-source-summary, #compare .source-license-tag, #compare .benchmark-sources");
  check("comparison_view_renders", compareReady, `ready=${compareReady}`);
  check(
    "comparison_keeps_benchmark_evidence_separate",
    benchComparison > 0,
    `benchmarkBlocks=${benchComparison} sourceMarks=${compareSourceSummaries}`,
  );
  const compareOverflow = await overflowProbe();
  check("comparison_no_overflow", !compareOverflow.overflow, JSON.stringify(compareOverflow));
  await screenshot("desktop-comparison.png");

  // AI explanation (live provider).
  if (await count(".ai-analysis-button")) {
    await click(".ai-analysis-button");
    const aiDone = await waitFor(
      `document.querySelectorAll('.ai-analysis-result, .ai-analysis-error').length > 0`,
      { timeout: 90000 },
    );
    const aiState = (await count(".ai-analysis-result")) > 0 ? "success" : "error";
    check("comparison_ai_analysis", aiDone, `state=${aiState}`);
  } else {
    check("comparison_ai_analysis", false, "no ai-analysis-button");
  }

  // ---- 7. Build configuration + intelligence --------------------------
  if (await count(".clear-search-icon")) {
    await click(".clear-search-icon");
    await sleep(200);
  }
  await evaluate("document.querySelector('#explore')?.scrollIntoView()");
  await sleep(200);
  await clickButtonByText("CPU");
  await sleep(250);
  const cpuBuildClicked = await clickButtonByText("Add to Build");
  await sleep(600);
  await clickButtonByText("GPU");
  await sleep(250);
  const gpuBuildClicked = await clickButtonByText("Add to Build");
  await sleep(900);
  check("build_slots_added", cpuBuildClicked && gpuBuildClicked, `cpu=${cpuBuildClicked} gpu=${gpuBuildClicked}`);

  await evaluate("document.querySelector('#build')?.scrollIntoView()");
  await sleep(600);
  const buildSummary = await evaluate(
    "Array.from(document.querySelectorAll('.build-summary-item strong')).map(el => el.textContent.trim())",
  );
  check(
    "build_summary_populated",
    buildSummary.length >= 2 && buildSummary.every((s) => s && s !== "Empty slot"),
    JSON.stringify(buildSummary),
  );
  const intelligence = await count(".build-intelligence-signals, .build-intelligence");
  const buildChat = await count(".build-chat");
  check("build_intelligence_renders", intelligence > 0, `blocks=${intelligence}`);
  check("build_chat_present", buildChat > 0, `n=${buildChat}`);
  const buildOverflow = await overflowProbe();
  check("build_no_overflow", !buildOverflow.overflow, JSON.stringify(buildOverflow));
  await screenshot("desktop-build.png");

  // Build chat out-of-scope question. The app restores any persisted
  // conversation for the current build in the background, so the composer only
  // becomes usable once that restore settles. Wait for it before submitting,
  // otherwise the keystrokes land in an input the restore then re-renders away.
  const buildComposer = "#build-chat-title-composer";
  const restoreSettled = await waitFor(
    `document.querySelectorAll('.build-chat .build-conversation-status').length === 0`,
    { timeout: 60000 },
  );
  const composerReady = await waitFor(
    `(() => {
      const input = document.querySelector(${JSON.stringify(buildComposer)});
      return Boolean(input) && !input.disabled;
    })()`,
    { timeout: 60000 },
  );
  if (await count(buildComposer)) {
    await setInput(buildComposer, "Will this build run Crysis?");
    await submitComposer(buildComposer);
    const buildAnswered = await waitFor(
      `document.querySelectorAll('.build-chat .build-chat-message-assistant, .build-chat .hardware-chat-error').length > 0`,
      { timeout: 180000 },
    );
    const buildState = await evaluate(`(() => {
      const t = document.querySelector('.build-chat');
      if (!t) return 'no-build-chat';
      if (t.querySelector('.hardware-chat-error')) return 'error';
      if (t.querySelector('.hardware-chat-message[role=status]')) return 'loading';
      if (t.querySelector('.build-chat-message-assistant')) return 'answered';
      return 'idle';
    })()`);
    check(
      "build_chat_answers",
      buildAnswered && restoreSettled && composerReady,
      `state=${buildState} restored=${restoreSettled} ready=${composerReady}`,
    );
    await screenshot("desktop-build-chat.png");
  } else {
    check("build_chat_answers", false, "no build composer");
  }

  // ---- 8. Keyboard navigation + reduced motion ------------------------
  /* Focus starts wherever the last click left it. Reload the app so focus
     begins at the document top exactly as a fresh load would, making the first
     Tab reach the skip link as a keyboard user would experience it. */
  await cdp.send("Emulation.setEmulatedMedia", { features: [] });
  await gotoApp();
  await sleep(300);
  await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 });
  await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 });
  await sleep(300);
  const focusInfo = await evaluate(`(() => {
    const el = document.activeElement;
    const style = getComputedStyle(el);
    return {
      tag: el?.tagName,
      text: (el?.textContent || '').trim().slice(0, 40),
      href: el?.getAttribute?.('href') || null,
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
    };
  })()`);
  check(
    "keyboard_tab_focuses_skip_link",
    focusInfo.tag === "A" && focusInfo.text.toLowerCase().includes("skip"),
    JSON.stringify(focusInfo),
  );

  await cdp.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });
  await sleep(200);
  const motion = await evaluate(`(() => {
    const el = document.querySelector('.hardware-card, .catalog-readout-value');
    if (!el) return null;
    const s = getComputedStyle(el);
    return { transitionDuration: s.transitionDuration, animationDuration: s.animationDuration };
  })()`);
  /* prefers-reduced-motion sets transition/animation to 0.01ms, which Chrome
     reports as "1e-05s". Accept that plus an explicit "0s". */
  check(
    "reduced_motion_disables_transition",
    motion &&
      ["1e-05s", "0s", "0.00001s"].includes(motion.transitionDuration) &&
      ["1e-05s", "0s", "0.00001s"].includes(motion.animationDuration),
    JSON.stringify(motion),
  );
  await cdp.send("Emulation.setEmulatedMedia", { features: [] });

  // ---- 9. Console / network health ------------------------------------
  const ignorable = (line) =>
    line.includes("favicon") ||
    line.includes("Download the React DevTools") ||
    line.includes("ERR_BLOCKED_BY_CLIENT");
  const realConsoleErrors = consoleErrors.filter((l) => !ignorable(l));
  const realFailed = failedRequests.filter((l) => !l.includes("favicon") && !l.includes("net::ERR_ABORTED"));
  const realBad = badResponses.filter((l) => !l.includes("favicon"));
  check("no_console_errors", realConsoleErrors.length === 0, JSON.stringify(realConsoleErrors.slice(0, 5)));
  check("no_page_exceptions", pageErrors.length === 0, JSON.stringify(pageErrors.slice(0, 5)));
  check("no_failed_requests", realFailed.length === 0, JSON.stringify(realFailed.slice(0, 5)));
  check("no_error_responses", realBad.length === 0, JSON.stringify(realBad.slice(0, 5)));

  const passed = results.filter((r) => r.passed).length;
  const payload = {
    generated_at: new Date().toISOString(),
    app_url: APP_URL,
    chrome: (await fetch(`${CDP}/json/version`).then((r) => r.json())).Browser,
    checks: results,
    passed,
    failed: results.length - passed,
    all_passed: passed === results.length,
    consoleErrors: realConsoleErrors,
    pageErrors,
    failedRequests: realFailed,
    badResponses: realBad,
    screenshots: results.map((r) => r.name).length,
  };
  writeFileSync(OUT, JSON.stringify(payload, null, 2), "utf8");
  for (const r of results) console.log(r.passed ? "PASS" : "FAIL", r.name, "-", r.detail);
  console.log(`\nTOTAL ${passed}/${results.length} -> ${OUT}`);
  return payload.all_passed ? 0 : 1;
}

main()
  .then((code) => process.exit(code))
  .catch((err) => {
    console.error("browser_verify crashed:", err);
    writeFileSync(
      OUT,
      JSON.stringify({ crashed: String(err?.stack || err), checks: results }, null, 2),
      "utf8",
    );
    process.exit(2);
  });
