import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

/*
 * Regression coverage for the markdown rendering wiring.
 *
 * After Phase 2.2 component decomposition, `MarkdownContent` lives in
 * `components/Markdown.jsx` and delegates to the `parseMarkdown` helper from
 * ./markdown.js. App.jsx imports `MarkdownContent` from the component file.
 *
 * There is no DOM renderer available in this project's test setup, so the
 * contract is covered by asserting the import wiring directly, then asserting
 * the imported symbol is the real helper. A missing import cannot slip back
 * through unnoticed.
 */

const markdownComponentSource = readFileSync(
  new URL("./components/Markdown.jsx", import.meta.url),
  "utf8",
);

const appSource = readFileSync(new URL("./App.jsx", import.meta.url), "utf8");

const markdownImportInComponent = markdownComponentSource.match(
  /^import\s*\{([^}]*)\}\s*from\s*["']\.\.\/markdown\.js["'];/m,
);

describe("markdown rendering wiring", () => {
  it("imports parseMarkdown from ../markdown.js in the component file", () => {
    const localSource = markdownComponentSource;
    const localRedefinition = localSource.match(
      /(?:const|function)\s+parseMarkdown\s*=|parseMarkdown:\s*function/,
    );
    assert.equal(
      localRedefinition,
      null,
      "parseMarkdown must come from ../markdown.js, not be redeclared locally",
    );

    assert.ok(
      markdownImportInComponent,
      'components/Markdown.jsx must import parseMarkdown from "../markdown.js"',
    );
    const imported = markdownImportInComponent[1]
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean);
    assert.ok(
      imported.includes("parseMarkdown"),
      `parseMarkdown must be imported, found: ${imported.join(", ")}`,
    );
  });

  it("MarkdownContent delegates to parseMarkdown", () => {
    assert.ok(
      markdownComponentSource.includes("parseMarkdown(markdown)"),
      "MarkdownContent should delegate to parseMarkdown",
    );
  });

  it("App.jsx uses the extracted MarkdownContent component", () => {
    assert.ok(
      /import\s*\{[^}]*MarkdownContent[^}]*\}\s*from\s*["']\.\/components\/Markdown\.jsx["'];/.test(
        appSource,
      ),
      "App.jsx must import MarkdownContent from ./components/Markdown.jsx",
    );
    assert.ok(
      appSource.includes("<MarkdownContent"),
      "App.jsx must use <MarkdownContent> after decomposition",
    );
    assert.equal(
      /(?:const|function)\s+MarkdownContent\s*=/.test(appSource),
      false,
      "MarkdownContent must not be redefined locally in App.jsx",
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
