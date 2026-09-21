import test from "node:test";
import assert from "node:assert/strict";

import { parseMarkdown } from "./markdown.js";

test("parses headings and bold inline content", () => {
  assert.deepEqual(
    parseMarkdown("**AMD Ryzen Z1**\n### Key Specification Differences\n**Core and Thread Count**"),
    [
      {
        type: "paragraph",
        children: [{ type: "bold", value: "AMD Ryzen Z1" }],
      },
      {
        type: "heading",
        level: 3,
        children: [{ type: "text", value: "Key Specification Differences" }],
      },
      {
        type: "paragraph",
        children: [{ type: "bold", value: "Core and Thread Count" }],
      },
    ],
  );
});

test("parses paragraphs and bullet lists", () => {
  assert.deepEqual(
    parseMarkdown(
      "The first paragraph explains the result.\nIt continues on the next line.\n\n- **CPU A** has more cores.\n- CPU B has a lower TDP.",
    ),
    [
      {
        type: "paragraph",
        children: [
          {
            type: "text",
            value: "The first paragraph explains the result. It continues on the next line.",
          },
        ],
      },
      {
        type: "list",
        items: [
          [{ type: "bold", value: "CPU A" }, { type: "text", value: " has more cores." }],
          [{ type: "text", value: "CPU B has a lower TDP." }],
        ],
      },
    ],
  );
});

test("keeps Markdown text safe as text values", () => {
  const [paragraph] = parseMarkdown("<script>alert('xss')</script> **safe**");

  assert.deepEqual(paragraph.children, [
    { type: "text", value: "<script>alert('xss')</script> " },
    { type: "bold", value: "safe" },
  ]);
});
