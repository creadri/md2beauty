from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Iterable, Iterator, Union, Any
import io
import re


# Simple Markdown IR nodes (block-level only for now)

@dataclass
class Block:
    pass


@dataclass
class Document(Block):
    blocks: List[Block] = field(default_factory=list)


@dataclass
class Heading(Block):
    level: int
    text: str


@dataclass
class Paragraph(Block):
    text: str


@dataclass
class CodeBlock(Block):
    language: Optional[str]
    code: str


@dataclass
class ListItem:
    text: str
    checked: Optional[bool] = None  # for task list items: True/False/None


@dataclass
class ListBlock(Block):
    ordered: bool
    items: List[ListItem] = field(default_factory=list)


@dataclass
class Image(Block):
    alt: str
    src: str


@dataclass
class SvgBlock(Block):
    svg: str  # raw inline SVG markup


@dataclass
class ThematicBreak(Block):
    pass


@dataclass
class Table(Block):
    headers: List[str]
    aligns: List[Optional[str]]  # 'left' | 'center' | 'right' | None per column
    rows: List[List[str]]


# ---------------- Inline emphasis (bold/italic/strikethrough) ----------------

@dataclass
class InlineSpan:
    text: str
    bold: bool = False
    italic: bool = False
    strike: bool = False


def parse_inline_emphasis(text: str) -> List[InlineSpan]:
    """Parse a subset of Markdown inline emphasis markers into spans.

    Supported markers:
    - **bold** or __bold__ toggles bold
    - *italic* or _italic_ toggles italic
    - ~~strike~~ toggles strikethrough

    This is a simple, toggle-based parser aimed for well-formed content and may
    not handle all edge cases of full Markdown spec. It avoids allocations by
    streaming tokens and emitting spans with current flags.
    """
    if not text:
        return []
    parts = re.split(r"(\*\*|__|~~|\*|_)", text)
    bold = italic = strike = False
    spans: List[InlineSpan] = []
    for tok in parts:
        if tok == "**" or tok == "__":
            bold = not bold
            continue
        if tok == "~~":
            strike = not strike
            continue
        if tok == "*" or tok == "_":
            italic = not italic
            continue
        if tok:
            spans.append(InlineSpan(text=tok, bold=bold, italic=italic, strike=strike))
    return spans


