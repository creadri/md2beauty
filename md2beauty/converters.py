from __future__ import annotations

from typing import Optional, Union, Iterable
import re
import tempfile
import os
import io

from .theme import Theme
from .mdparser import parse_markdown_stream
from .embeds import default_diagram_service, RenderResult


class Converter:
    """Base converter interface."""

    def __init__(self, theme: Optional[Union[str, Theme, dict]] = None):
        if theme is None or isinstance(theme, Theme):
            self.theme = theme
        elif isinstance(theme, dict):
            self.theme = Theme.from_dict(theme)
        else:
            self.theme = Theme.from_json_file(theme)

    def convert(self, md_text: str) -> bytes:
        """Convert markdown text to target format. Must return bytes ready to write to file.

        This is a compatibility wrapper. Implementations should override convert_stream
        and optionally this method to support string input.
        """
        import io as _io
        return self.convert_stream(_io.StringIO(md_text))

    def convert_stream(self, lines: Iterable[str]) -> bytes:
        """Stream-convert markdown lines to target format. Must return bytes ready to write to file."""
        raise NotImplementedError()


class HtmlConverter(Converter):
    def __init__(self, theme: Optional[Union[str, Theme]] = None):
        super().__init__(theme)

    def convert_stream(self, lines: Iterable[str]) -> bytes:
        """Render a subset of Markdown to HTML using the streaming parser.

        Mermaid code blocks are rendered (via _render_mermaid_to_svg). The output
        is conservative (block-level HTML) and intended to be lightweight so the
    project no longer depends on the external `markdown` package.
    """
        parts: list[str] = []
        # Import IR types once
        from .mdparser import (
            Heading as IRHeading,
            Paragraph as IRParagraph,
            CodeBlock as IRCode,
            ListBlock as IRList,
            Image as IRImage,
            SvgBlock as IRSvg,
            ThematicBreak as IRHr,
            Table as IRTable,
            parse_inline_emphasis,
        )
        title_text: Optional[str] = None

        # Track whether we used Pygments so we can inject CSS once
        pygments_css: Optional[str] = None

        for block in parse_markdown_stream(lines=lines):
            if isinstance(block, IRHeading):
                lvl = max(1, min(6, block.level))
                spans = parse_inline_emphasis(block.text)
                inner = "".join(self._render_inline_span_html(s) for s in spans) or self._escape_html(block.text)
                parts.append(f"<h{lvl}>{inner}</h{lvl}>")
                if title_text is None:
                    title_text = block.text.strip()
            elif isinstance(block, IRParagraph):
                spans = parse_inline_emphasis(block.text)
                inner = "".join(self._render_inline_span_html(s) for s in spans) or self._escape_html(block.text)
                parts.append(f"<p>{inner}</p>")
            elif isinstance(block, IRCode):
                if block.language == 'mermaid':
                    rr: Optional[RenderResult] = None
                    try:
                        rr = default_diagram_service.render(
                            kind="mermaid",
                            code=block.code,
                            preferred_formats=["svg", "png"],
                        )
                    except Exception:
                        rr = None
                    if rr and rr.mime == "image/svg+xml":
                        try:
                            with open(rr.path, "r", encoding="utf-8") as f:
                                parts.append(f.read())
                        finally:
                            rr.cleanup()
                    elif rr and rr.mime.startswith("image/"):
                        try:
                            with open(rr.path, "rb") as f:
                                import base64 as _b64
                                data = _b64.b64encode(f.read()).decode("ascii")
                                parts.append(f"<img src=\"data:{rr.mime};base64,{data}\" alt=\"mermaid diagram\"/>")
                        finally:
                            rr.cleanup()
                    else:
                        parts.append(self._wrap_code_block(block.code, 'mermaid'))
                else:
                    # Try Pygments server-side highlighting
                    lang = (block.language or '').strip()
                    highlighted_html: Optional[str] = None
                    if lang:
                        try:
                            from pygments import highlight  # type: ignore
                            from pygments.lexers import get_lexer_by_name  # type: ignore
                            from pygments.formatters import HtmlFormatter  # type: ignore
                            lexer = None
                            try:
                                lexer = get_lexer_by_name(lang)
                            except Exception:
                                lexer = get_lexer_by_name('text')
                            # Allow theme to choose a Pygments style via Theme.formats['html'].pygments_style
                            style_name = None
                            try:
                                if isinstance(self.theme, Theme):
                                    html_fmt = self.theme.formats.get('html') if isinstance(self.theme.formats, dict) else None
                                    if html_fmt and getattr(html_fmt, 'pygments_style', None):
                                        style_name = html_fmt.pygments_style  # type: ignore[attr-defined]
                                    if not style_name and getattr(self.theme, 'pygments_style', None):
                                        style_name = self.theme.pygments_style  # type: ignore[attr-defined]
                            except Exception:
                                style_name = None
                            if style_name:
                                try:
                                    formatter = HtmlFormatter(nowrap=False, cssclass="highlight", style=style_name)
                                except Exception:
                                    formatter = HtmlFormatter(nowrap=False, cssclass="highlight")
                            else:
                                formatter = HtmlFormatter(nowrap=False, cssclass="highlight")
                            highlighted_html = highlight(block.code, lexer, formatter)
                            # Capture CSS once
                            if pygments_css is None:
                                pygments_css = formatter.get_style_defs('.highlight')
                        except Exception:
                            highlighted_html = None
                    if highlighted_html:
                        parts.append(highlighted_html)
                    else:
                        parts.append(f"<pre><code class=\"language-{self._escape_html(lang or 'text')}\">{self._escape_html(block.code)}</code></pre>")
            elif isinstance(block, IRList):
                tag = 'ol' if block.ordered else 'ul'
                parts.append(f"<{tag}>")
                for item in block.items:
                    spans = parse_inline_emphasis(item.text)
                    inner = "".join(self._render_inline_span_html(s) for s in spans) or self._escape_html(item.text)
                    parts.append(f"<li>{inner}</li>")
                parts.append(f"</{tag}>")
            elif isinstance(block, IRImage):
                parts.append(f"<img src=\"{self._escape_html(block.src)}\" alt=\"{self._escape_html(block.alt)}\" />")
            elif isinstance(block, IRSvg):
                parts.append(block.svg)
            elif isinstance(block, IRHr):
                parts.append("<hr />")
            elif isinstance(block, IRTable):
                # Basic table rendering with alignment styles + inline emphasis
                from .mdparser import parse_inline_emphasis as _pie
                def _td_style(align: Optional[str]) -> str:
                    return f' style="text-align: {align};"' if align in ("left", "center", "right") else ''
                def _inline_html(text: str) -> str:
                    spans = _pie(text)
                    return "".join(self._render_inline_span_html(s) for s in spans) if spans else self._escape_html(text)
                thead = "<thead><tr>" + "".join(
                    f"<th{_td_style(block.aligns[i] if i < len(block.aligns) else None)}>{_inline_html(h)}</th>"
                    for i, h in enumerate(block.headers)
                ) + "</tr></thead>"
                tbody_rows = []
                for row in block.rows:
                    tds = []
                    for i, cell in enumerate(row):
                        tds.append(f"<td{_td_style(block.aligns[i] if i < len(block.aligns) else None)}>{_inline_html(cell)}</td>")
                    tbody_rows.append("<tr>" + "".join(tds) + "</tr>")
                tbody = "<tbody>" + "".join(tbody_rows) + "</tbody>"
                parts.append("<table>" + thead + tbody + "</table>")

        body_inner = "\n".join(parts)
        body_fragment = f'<div class="md2beauty-page">\n{body_inner}\n</div>'

        css_blocks: list[str] = []
        page_css = ''
        container_css = ''
        if isinstance(self.theme, Theme):
            # Base theme CSS
            css_blocks.append(self.theme.to_css())

            # Page settings for HTML/print using typed models
            page_cfg: dict = {}
            if getattr(self.theme, 'page', None):
                page_cfg.update(self.theme.page.model_dump(exclude_unset=True))  # type: ignore[attr-defined]
            html_fmt = self.theme.formats.get('html') if isinstance(self.theme.formats, dict) else None
            if html_fmt and getattr(html_fmt, 'page', None):
                page_cfg.update(html_fmt.page.model_dump(exclude_unset=True))  # type: ignore[attr-defined]

            if page_cfg:
                ptype = str(page_cfg.get('type', '')).strip().lower()
                # Map common sizes
                page_width: Optional[str] = None
                page_height: Optional[str] = None
                page_size_keyword: Optional[str] = None
                if ptype == 'a4':
                    page_size_keyword = 'A4'
                    page_width, page_height = '210mm', '297mm'
                elif ptype == 'letter':
                    page_size_keyword = 'Letter'
                    page_width, page_height = '8.5in', '11in'

                margins = page_cfg.get('margins', {}) or {}

                def _norm(v: Optional[str], default: str) -> str:
                    if v is None and v != 0:
                        return default
                    s = str(v).strip()
                    # accept px, pt, in, mm, cm as-is; bare number -> inches
                    if re.match(r"^\d+(?:\.\d+)?(px|pt|in|mm|cm)$", s):
                        return s
                    if re.match(r"^\d+(?:\.\d+)?$", s):
                        return s + 'in'
                    return default

                # Allow explicit width/height override
                page_width = page_cfg.get('width') or page_width
                page_height = page_cfg.get('height') or page_height
                if page_width:
                    page_width = _norm(page_width, '8.5in')
                if page_height:
                    page_height = _norm(page_height, '11in')

                m_top = _norm(margins.get('top'), '1in')
                m_right = _norm(margins.get('right'), '1in')
                m_bottom = _norm(margins.get('bottom'), '1in')
                m_left = _norm(margins.get('left'), '1in')

                # @page for printing
                if page_size_keyword:
                    page_css = f"@page {{ size: {page_size_keyword}; margin: {m_top} {m_right} {m_bottom} {m_left}; }}"
                elif page_width and page_height:
                    page_css = f"@page {{ size: {page_width} {page_height}; margin: {m_top} {m_right} {m_bottom} {m_left}; }}"

                # On-screen container width equals page width, with padding simulating margins.
                # For print, remove container padding and rely on @page margins.
                if page_width:
                    container_css = (
                        ".md2beauty-page { "
                        f"width: {page_width}; margin: 0 auto; padding: {m_top} {m_right} {m_bottom} {m_left}; box-sizing: border-box;"
                        " }\n"
                        "@media print { body { margin: 0; } .md2beauty-page { width: auto; padding: 0; } }\n"
                        "img, svg { max-width: 100%; height: auto; }\n"
                        "pre, blockquote, table { break-inside: avoid; page-break-inside: avoid; }"
                    )

        if page_css:
            css_blocks.append(page_css)
        if container_css:
            css_blocks.append(container_css)

        # Append Pygments CSS if we used highlighting
        if pygments_css:
            css_blocks.append(pygments_css)
        # If theme defines a background-color for code/pre, also force it on .highlight wrappers
        code_bg: Optional[str] = None
        if isinstance(self.theme, Theme):
            try:
                # Prefer format-specific, then base
                st = None
                html_fmt = self.theme.formats.get('html') if isinstance(self.theme.formats, dict) else None
                if html_fmt and hasattr(html_fmt, 'styles'):
                    st = (html_fmt.styles.get('pre') or html_fmt.styles.get('code'))
                if not st:
                    st = (self.theme.styles.get('pre') or self.theme.styles.get('code'))
                if st and getattr(st, 'background_color', None):
                    code_bg = str(st.background_color)
            except Exception:
                code_bg = None
        if code_bg:
            css_blocks.append(
                ".highlight { background: %s !important; }\n.highlight pre { background: %s !important; }" % (code_bg, code_bg)
            )

        css_text = "\n\n".join(css_blocks) if css_blocks else ""

        # Build full HTML document
        lang = "en"
        if isinstance(self.theme, Theme):
            try:
                lang = str(self.theme.meta.get('lang', lang))
            except Exception:
                pass
        title = None
        if isinstance(self.theme, Theme):
            try:
                title = self.theme.meta.get('title')
            except Exception:
                title = None
        if not title:
            title = title_text or "Document"

        head_parts = [
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
        ]
        if css_text:
            head_parts.append(f"<style>\n{css_text}\n</style>")
        head_parts.append(f"<title>{self._escape_html(title)}</title>")

        full_html = (
            "<!DOCTYPE html>\n"
            f"<html lang=\"{self._escape_html(lang)}\">\n"
            "<head>\n" + "\n".join(head_parts) + "\n</head>\n"
            "<body>\n" + body_fragment + "\n</body>\n"
            "</html>\n"
        )

        return full_html.encode('utf-8')

    def convert(self, md_text: str) -> bytes:  # type: ignore[override]
        import io as _io
        return self.convert_stream(_io.StringIO(md_text))

    # no separate mermaid extraction needed — handled during streaming parse

    def _wrap_code_block(self, code: str, lang: str) -> str:
        return f"<pre><code class=\"language-{lang}\">{self._escape_html(code)}</code></pre>"

    def _escape_html(self, text: str) -> str:
        return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def _render_inline_span_html(self, span) -> str:
        # span is mdparser.InlineSpan
        txt = self._escape_html(span.text)
        if span.strike:
            txt = f"<del>{txt}</del>"
        if span.italic:
            txt = f"<em>{txt}</em>"
        if span.bold:
            txt = f"<strong>{txt}</strong>"
        return txt

    # Mermaid rendering now delegated to embeds.default_diagram_service

