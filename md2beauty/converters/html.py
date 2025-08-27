from __future__ import annotations

from typing import Optional, Union, Iterable
import re

from ..theme import Theme
from .. import is_debug
from ..mdparser import parse_markdown_stream
from ..embeds import default_diagram_service, RenderResult
from . import Converter


class HtmlConverter(Converter):
    def __init__(self, theme: Optional[Union[str, Theme]] = None):
        super().__init__(theme)

    def convert_stream(self, lines: Iterable[str]) -> bytes:
        parts: list[str] = []
        from ..mdparser import (
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
                if (block.language or '').strip().lower() == 'mermaid':
                    rr: Optional[RenderResult] = None
                    try:
                        rr = default_diagram_service.render(
                            kind="mermaid",
                            code=block.code,
                            preferred_formats=["svg", "png"],
                        )
                    except Exception:
                        if is_debug():
                            raise
                        rr = None
                        raise
                    if rr:
                        mime = (rr.mime or "").lower()
                        try:
                            if mime.startswith("image/svg") or rr.path.lower().endswith(".svg"):
                                # Inline SVG so it inherits CSS and scales properly
                                with open(rr.path, "r", encoding="utf-8") as f:
                                    parts.append(f.read())
                            elif mime.startswith("image/"):
                                # Fallback: embed raster output as base64 data URI
                                with open(rr.path, "rb") as f:
                                    import base64 as _b64
                                    data = _b64.b64encode(f.read()).decode("ascii")
                                    parts.append(
                                        f"<img src=\"data:{rr.mime};base64,{data}\" alt=\"mermaid diagram\"/>"
                                    )
                            else:
                                parts.append(self._wrap_code_block(block.code, 'mermaid'))
                        finally:
                            rr.cleanup()
                    else:
                        parts.append(self._wrap_code_block(block.code, 'mermaid'))
                else:
                    lang = (block.language or '').strip()
                    highlighted_html: Optional[str] = None
                    if lang:
                        try:
                            from pygments import highlight  # type: ignore
                            from pygments.lexers import get_lexer_by_name  # type: ignore
                            from pygments.formatters import HtmlFormatter  # type: ignore
                            try:
                                lexer = get_lexer_by_name(lang)
                            except Exception:
                                lexer = get_lexer_by_name('text')
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
                    from ..mdparser import parse_inline_emphasis as _pie
                    spans = _pie(item.text)
                    inner = "".join(self._render_inline_span_html(s) for s in spans) if spans else self._escape_html(item.text)
                    parts.append(f"<li>{inner}</li>")
                parts.append(f"</{tag}>")
            elif isinstance(block, IRImage):
                parts.append(f"<img src=\"{self._escape_html(block.src)}\" alt=\"{self._escape_html(block.alt)}\" />")
            elif isinstance(block, IRSvg):
                parts.append(block.svg)
            elif isinstance(block, IRHr):
                parts.append("<hr />")
            elif isinstance(block, IRTable):
                from ..mdparser import parse_inline_emphasis as _pie
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
            css_blocks.append(self.theme.to_css())
            page_cfg: dict = {}
            if getattr(self.theme, 'page', None):
                page_cfg.update(self.theme.page.model_dump(exclude_unset=True))  # type: ignore[attr-defined]
            html_fmt = self.theme.formats.get('html') if isinstance(self.theme.formats, dict) else None
            if html_fmt and getattr(html_fmt, 'page', None):
                page_cfg.update(html_fmt.page.model_dump(exclude_unset=True))  # type: ignore[attr-defined]
            if page_cfg:
                ptype = str(page_cfg.get('type', '')).strip().lower()
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
                    if re.match(r"^\d+(?:\.\d+)?(px|pt|in|mm|cm)$", s):
                        return s
                    if re.match(r"^\d+(?:\.\d+)?$", s):
                        return s + 'in'
                    return default
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
                if page_size_keyword:
                    page_css = f"@page { '{' } size: {page_size_keyword}; margin: {m_top} {m_right} {m_bottom} {m_left}; {'}'}"
                elif page_width and page_height:
                    page_css = f"@page { '{' } size: {page_width} {page_height}; margin: {m_top} {m_right} {m_bottom} {m_left}; {'}'}"
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

        code_bg: Optional[str] = None
        if isinstance(self.theme, Theme):
            try:
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

        if pygments_css:
            css_blocks.append(pygments_css)

        css_text = "\n\n".join(css_blocks) if css_blocks else ""

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

    def _wrap_code_block(self, code: str, lang: str) -> str:
        return f"<pre><code class=\"language-{lang}\">{self._escape_html(code)}</code></pre>"

    def _escape_html(self, text: str) -> str:
        return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def _render_inline_span_html(self, span) -> str:
        txt = self._escape_html(span.text)
        if span.strike:
            txt = f"<del>{txt}</del>"
        if span.italic:
            txt = f"<em>{txt}</em>"
        if span.bold:
            txt = f"<strong>{txt}</strong>"
        return txt
