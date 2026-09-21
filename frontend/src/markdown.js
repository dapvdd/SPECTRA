const parseInlineMarkdown = (text) => {
  const parts = [];
  const boldPattern = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;

  for (const match of text.matchAll(boldPattern)) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }

    parts.push({ type: "bold", value: match[1] });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push({ type: "text", value: text.slice(lastIndex) });
  }

  return parts.length > 0 ? parts : [{ type: "text", value: "" }];
};

export const parseMarkdown = (markdown) => {
  const lines = String(markdown ?? "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let paragraphLines = [];
  let listItems = [];

  const flushParagraph = () => {
    if (paragraphLines.length > 0) {
      blocks.push({
        type: "paragraph",
        children: parseInlineMarkdown(paragraphLines.join(" ").trim()),
      });
      paragraphLines = [];
    }
  };

  const flushList = () => {
    if (listItems.length > 0) {
      blocks.push({ type: "list", items: listItems });
      listItems = [];
    }
  };

  for (const line of lines) {
    const headingMatch = line.match(/^(#{2,3})\s+(.+?)\s*#*$/);
    const listMatch = line.match(/^\s*[-*]\s+(.+)$/);

    if (headingMatch) {
      flushParagraph();
      flushList();
      blocks.push({
        type: "heading",
        level: headingMatch[1].length,
        children: parseInlineMarkdown(headingMatch[2]),
      });
    } else if (listMatch) {
      flushParagraph();
      listItems.push(parseInlineMarkdown(listMatch[1].trim()));
    } else if (line.trim() === "") {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraphLines.push(line.trim());
    }
  }

  flushParagraph();
  flushList();
  return blocks;
};