class DocxConverter(Converter):
    """Convert Markdown to DOCX bytes using a streaming Markdown IR.

    Supported blocks: headings, paragraphs, code blocks, lists, images, tables, inline SVG.
    Mermaid code blocks are rendered to images (SVG preferred, PNG fallback) via mermaid-cli.
    """

    def convert_stream(self, lines: Iterable[str]) -> bytes:
        from docx import Document
        from docx.shared import Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from .mdparser import (
            parse_markdown_stream,
            Heading as IRHeading,
            Paragraph as IRParagraph,
            CodeBlock as IRCode,
            ListBlock as IRList,
            Image as IRImage,
            SvgBlock as IRSvg,
            Table as IRTable,
            parse_inline_emphasis,
        )

        document = Document()
        if self.theme and isinstance(self.theme, Theme):
            try:
                self.theme.apply_to_docx(document)
            except Exception:
                pass

        for block in parse_markdown_stream(lines=lines):
            if isinstance(block, IRHeading):
                level = max(1, min(6, block.level))
                try:
                    p = document.add_paragraph(style=f"Heading {level}")
                except Exception:
                    p = document.add_paragraph()
                self._append_inline_runs_docx(p, parse_inline_emphasis(block.text))
            elif isinstance(block, IRParagraph):
                p = document.add_paragraph()
                self._append_inline_runs_docx(p, parse_inline_emphasis(block.text))
            elif isinstance(block, IRCode):
                if (block.language or '').lower() == 'mermaid':
                    rr: Optional[RenderResult] = None
                    try:
                        rr = default_diagram_service.render(
                            kind="mermaid",
                            code=block.code,
                            preferred_formats=["png", "jpeg", "svg"],
                        )
                    except Exception:
                        rr = None
                    if rr and rr.mime.startswith("image/"):
                        try:
                            document.add_picture(rr.path, width=Inches(6))
                        except Exception:
                            document.add_paragraph(block.code)
                        finally:
                            rr.cleanup()
                    else:
                        document.add_paragraph(block.code)
                else:
                    # Attempt Pygments highlighting for DOCX when a language is specified
                    lang = (block.language or '').strip()
                    used_highlight = False
                    if lang:
                        try:
                            from pygments import lex  # type: ignore
                            from pygments.lexers import get_lexer_by_name  # type: ignore
                            from pygments.styles import get_style_by_name  # type: ignore
                            from pygments.token import Token  # type: ignore
                            # Choose style from theme if set
                            style_name = None
                            if isinstance(self.theme, Theme):
                                fmt = self.theme.formats.get('docx') if isinstance(self.theme.formats, dict) else None
                                if fmt and getattr(fmt, 'pygments_style', None):
                                    style_name = fmt.pygments_style  # type: ignore[attr-defined]
                                if not style_name and getattr(self.theme, 'pygments_style', None):
                                    style_name = self.theme.pygments_style  # type: ignore[attr-defined]
                            style = get_style_by_name(style_name) if style_name else get_style_by_name('default')
                            lexer = get_lexer_by_name(lang)
                            p = document.add_paragraph()
                            # Apply background shading from theme if defined
                            try:
                                code_bg = None
                                if isinstance(self.theme, Theme):
                                    fmt = self.theme.formats.get('docx') if isinstance(self.theme.formats, dict) else None
                                    st = None
                                    if fmt and hasattr(fmt, 'styles'):
                                        st = (fmt.styles.get('pre') or fmt.styles.get('code'))
                                    if not st:
                                        st = (self.theme.styles.get('pre') or self.theme.styles.get('code'))
                                    if st and getattr(st, 'background_color', None):
                                        code_bg = str(st.background_color)
                                if code_bg:
                                    r = int(code_bg.lstrip('#')[0:2], 16); g = int(code_bg.lstrip('#')[2:4], 16); b = int(code_bg.lstrip('#')[4:6], 16)
                                    # Best-effort: use paragraph shading via XML
                                    p._element.get_or_add_pPr().get_or_add_shd().val = 'clear'
                                    p._element.get_or_add_pPr().get_or_add_shd().color = 'auto'
                                    p._element.get_or_add_pPr().get_or_add_shd().fill = f"{r:02X}{g:02X}{b:02X}"
                            except Exception:
                                pass
                            for ttype, value in lex(block.code, lexer):
                                if not value:
                                    continue
                                # Resolve nearest style in hierarchy
                                tt = ttype
                                while tt and tt not in style.styles:
                                    tt = tt.parent
                                style_str = style.styles.get(tt, '')
                                bold = 'bold' in style_str
                                italic = 'italic' in style_str
                                color = None
                                m = re.search(r"#([0-9a-fA-F]{6})", style_str)
                                if m:
                                    color = m.group(1)
                                parts_txt = value.split('\n')
                                for i, seg in enumerate(parts_txt):
                                    if seg:
                                        run = p.add_run(seg)
                                        try:
                                            run.font.name = 'Courier New'
                                        except Exception:
                                            pass
                                        if bold:
                                            run.bold = True
                                        if italic:
                                            run.italic = True
                                        if color:
                                            try:
                                                from docx.shared import RGBColor  # type: ignore
                                                r = int(color[0:2], 16); g = int(color[2:4], 16); b = int(color[4:6], 16)
                                                run.font.color.rgb = RGBColor(r, g, b)
                                            except Exception:
                                                pass
                                    if i < len(parts_txt) - 1:
                                        try:
                                            p.add_run().add_break()
                                        except Exception:
                                            pass
                            used_highlight = True
                        except Exception:
                            used_highlight = False
                    if not used_highlight:
                        p = document.add_paragraph(block.code)
                        # Apply background if configured
                        try:
                            code_bg = None
                            if isinstance(self.theme, Theme):
                                fmt = self.theme.formats.get('docx') if isinstance(self.theme.formats, dict) else None
                                st = None
                                if fmt and hasattr(fmt, 'styles'):
                                    st = (fmt.styles.get('pre') or fmt.styles.get('code'))
                                if not st:
                                    st = (self.theme.styles.get('pre') or self.theme.styles.get('code'))
                                if st and getattr(st, 'background_color', None):
                                    code_bg = str(st.background_color)
                            if code_bg:
                                r = int(code_bg.lstrip('#')[0:2], 16); g = int(code_bg.lstrip('#')[2:4], 16); b = int(code_bg.lstrip('#')[4:6], 16)
                                p._element.get_or_add_pPr().get_or_add_shd().val = 'clear'
                                p._element.get_or_add_pPr().get_or_add_shd().color = 'auto'
                                p._element.get_or_add_pPr().get_or_add_shd().fill = f"{r:02X}{g:02X}{b:02X}"
                        except Exception:
                            pass
            elif isinstance(block, IRList):
                style = "List Number" if block.ordered else "List Bullet"
                for item in block.items:
                    try:
                        p = document.add_paragraph(style=style)
                    except Exception:
                        p = document.add_paragraph()
                    self._append_inline_runs_docx(p, parse_inline_emphasis(item.text))
            elif isinstance(block, IRImage):
                src = block.src
                try:
                    from .media import MediaFetcher

                    fetcher = MediaFetcher()
                    res = fetcher.fetch(src)
                    if res:
                        try:
                            document.add_picture(res.path, width=Inches(6))
                        except Exception:
                            pass
                        # cleanup non-cached temporary files
                        if not res.cached:
                            try:
                                os.unlink(res.path)
                            except Exception:
                                pass
                except Exception:
                    # ignore image failures; continue with other content
                    pass
            elif isinstance(block, IRSvg):
                try:
                    svg_bytes = block.svg.encode('utf-8')
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.svg')
                    tmp.write(svg_bytes)
                    tmp.flush()
                    document.add_picture(tmp.name, width=Inches(6))
                    os.unlink(tmp.name)
                except Exception:
                    pass
            elif isinstance(block, IRTable):
                # Create a table with header row + body rows
                cols = max(1, len(block.headers))
                rows = 1 + len(block.rows)
                table = document.add_table(rows=rows, cols=cols)
                # Header row with inline emphasis (force bold weight on header spans)
                hdr_cells = table.rows[0].cells
                from .mdparser import parse_inline_emphasis as _pie
                for i, text in enumerate(block.headers):
                    p = hdr_cells[i].paragraphs[0]
                    spans = _pie(text)
                    if spans:
                        for s in spans:
                            run = p.add_run(s.text)
                            try:
                                run.bold = True or s.bold  # header cells are bold by default
                                run.italic = bool(s.italic)
                                if s.strike:
                                    run.font.strike = True
                            except Exception:
                                pass
                    else:
                        run = p.add_run(text)
                        try:
                            run.bold = True
                        except Exception:
                            pass
                    # alignment for header based on aligns if provided
                    try:
                        align = block.aligns[i] if i < len(block.aligns) else None
                        if align == 'center':
                            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        elif align == 'right':
                            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        elif align == 'left':
                            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    except Exception:
                        pass
                # Body rows
                for r_idx, row_vals in enumerate(block.rows, start=1):
                    cells = table.rows[r_idx].cells
                    for c_idx in range(cols):
                        val = row_vals[c_idx] if c_idx < len(row_vals) else ''
                        p = cells[c_idx].paragraphs[0]
                        # clear any default text
                        if getattr(p, 'clear', None):
                            try:
                                p.clear()
                            except Exception:
                                pass
                        spans = _pie(val)
                        if spans:
                            self._append_inline_runs_docx(p, spans)
                        else:
                            p.text = val
                        try:
                            align = block.aligns[c_idx] if c_idx < len(block.aligns) else None
                            if align == 'center':
                                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            elif align == 'right':
                                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                            elif align == 'left':
                                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        except Exception:
                            pass

        bio = io.BytesIO()
        document.save(bio)
        return bio.getvalue()

    def convert(self, md_text: str) -> bytes:  # type: ignore[override]
        import io as _io
        return self.convert_stream(_io.StringIO(md_text))

    def _append_inline_runs_docx(self, paragraph, spans):
        try:
            for s in spans:
                run = paragraph.add_run(s.text)
                if s.bold:
                    run.bold = True
                if s.italic:
                    run.italic = True
                if s.strike:
                    run.font.strike = True
        except Exception:
            # Best-effort; if something goes wrong, fall back to plain text
            if getattr(paragraph, 'add_run', None):
                paragraph.add_run("".join(s.text for s in spans))

    # Per-converter Mermaid image rendering removed in favor of shared service

