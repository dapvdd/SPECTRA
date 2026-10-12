import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

/*
 * Batch 016 regression coverage.

 * `MarkdownContent` in App.jsx renders AI answers, build-chat messages and the
 * comparison explanation by calling the `parseMarkdown` helper from
 * ./markdown.js. That helper is used but was never imported, so every one of
 * those surfaces threw `ReferenceError: parseMarkdown is not defined` at
 * render time and crashed the whole React tree.

 * There is no DOM renderer available in this project's test setup, so the
 * defect is covered the way the rest of the suite covers the JSX/CSS contract:
 * by asserting the import wiring directly, then asserting the imported symbol
 * is the real helper. A missing import cannot slip back through unnoticed.
 */

const appSource = readFileSync(new URL("./App.jsx", import.meta.url), "utf8");

const markdownImport = appSource.match(
  /^import\s*\{([^}]*)\}\s*from\s*["']\.\/markdown\.js["'];/m,
);

describe("markdown rendering wiring", () => {
  it("imports parseMarkdown from ./markdown.js", () => {
    assert.ok(
      markdownImport,
      'App.jsx must import parseMarkdown from "./markdown.js"',
    );
    const imported = markdownImport[1]
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean);
    assert.ok(
      imported.includes("parseMarkdown"),
      `parseMarkdown must be imported, found: ${imported.join(", ")}`,
    );
  });

  it("actually uses the imported helper rather than a local redefinition", () => {
    const localDefinition = appSource.match(
      /(?:const|function)\s+parseMarkdown\s*=/,
    );
    assert.equal(
      localDefinition,
      null,
      "parseMarkdown must come from ./markdown.js, not be redeclared locally",
    );
    assert.ok(
      appSource.includes("parseMarkdown(markdown)"),
      "MarkdownContent should delegate to parseMarkdown",
    );
  });

  it("keeps parseMarkdown available to every MarkdownContent use", async () => {
    const { parseMarkdown } = await import("./markdown.js");
    const blocks = parseMarkdown("**bold**\n- item");
    assert.deepEqual(blocks[0], {
      type: "paragraph",
      children: [{ type: "bold", value: "bold" }],
    });
    assert.equal(blocks[1].type, "list");
    assert.equal(blocks[1].items.length, 1);
  });
});
