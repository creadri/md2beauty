from __future__ import annotations

from typing import Optional, Union, Iterable
import re
import shutil
import subprocess
import tempfile
import os
import pathlib
import hashlib
import base64
import logging
import io

from .theme import Theme
from .mdparser import parse_markdown_stream


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
        )
        title_text: Optional[str] = None

        for block in parse_markdown_stream(lines=lines):
            if isinstance(block, IRHeading):
                lvl = max(1, min(6, block.level))
                parts.append(f"<h{lvl}>{self._escape_html(block.text)}</h{lvl}>")
                if title_text is None:
                    title_text = block.text.strip()
            elif isinstance(block, IRParagraph):
                parts.append(f"<p>{self._escape_html(block.text)}</p>")
            elif isinstance(block, IRCode):
                if block.language == 'mermaid':
                    svg = self._render_mermaid_to_svg(block.code)
                    parts.append(svg if svg else self._wrap_code_block(block.code, 'mermaid'))
                else:
                    parts.append(f"<pre><code>{self._escape_html(block.code)}</code></pre>")
            elif isinstance(block, IRList):
                tag = 'ol' if block.ordered else 'ul'
                parts.append(f"<{tag}>")
                for item in block.items:
                    parts.append(f"<li>{self._escape_html(item.text)}</li>")
                parts.append(f"</{tag}>")
            elif isinstance(block, IRImage):
                parts.append(f"<img src=\"{self._escape_html(block.src)}\" alt=\"{self._escape_html(block.alt)}\" />")
            elif isinstance(block, IRSvg):
                parts.append(block.svg)
            elif isinstance(block, IRHr):
                parts.append("<hr />")
            elif isinstance(block, IRTable):
                # Basic table rendering with alignment styles
                def _td_style(align: Optional[str]) -> str:
                    return f' style="text-align: {align};"' if align in ("left", "center", "right") else ''
                thead = "<thead><tr>" + "".join(
                    f"<th{_td_style(block.aligns[i] if i < len(block.aligns) else None)}>{self._escape_html(h)}</th>"
                    for i, h in enumerate(block.headers)
                ) + "</tr></thead>"
                tbody_rows = []
                for row in block.rows:
                    tds = []
                    for i, cell in enumerate(row):
                        tds.append(f"<td{_td_style(block.aligns[i] if i < len(block.aligns) else None)}>{self._escape_html(cell)}</td>")
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

    def _render_mermaid_to_svg(self, mermaid_text: str) -> Optional[str]:
        """Try to render mermaid diagram to SVG using mermaid-cli (mmdc) or npx.

        Returns an inline SVG string, or an <img> data-uri PNG fallback, or None on failure.
        """
        logger = logging.getLogger("md2beauty.mermaid")

        project_root = pathlib.Path(__file__).resolve().parents[1]
        local_mmdc = project_root / "node_modules" / ".bin" / "mmdc"

        mmdc_exe = shutil.which("mmdc")
        if not mmdc_exe and local_mmdc.exists():
            mmdc_exe = str(local_mmdc)

        npx_exe = shutil.which("npx")

        if not mmdc_exe and not npx_exe:
            logger.debug("No mmdc or npx found for mermaid rendering")
            return None

        # cache by hash
        cache_dir = project_root / ".cache" / "md2beauty"
        cache_dir.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256(mermaid_text.encode("utf-8")).hexdigest()
        cached_svg = cache_dir / f"{h}.svg"
        cached_png = cache_dir / f"{h}.png"
        if cached_svg.exists():
            logger.debug("Using cached mermaid svg %s", cached_svg)
            return cached_svg.read_text(encoding="utf-8")
        if cached_png.exists():
            logger.debug("Using cached mermaid png %s", cached_png)
            data = base64.b64encode(cached_png.read_bytes()).decode("ascii")
            return f"<img src=\"data:image/png;base64,{data}\" alt=\"mermaid diagram\"/>"

        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "diagram.mmd")
            out_svg = os.path.join(tmpdir, "diagram.svg")
            out_png = os.path.join(tmpdir, "diagram.png")
            with open(in_path, "w", encoding="utf-8") as f:
                f.write(mermaid_text)

            # try SVG first
            try:
                if mmdc_exe:
                    cmd = [mmdc_exe, "-i", in_path, "-o", out_svg]
                else:
                    cmd = [npx_exe, "@mermaid-js/mermaid-cli", "-i", in_path, "-o", out_svg]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.path.exists(out_svg):
                    svg = open(out_svg, "r", encoding="utf-8").read()
                    try:
                        cached_svg.write_text(svg, encoding="utf-8")
                    except Exception:
                        logger.debug("Failed to write svg cache")
                    return svg
            except Exception as e:
                logger.debug("SVG render failed: %s", e)

            # try PNG fallback
            try:
                if mmdc_exe:
                    cmd = [mmdc_exe, "-i", in_path, "-o", out_png]
                else:
                    cmd = [npx_exe, "@mermaid-js/mermaid-cli", "-i", in_path, "-o", out_png]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.path.exists(out_png):
                    png_bytes = open(out_png, "rb").read()
                    try:
                        cached_png.write_bytes(png_bytes)
                    except Exception:
                        logger.debug("Failed to write png cache")
                    data = base64.b64encode(png_bytes).decode("ascii")
                    return f"<img src=\"data:image/png;base64,{data}\" alt=\"mermaid diagram\"/>"
            except Exception as e:
                logger.debug("PNG render failed: %s", e)

        return None