def get_converter(format_name: str, theme: Optional[Union[str, Theme]] = None, **opts) -> Converter:
    fmt = format_name.lower()
    if fmt == "html":
        return HtmlConverter(theme)
    if fmt == "docx":
        return DocxConverter(theme)
    if fmt == "pptx":
        return PptxConverter(theme)
    if fmt == "pdf":
        return PdfConverter(theme)
    raise NotImplementedError(f"No converter implemented for format: {format_name}")


class PptxConverter(Converter):
    """Convert Markdown into a simple PPTX presentation.

    Strategy:
    - H1/H2 start a new slide (Title and Content), title set from heading text.
    - Paragraphs and list items go into the slide's content text frame as bullets.
    - Code blocks are added as monospace text in a separate textbox.
    - Mermaid blocks are rendered via DiagramService and inserted as images when available.
    - Images are fetched via MediaFetcher and inserted; cleaned up if temporary.
    - Tables are added using python-pptx table shapes.
    """

    def convert_stream(self, lines: Iterable[str]) -> bytes:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN
        from .mdparser import (
            parse_markdown_stream,
            Heading as IRHeading,
            Paragraph as IRParagraph,
            CodeBlock as IRCode,
            ListBlock as IRList,
            Image as IRImage,
            SvgBlock as IRSvg,
            Table as IRTable,
            parse_inline_emphasis,
        )

        pres = Presentation()
        # Apply theme styles best-effort
        if self.theme and isinstance(self.theme, Theme):
            try:
                self.theme.apply_to_pptx(pres)
            except Exception:
                pass

        # Helpers to manage slide/content
        def new_content_slide(title_text: str = ""):
            layout_idx = 1 if len(pres.slide_layouts) > 1 else 0  # Title and Content fallback to Title
            slide = pres.slides.add_slide(pres.slide_layouts[layout_idx])
            try:
                if slide.shapes.title is not None and title_text:
                    slide.shapes.title.text = title_text
            except Exception:
                pass
            # Find content placeholder (usually index 1)
            content_tf = None
            try:
                for shape in slide.shapes:
                    if getattr(shape, 'has_text_frame', False) and shape.text_frame is not None and shape is not slide.shapes.title:
                        content_tf = shape.text_frame
                        break
            except Exception:
                content_tf = None
            return slide, content_tf

        def add_text_paragraph(tf, text: str, level: int = 0):
            if tf is None:
                return
            # If frame already has default empty paragraph, reuse it if empty
            if not tf.paragraphs:
                p = tf.add_paragraph()
            else:
                p = tf.paragraphs[-1]
                if p.text:
                    p = tf.add_paragraph()
            p.level = max(0, min(5, level))
            # Inline emphasis into runs
            spans = parse_inline_emphasis(text)
            # clear any auto text in paragraph
            try:
                if getattr(p, 'clear', None):
                    p.clear()
            except Exception:
                pass
            if not spans:
                p.text = text
            else:
                for s in spans:
                    run = p.add_run()
                    run.text = s.text
                    try:
                        if s.bold:
                            run.font.bold = True
                        if s.italic:
                            run.font.italic = True
                        if s.strike:
                            run.font.strike = True
                    except Exception:
                        pass

        current_slide = None
        current_tf = None
        title_set = False

        for block in parse_markdown_stream(lines=lines):
            if isinstance(block, IRHeading):
                lvl = max(1, min(6, block.level))
                if lvl <= 2:
                    current_slide, current_tf = new_content_slide(block.text)
                    title_set = True
                else:
                    if current_slide is None:
                        current_slide, current_tf = new_content_slide()
                    # Add sub-heading as bold line
                    add_text_paragraph(current_tf, f"**{block.text}**", level=0)
            elif isinstance(block, IRParagraph):
                if current_slide is None:
                    current_slide, current_tf = new_content_slide("Document")
                add_text_paragraph(current_tf, block.text, level=0)
            elif isinstance(block, IRList):
                if current_slide is None:
                    current_slide, current_tf = new_content_slide("Document")
                for item in block.items:
                    add_text_paragraph(current_tf, item.text, level=1 if not block.ordered else 0)
            elif isinstance(block, IRCode):
                # Mermaid rendering to image if possible
                if (block.language or '').lower() == 'mermaid':
                    rr: Optional[RenderResult] = None
                    try:
                        rr = default_diagram_service.render(
                            kind="mermaid", code=block.code, preferred_formats=["png", "jpeg", "svg"],
                        )
                    except Exception:
                        rr = None
                    if rr and rr.mime.startswith("image/"):
                        if current_slide is None:
                            current_slide, current_tf = new_content_slide("Diagram")
                        try:
                            left = Inches(1)
                            top = Inches(1.5)
                            width = Inches(8)
                            current_slide.shapes.add_picture(rr.path, left, top, width=width)
                        except Exception:
                            # fallback: add code text
                            add_text_paragraph(current_tf, block.code, level=0)
                        finally:
                            rr.cleanup()
                    else:
                        if current_slide is None:
                            current_slide, current_tf = new_content_slide("Code")
                        add_text_paragraph(current_tf, block.code, level=0)
                else:
                    if current_slide is None:
                        current_slide, current_tf = new_content_slide("Code")
                    # Add as monospace in a textbox with simple Pygments colors if available
                    try:
                        left, top, width, height = Inches(1), Inches(1.5), Inches(8), Inches(2.5)
                        tx_box = current_slide.shapes.add_textbox(left, top, width, height)
                        # Apply background color from theme to textbox fill if defined
                        try:
                            code_bg = None
                            if isinstance(self.theme, Theme):
                                fmt = self.theme.formats.get('pptx') if isinstance(self.theme.formats, dict) else None
                                st = None
                                if fmt and hasattr(fmt, 'styles'):
                                    st = (fmt.styles.get('pre') or fmt.styles.get('code'))
                                if not st:
                                    st = (self.theme.styles.get('pre') or self.theme.styles.get('code'))
                                if st and getattr(st, 'background_color', None):
                                    code_bg = str(st.background_color)
                            if code_bg:
                                from pptx.dml.color import RGBColor as PPTXRGB  # type: ignore
                                fill = tx_box.fill
                                fill.solid()
                                r = int(code_bg.lstrip('#')[0:2], 16); g = int(code_bg.lstrip('#')[2:4], 16); b = int(code_bg.lstrip('#')[4:6], 16)
                                fill.fore_color.rgb = PPTXRGB(r, g, b)
                        except Exception:
                            pass
                        tf = tx_box.text_frame
                        tf.word_wrap = True
                        used_highlight = False
                        lang = (block.language or '').strip()
                        if lang:
                            try:
                                from pygments import lex  # type: ignore
                                from pygments.lexers import get_lexer_by_name  # type: ignore
                                from pygments.styles import get_style_by_name  # type: ignore
                                lexer = get_lexer_by_name(lang)
                                style_name = None
                                if isinstance(self.theme, Theme):
                                    fmt = self.theme.formats.get('pptx') if isinstance(self.theme.formats, dict) else None
                                    if fmt and getattr(fmt, 'pygments_style', None):
                                        style_name = fmt.pygments_style  # type: ignore[attr-defined]
                                    if not style_name and getattr(self.theme, 'pygments_style', None):
                                        style_name = self.theme.pygments_style  # type: ignore[attr-defined]
                                style = get_style_by_name(style_name) if style_name else get_style_by_name('default')
                                # Create one paragraph and add runs for tokens, breaking lines as needed
                                p = tf.paragraphs[-1] if tf.paragraphs else tf.add_paragraph()
                                # Clear paragraph if it contains auto text
                                try:
                                    if getattr(p, 'clear', None):
                                        p.clear()
                                except Exception:
                                    pass
                                from pptx.dml.color import RGBColor as PPTXRGB  # type: ignore
                                for ttype, value in lex(block.code, lexer):
                                    if value == "":
                                        continue
                                    # Find nearest style
                                    tt = ttype
                                    while tt and tt not in style.styles:
                                        tt = tt.parent
                                    style_str = style.styles.get(tt, '')
                                    bold = 'bold' in style_str
                                    italic = 'italic' in style_str
                                    color = None
                                    m = re.search(r"#([0-9a-fA-F]{6})", style_str)
                                    if m:
                                        color = m.group(1)
                                    segments = value.split('\n')
                                    for i, seg in enumerate(segments):
                                        if seg:
                                            run = p.add_run()
                                            run.text = seg
                                            try:
                                                run.font.name = 'Courier New'
                                            except Exception:
                                                pass
                                            if bold:
                                                run.font.bold = True
                                            if italic:
                                                run.font.italic = True
                                            if color:
                                                try:
                                                    r = int(color[0:2], 16); g = int(color[2:4], 16); b = int(color[4:6], 16)
                                                    run.font.color.rgb = PPTXRGB(r, g, b)
                                                except Exception:
                                                    pass
                                        if i < len(segments) - 1:
                                            p = tf.add_paragraph()
                                            p.level = 0
                                    used_highlight = True
                            except Exception:
                                used_highlight = False
                        if not used_highlight:
                            add_text_paragraph(tf, block.code, level=0)
                    except Exception:
                        add_text_paragraph(current_tf, block.code, level=0)
            elif isinstance(block, IRImage):
                try:
                    from .media import MediaFetcher
                    if current_slide is None:
                        current_slide, current_tf = new_content_slide("Image")
                    fetcher = MediaFetcher()
                    res = fetcher.fetch(block.src)
                    if res:
                        try:
                            left, top, width = Inches(1), Inches(1.5), Inches(8)
                            current_slide.shapes.add_picture(res.path, left, top, width=width)
                        except Exception:
                            pass
                        if not res.cached:
                            try:
                                os.unlink(res.path)
                            except Exception:
                                pass
                except Exception:
                    pass
            elif isinstance(block, IRSvg):
                # python-pptx doesn't support SVG directly; add a note
                if current_slide is None:
                    current_slide, current_tf = new_content_slide("Diagram")
                add_text_paragraph(current_tf, "[SVG diagram not supported in PPTX]", level=0)
            elif isinstance(block, IRTable):
                # Add a simple table on a new or current slide
                if current_slide is None:
                    current_slide, current_tf = new_content_slide("Table")
                try:
                    rows = 1 + len(block.rows)
                    cols = max(1, len(block.headers))
                    left, top, width, height = Inches(0.75), Inches(1.5), Inches(9), Inches(3)
                    table_shape = current_slide.shapes.add_table(rows, cols, left, top, width, height)
                    table = table_shape.table
                    # headers
                    for c in range(cols):
                        txt = block.headers[c] if c < len(block.headers) else ''
                        cell = table.cell(0, c)
                        cell.text = txt
                    # body
                    for r_idx, row_vals in enumerate(block.rows, start=1):
                        for c in range(cols):
                            val = row_vals[c] if c < len(row_vals) else ''
                            table.cell(r_idx, c).text = val
                except Exception:
                    add_text_paragraph(current_tf, "[Table omitted due to PPTX error]", level=0)

        # If nothing was added, ensure one slide exists
        if len(pres.slides) == 0:
            current_slide, current_tf = new_content_slide("Document")
            add_text_paragraph(current_tf, "(Empty)", level=0)

        bio = io.BytesIO()
        pres.save(bio)
        return bio.getvalue()


