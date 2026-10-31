/**
 * MarkdownContent
 *
 * Pure rendering component: parses and renders SPECTRA's markdown dialect
 * (bold, headings, lists). Extracted from App.jsx as part of Phase 2.2
 * component decomposition. The CSS for `.markdown-content` lives in App.css.
 */

import { parseMarkdown } from "../markdown.js";

export function MarkdownContent({ markdown, headingOffset = 0, className = "" }) {
  const blockClassName = className
    ? `markdown-content ${className}`
    : "markdown-content";

  return (
    <div className={blockClassName}>
      {parseMarkdown(markdown).map((block, blockIndex) => {
        const renderInline = (parts) =>
          parts.map((part, partIndex) =>
            part.type === "bold" ? (
              <strong key={`${blockIndex}-${partIndex}`}>{part.value}</strong>
            ) : (
              <span key={`${blockIndex}-${partIndex}`}>{part.value}</span>
            )
          );

        if (block.type === "heading") {
          const Heading = `h${Math.min(6, Math.max(1, block.level + headingOffset))}`;
          return (
            <Heading key={blockIndex}>
              {renderInline(block.children)}
            </Heading>
          );
        }

        if (block.type === "list") {
          return (
            <ul key={blockIndex}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        }

        return <p key={blockIndex}>{renderInline(block.children)}</p>;
      })}
    </div>
  );
}

export default MarkdownContent;