class DocxConverter(Converter):
    """Convert Markdown to DOCX bytes using a streaming Markdown IR.

    Supported blocks: headings, paragraphs, code blocks, lists, images, tables, inline SVG.
    Mermaid code blocks are rendered to images (SVG preferred, PNG fallback) via mermaid-cli.
    """

    def convert_stream(self, lines: Iterable[str]) -> bytes:
        from docx import Document
        from docx.shared import Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from .mdparser import parse_markdown_stream, Heading as IRHeading, Paragraph as IRParagraph, CodeBlock as IRCode, ListBlock as IRList, Image as IRImage, SvgBlock as IRSvg, Table as IRTable

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
                    document.add_paragraph(block.text, style=f"Heading {level}")
                except Exception:
                    document.add_paragraph(block.text)
            elif isinstance(block, IRParagraph):
                document.add_paragraph(block.text)
            elif isinstance(block, IRCode):
                if (block.language or '').lower() == 'mermaid':
                    try:
                        img_path = self._render_mermaid_to_image(block.code)
                    except Exception:
                        img_path = None
                    if img_path and os.path.exists(img_path):
                        try:
                            document.add_picture(img_path, width=Inches(6))
                        except Exception:
                            # fallback to code paragraph if image insertion fails
                            document.add_paragraph(block.code)
                        finally:
                            try:
                                os.unlink(img_path)
                            except Exception:
                                pass
                    else:
                        document.add_paragraph(block.code)
                else:
                    document.add_paragraph(block.code)
            elif isinstance(block, IRList):
                style = "List Number" if block.ordered else "List Bullet"
                for item in block.items:
                    try:
                        document.add_paragraph(item.text, style=style)
                    except Exception:
                        document.add_paragraph(item.text)
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
                # Header row
                hdr_cells = table.rows[0].cells
                for i, text in enumerate(block.headers):
                    p = hdr_cells[i].paragraphs[0]
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

    def _render_mermaid_to_image(self, mermaid_text: str) -> Optional[str]:
        """Render mermaid text to a temporary image file (SVG preferred, PNG fallback).

        Returns a filesystem path to the image, or None on failure. Caller is responsible for deleting it.
        """
        project_root = pathlib.Path(__file__).resolve().parents[1]
        local_mmdc = project_root / "node_modules" / ".bin" / "mmdc"

        mmdc_exe = shutil.which("mmdc")
        if not mmdc_exe and local_mmdc.exists():
            mmdc_exe = str(local_mmdc)

        npx_exe = shutil.which("npx")

        if not mmdc_exe and not npx_exe:
            return None

        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "diagram.mmd")
            out_svg = os.path.join(tmpdir, "diagram.svg")
            out_png = os.path.join(tmpdir, "diagram.png")
            with open(in_path, "w", encoding="utf-8") as f:
                f.write(mermaid_text)

            # try SVG first
            try:
                if mmdc_exe:
                    cmd = [mmdc_exe, "-i", in_path, "-o", out_svg]
                else:
                    cmd = [npx_exe, "@mermaid-js/mermaid-cli", "-i", in_path, "-o", out_svg]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.path.exists(out_svg):
                    data = open(out_svg, "rb").read()
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.svg')
                    tmp.write(data)
                    tmp.flush()
                    tmp.close()
                    return tmp.name
            except Exception:
                pass

            # try PNG fallback
            try:
                if mmdc_exe:
                    cmd = [mmdc_exe, "-i", in_path, "-o", out_png]
                else:
                    cmd = [npx_exe, "@mermaid-js/mermaid-cli", "-i", in_path, "-o", out_png]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.path.exists(out_png):
                    data = open(out_png, "rb").read()
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    tmp.write(data)
                    tmp.flush()
                    tmp.close()
                    return tmp.name
            except Exception:
                pass

        return None

def get_converter(format_name: str, theme: Optional[Union[str, Theme]] = None, **opts) -> Converter:
    fmt = format_name.lower()
    if fmt == "html":
        return HtmlConverter(theme)
    if fmt == "docx":
        return DocxConverter(theme)
    # Placeholder for pptx converter
    raise NotImplementedError(f"No converter implemented for format: {format_name}")