class PdfConverter(Converter):
    """Convert Markdown to PDF using Playwright (Chromium) to render HTML to PDF.

    Requirements: playwright installed and Chromium downloaded.
    If Playwright is not available, raise a RuntimeError with install guidance.
    """

    def convert_stream(self, lines: Iterable[str]) -> bytes:
        # Render HTML first for consistent theming and assets
        html_bytes = HtmlConverter(self.theme).convert_stream(lines)
        html_str = html_bytes.decode("utf-8", errors="replace")
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception:
            guidance = (
                "Playwright is not installed. To enable PDF export, run:\n"
                "  pip install playwright\n"
                "  python -m playwright install chromium\n"
                "This uses a headless Chromium to print HTML to PDF with full CSS/SVG support."
            )
            raise RuntimeError(guidance)

        base_url = f"file://{os.getcwd().rstrip('/')}/"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])  # --no-sandbox for container CI
                context = browser.new_context()
                page = context.new_page()
                page.set_content(html_str, wait_until="load", base_url=base_url)
                # prefer_css_page_size honors @page size from theme CSS
                pdf_bytes = page.pdf(print_background=True, prefer_css_page_size=True)
                context.close()
                browser.close()
        except Exception:
            guidance = (
                "Playwright browser not available. To enable PDF export, run:\n"
                "  pip install playwright\n"
                "  python -m playwright install chromium\n"
                "This uses a headless Chromium to print HTML to PDF with full CSS/SVG support."
            )
            raise RuntimeError(guidance)
        return pdf_bytes
