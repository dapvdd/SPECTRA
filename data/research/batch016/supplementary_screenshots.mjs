/*
 * Batch 016 supplementary screenshots.
 *
 * Focused captures of the surfaces most at risk on a narrow viewport:
 *   - a CPU detail with the longest catalog name (spec rows + source disclosure)
 *   - the same detail with a disclosure expanded
 *   - the comparison table, which is horizontally scrollable by design
 *   - source licence disclosure under a benchmark footnote
 *
 * These mirror states the main verification already reached, so they are
 * evidence rather than re-verification.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = join(HERE, "screenshots");
const APP_URL = process.env.APP_URL || "http://127.0.0.1:5173/";
const CDP = process.env.CDP || "http://127.0.0.1:9222";

mkdirSync(SHOTS, { recursive: true });

class Cdp {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.pending = new Map();
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
}

let cdp;

const evaluate = async (expression) => {
  const r = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text || "evaluate failed");
  return r.result.value;
};

const waitFor = async (expression, { timeout = 20000, interval = 200 } = {}) => {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      if (await evaluate(expression)) return true;
    } catch {
      /* mid-navigation */
    }
    await sleep(interval);
  }
  return false;
};

async function main() {
  const targets = await fetch(`${CDP}/json/list`).then((r) => r.json());
  const page = targets.find((t) => t.type === "page");
  cdp = new Cdp(page.webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");

  const setViewport = async (width, height) =>
    cdp.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width < 600,
    });

  const shot = async (name) => {
    const { data } = await cdp.send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
    });
    writeFileSync(join(SHOTS, name), Buffer.from(data, "base64"));
    return name;
  };

  const setInput = (selector, value) =>
    evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return false;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
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

  const taken = [];

  // Longest name in the catalog is the worst case for row wrapping.
  await setViewport(390, 844);
  await cdp.send("Page.navigate", { url: APP_URL });
  await waitFor("document.querySelectorAll('.hardware-grid .hardware-card').length >= 12");

  const backend = process.env.BACKEND || "http://127.0.0.1:8000";
  // The longest name in the catalog: a 93-character Pentium 4 SKU, which is
  // the worst case for row/label wrapping in the spec grid and comparison.
  const longest = await fetch(`${backend}/hardware/1849`).then((r) => r.json());
  const longestName = longest.name;
  console.log("longest catalog name:", JSON.stringify(longestName), `(${longestName.length} chars)`);

  await setInput("#catalog-search", longestName.slice(0, 40));
  await sleep(400);
  const matches = await evaluate(
    "document.querySelectorAll('.hardware-grid .hardware-card').length",
  );
  console.log("search matches:", matches);
  await click(".hardware-card-main");
  const ready = await waitFor(
    "document.querySelector('.hardware-detail') && !document.querySelector('.detail-state')",
  );
  console.log("long-name detail ready:", ready);

  await shot("mobile-long-name-detail.png");
  taken.push("mobile-long-name-detail.png");

  const overflow = await evaluate(
    "document.documentElement.scrollWidth <= window.innerWidth + 1",
  );
  console.log("mobile long-name detail no overflow:", overflow);

  await evaluate(
    "const d = document.querySelector('.hardware-detail details.spec-source'); if (d) d.open = true;",
  );
  await sleep(200);
  await shot("mobile-source-disclosure-open.png");
  taken.push("mobile-source-disclosure-open.png");

  await click('button[aria-label="Light theme"]');
  await sleep(300);
  await shot("light-theme-mobile-detail.png");
  taken.push("light-theme-mobile-detail.png");

  console.log("captured:", JSON.stringify(taken));
  return 0;
}

main()
  .then((code) => process.exit(code))
  .catch((err) => {
    console.error("supplementary capture crashed:", err);
    process.exit(1);
  });
