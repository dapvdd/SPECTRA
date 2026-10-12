"""Minimal, deterministic MediaWiki wikitext table parser (Batch 014).

Parses ``{| ... |}`` tables from raw wikitext into a rectangular grid,
honouring ``rowspan`` / ``colspan``, and cleans common inline markup
(refs, templates, links, entities) so a cell can be read as a value.

Dependency-free. The parser never interprets column *meaning*; callers map
columns per table.
"""

from __future__ import annotations

import re

_REF_RE = re.compile(r"<ref[^>]*?/>|<ref[^>]*?>.*?</ref>", re.DOTALL | re.IGNORECASE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_templates(text: str) -> str:
    # Drop footnote/reference templates entirely (their text is commentary,
    # not the value).
    for _ in range(4):
        new = re.sub(r"\{\{\s*(?:efn|refn|note|ref|r|sfn)[^{}]*\}\}", "", text)
        if new == text:
            break
        text = new

    def dts(m):
        parts = [p.strip() for p in m.group(1).split("|")]
        return "-".join(p for p in parts if "=" not in p)

    text = re.sub(r"\{\{\s*dts\s*\|([^}]*)\}\}", dts, text, flags=re.IGNORECASE)
    for name in ("tooltip", "abbr", "nowrap"):
        text = re.sub(
            r"\{\{\s*%s\s*\|([^|}]*)\|?[^}]*\}\}" % name,
            lambda m: m.group(1),
            text,
            flags=re.IGNORECASE,
        )

    def simple(m):
        parts = [p.strip() for p in m.group(1).split("|")]
        args = [p for p in parts[1:] if "=" not in p and "{{" not in p]
        return args[0] if args else ""

    for _ in range(5):
        new = re.sub(r"\{\{([^{}]*?)\}\}", simple, text)
        if new == text:
            break
        text = new
    return text


def clean_cell(text: str) -> str:
    text = _COMMENT_RE.sub("", text)
    text = _REF_RE.sub("", text)
    text = _strip_templates(text)
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[https?://[^\s\]]+\s+([^\]]*)\]", r"\1", text)
    text = re.sub(r"\[https?://[^\]]*\]", "", text)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"&[a-z]+;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_attrs(piece: str):
    piece = piece.strip()
    # explicit separator: attributes + '|' + content
    if "|" in piece:
        prefix = piece.split("|", 1)[0]
        if re.fullmatch(r"(?:\s*[A-Za-z][\w:-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'|\S+))+\s*", prefix):
            _, rest = piece.split("|", 1)
            return prefix.strip(), rest.strip()
    # attributes attached directly to content (MediaWiki allows the separator
    # only when content exists; blank/NA cells omit it)
    m = re.match(
        r"((?:\s*[A-Za-z][\w:-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'|\S+))+\s*)(.*)$",
        piece,
    )
    if m and (m.group(2).strip() or "rowspan" in m.group(1) or "colspan" in m.group(1)):
        return m.group(1).strip(), m.group(2).strip()
    if piece in ("", "|"):
        return "", ""
    return "", piece


def _split_cells(row_lines):
    cells = []
    attrs_c = None
    content_c = []

    def flush():
        if content_c or attrs_c is not None:
            cells.append((attrs_c or "", " ".join(content_c).strip()))

    for raw in row_lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        stripped = line.lstrip()
        if stripped[0] in "|!":
            marker = stripped[0]
            body = stripped[1:]
            sep = "||" if marker == "|" else "!!"
            for k, piece in enumerate(body.split(sep)):
                attrs, content = _split_attrs(piece)
                if k == 0:
                    flush()
                    attrs_c, content_c = attrs, ([content] if content else [])
                else:
                    cells.append((attrs, content))
        else:
            content_c.append(stripped.strip())
    flush()
    return cells


def _attr_int(attrs, name, default):
    m = re.search(r"%s\s*=\s*\"?(\d+)" % name, attrs)
    return int(m.group(1)) if m else default


def _split_rows(lines):
    raw_rows, current = [], []
    for l in lines:
        if l.startswith("|-"):
            raw_rows.append(current)
            current = []
        elif l.startswith("|}"):
            raw_rows.append(current)
            current = []
        else:
            current.append(l)
    if current:
        raw_rows.append(current)
    return raw_rows


def parse_table(lines):
    """Return a rectangular list-of-lists grid for one table's raw lines."""
    raw_rows = _split_rows(lines[1:])
    grid = []
    carry = []  # carry[r][col] = value held by a rowspan from an earlier row
    ncols = 0
    for r, row_lines in enumerate(raw_rows):
        while len(carry) <= r:
            carry.append({})
        row = dict(carry[r])
        col = 0
        for attrs, content in _split_cells(row_lines):
            while col in row:
                col += 1
            rowspan = _attr_int(attrs, "rowspan", 1)
            colspan = _attr_int(attrs, "colspan", 1)
            value = clean_cell(content)
            for dc in range(colspan):
                row[col + dc] = value
                for rr in range(1, rowspan):
                    while len(carry) <= r + rr:
                        carry.append({})
                    carry[r + rr][col + dc] = value
            col += colspan
        ncols = max(ncols, (max(row) + 1) if row else 0)
        grid.append(row)
    return [[row.get(c, "") for c in range(ncols)] for row in grid]


def find_tables(path):
    """Return list of (start_line, lines) for each top-level table."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    tables, i = [], 0
    while i < len(lines):
        if lines[i].startswith("{|"):
            depth, j = 0, i
            while j < len(lines):
                if lines[j].startswith("{|"):
                    depth += 1
                if lines[j].startswith("|}"):
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            tables.append((i + 1, lines[i:j + 1]))
            i = j + 1
        else:
            i += 1
    return tables