def parse_markdown_stream(md_text: Optional[str] = None, lines: Optional[Iterable[str]] = None) -> Iterator[Block]:
    """Streaming Markdown parser yielding IR blocks incrementally.

    Accepts either a full string (md_text) or an iterable of lines.
    """
    if lines is None:
        if md_text is None:
            return
        # Iterate without allocating a list of lines
        lines_iter: Iterable[str] = io.StringIO(md_text)
    else:
        lines_iter = lines

    para_buf: List[str] = []
    list_mode: Optional[str] = None  # 'ul' or 'ol'
    list_items: List[ListItem] = []

    def flush_para():
        nonlocal para_buf
        if para_buf:
            text = " ".join([s.strip() for s in para_buf]).strip()
            if text:
                yield Paragraph(text=text)
        para_buf = []

    def flush_list():
        nonlocal list_mode, list_items
        if list_mode and list_items:
            yield ListBlock(ordered=(list_mode == 'ol'), items=list_items)
        list_mode = None
        list_items = []

    # simple look-ahead buffer for one line
    line_iter = iter(lines_iter)
    _pushback: Optional[str] = None

    def get_line() -> Optional[str]:
        nonlocal _pushback
        if _pushback is not None:
            s = _pushback
            _pushback = None
            return s
        try:
            return next(line_iter)
        except StopIteration:
            return None

    def unget_line(s: str) -> None:
        nonlocal _pushback
        _pushback = s

    while True:
        raw_line = get_line()
        if raw_line is None:
            break
        # normalize: drop trailing newline
        line = raw_line.rstrip('\n')

        reprocess = True
        while reprocess:
            reprocess = False

            # Inline SVG block start
            if '<svg' in line:
                # flush current paragraph and list before SVG
                for b in flush_para():
                    yield b
                for b in flush_list():
                    yield b
                start_idx = line.find('<svg')
                svg_lines = [line[start_idx:]]
                # collect until </svg>
                for raw2 in line_iter:
                    l2 = raw2.rstrip('\n')
                    svg_lines.append(l2)
                    if '</svg>' in l2:
                        break
                yield SvgBlock(svg="\n".join(svg_lines))
                break

            # Thematic break (hr)
            if re.match(r"^\s{0,3}((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})\s*$", line):
                for b in flush_para():
                    yield b
                for b in flush_list():
                    yield b
                yield ThematicBreak()
                break

            # Fenced code block (``` or ~~~)
            m_fence = re.match(r"^(```|~~~)([^`]*)$", line)
            if m_fence:
                fence = m_fence.group(1)
                info = (m_fence.group(2) or '').strip()
                lang = None
                if info:
                    # language is first word of info string
                    m_lang = re.match(r"^(\S+)", info)
                    if m_lang:
                        lang = m_lang.group(1)
                code_lines: List[str] = []
                while True:
                    raw2 = get_line()
                    if raw2 is None:
                        break
                    l2 = raw2.rstrip('\n')
                    if re.match(rf"^{re.escape(fence)}\s*$", l2):
                        break
                    code_lines.append(l2)
                # flush paragraph & list then emit code block
                for b in flush_para():
                    yield b
                for b in flush_list():
                    yield b
                yield CodeBlock(language=lang, code="\n".join(code_lines))
                break

            # Indented code block (>=4 spaces or tab)
            if re.match(r"^(\t| {4,}).*$", line):
                code_lines: List[str] = []
                def dedent_one(s: str) -> str:
                    if s.startswith('\t'):
                        return s[1:]
                    # remove 4 spaces at most one level
                    return s[4:] if s.startswith('    ') else s.lstrip(' ')
                # consume this and following indented lines
                cur = line
                while True:
                    if cur.strip() == '':
                        code_lines.append('')
                    else:
                        code_lines.append(dedent_one(cur))
                    nxt = get_line()
                    if nxt is None:
                        break
                    if re.match(r"^(\t| {4,}).*$", nxt) or nxt.strip() == '':
                        cur = nxt
                        continue
                    else:
                        unget_line(nxt)
                        break
                for b in flush_para():
                    yield b
                for b in flush_list():
                    yield b
                yield CodeBlock(language=None, code="\n".join(code_lines))
                break

            # Heading
            m_h = re.match(r"^(#{1,6})\s+(.*)$", line)
            if m_h:
                for b in flush_para():
                    yield b
                for b in flush_list():
                    yield b
                level = len(m_h.group(1))
                text = m_h.group(2).strip()
                yield Heading(level=level, text=text)
                break

            # Unordered list item (with optional task [ ]/[x])
            m_ul = re.match(r"^\s*[-*+]\s+(?:\[( |x|X)\]\s+)?(.+)$", line)
            if m_ul:
                for b in flush_para():
                    yield b
                if list_mode not in (None, 'ul'):
                    # switching list types: flush previous list first
                    for b in flush_list():
                        yield b
                list_mode = 'ul'
                checked = None
                if m_ul.group(1) is not None:
                    checked = True if m_ul.group(1).lower() == 'x' else False
                text_val = m_ul.group(2).strip() if m_ul.group(2) else ''
                list_items.append(ListItem(text=text_val, checked=checked))
                break

            # Ordered list item (with optional task [ ]/[x])
            m_ol = re.match(r"^\s*\d+[.)]\s+(?:\[( |x|X)\]\s+)?(.+)$", line)
            if m_ol:
                for b in flush_para():
                    yield b
                if list_mode not in (None, 'ol'):
                    for b in flush_list():
                        yield b
                list_mode = 'ol'
                checked = None
                if m_ol.group(1) is not None:
                    checked = True if m_ol.group(1).lower() == 'x' else False
                text_val = m_ol.group(2).strip() if m_ol.group(2) else ''
                list_items.append(ListItem(text=text_val, checked=checked))
                break

            # GFM Table detection: header | header ... then divider line of dashes
            if '|' in line:
                # peek next line
                nxt_raw = get_line()
                if nxt_raw is not None:
                    nxt = nxt_raw.rstrip('\n')
                    def split_cells(s: str) -> List[str]:
                        s2 = s.strip()
                        if s2.startswith('|'):
                            s2 = s2[1:]
                        if s2.endswith('|'):
                            s2 = s2[:-1]
                        return [c.strip() for c in s2.split('|')]
                    hdr_cells = split_cells(line)
                    div_cells = split_cells(nxt)
                    def is_div_cell(c: str) -> bool:
                        return re.match(r"^:?-{3,}:?$", c.strip()) is not None
                    if hdr_cells and div_cells and len(div_cells) == len(hdr_cells) and all(is_div_cell(c) for c in div_cells):
                        for b in flush_para():
                            yield b
                        for b in flush_list():
                            yield b
                        aligns: List[Optional[str]] = []
                        for c in div_cells:
                            c = c.strip()
                            if c.startswith(':') and c.endswith(':'):
                                aligns.append('center')
                            elif c.endswith(':'):
                                aligns.append('right')
                            elif c.startswith(':'):
                                aligns.append('left')
                            else:
                                aligns.append(None)
                        rows: List[List[str]] = []
                        # consume subsequent table rows
                        while True:
                            row_raw = get_line()
                            if row_raw is None:
                                break
                            row = row_raw.rstrip('\n')
                            if '|' not in row:
                                unget_line(row_raw)
                                break
                            cells = split_cells(row)
                            # allow short rows; pad
                            if len(cells) < len(hdr_cells):
                                cells += [''] * (len(hdr_cells) - len(cells))
                            rows.append(cells[:len(hdr_cells)])
                        yield Table(headers=hdr_cells, aligns=aligns, rows=rows)
                        break
                    else:
                        # not a table; push back the peeked line
                        unget_line(nxt_raw)

            # If we reach here and we were in a list, the list ends before this line
            if list_mode is not None:
                for b in flush_list():
                    yield b
                # reprocess the same line with list cleared
                reprocess = True
                continue

            # Image single-line
            m_img = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line)
            if m_img:
                for b in flush_para():
                    yield b
                alt = m_img.group(1).strip()
                src = m_img.group(2).strip()
                yield Image(alt=alt, src=src)
                break

            # Blockquote simplified (collects one paragraph)
            m_bq = re.match(r"^>\s?(.*)$", line)
            if m_bq:
                para_buf.append(m_bq.group(1))
                break

            # Setext headings (lookahead next line for === or ---)
            if para_buf == [] and line.strip() != '':
                nxt_raw = get_line()
                if nxt_raw is not None:
                    nxt = nxt_raw.rstrip('\n')
                    if re.match(r"^\s*===+\s*$", nxt):
                        for b in flush_para():
                            yield b
                        for b in flush_list():
                            yield b
                        yield Heading(level=1, text=line.strip())
                        break
                    if re.match(r"^\s*---+\s*$", nxt):
                        for b in flush_para():
                            yield b
                        for b in flush_list():
                            yield b
                        yield Heading(level=2, text=line.strip())
                        break
                    # not a setext; push back
                    unget_line(nxt_raw)

            # Blank line -> flush paragraph
            if line.strip() == "":
                for b in flush_para():
                    yield b
                break

            # Default paragraph text
            para_buf.append(line)
            break

    # End of input: flush remaining buffers
    # First, list
    if list_mode is not None:
        for b in flush_list():
            yield b
    # Then paragraph
    for b in flush_para():
        yield b


def parse_markdown(md_text: str) -> Document:
    """Compatibility wrapper: collects streaming blocks into a Document."""
    doc = Document()
    for block in parse_markdown_stream(md_text=md_text):
        doc.blocks.append(block)
    return doc
