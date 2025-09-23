from __future__ import annotations

from typing import Optional, Union

from ..theme import Theme
from ..mdparser import parse_markdown, Document

class Converter:
    """Base converter.

    Previous versions relied on a streaming API (``convert_stream`` receiving an
    iterator of lines). Most converters actually need the full document
    structure, so we now parse the Markdown up-front into a lightweight IR
    (see ``mdparser.parse_markdown``) and expose a new hook
    ``convert_document(doc: Document)``.

    Backwards compatibility: subclasses overriding ``convert_stream`` only will
    continue to work; however new implementations should override
    ``convert_document`` instead.
    """

    def __init__(self, theme: Optional[Union[str, Theme, dict]] = None):
        if theme is None or isinstance(theme, Theme):
            self.theme = theme
        elif isinstance(theme, dict):
            self.theme = Theme.from_dict(theme)
        else:
            self.theme = Theme.from_json_file(theme)

    # New primary API
    def convert(self, md_text: str) -> bytes:
        doc: Document = parse_markdown(md_text)
        return self.convert_document(doc)

    # New hook
    def convert_document(self, doc: Document) -> bytes:  # pragma: no cover - interface
        # Default fallback uses old streaming method if subclass provided it.
        if hasattr(self, "convert_stream") and callable(getattr(self, "convert_stream")):
            import io as _io
            # Recreate original streaming behavior for legacy subclasses
            return self.convert_stream(_io.StringIO("\n".join(
                self._serialize_block_as_markdown(b) for b in doc.blocks
            )))  # type: ignore[attr-defined]
        raise NotImplementedError("Subclass must implement convert_document")

    # Legacy hook (kept for backward compatibility)
    def convert_stream(self, lines):  # pragma: no cover - legacy path
        raise NotImplementedError()

    # Minimal fallback serialization (lossy) used only if a legacy subclass relies on convert_stream
    def _serialize_block_as_markdown(self, block) -> str:
        from ..mdparser import Heading, Paragraph, CodeBlock, ListBlock, Image, SvgBlock, ThematicBreak, Table
        if isinstance(block, Heading):
            return f"{'#'*block.level} {block.text}"
        if isinstance(block, Paragraph):
            return block.text
        if isinstance(block, CodeBlock):
            fence = '```'
            lang = block.language or ''
            return f"{fence}{lang}\n{block.code}\n{fence}"
        if isinstance(block, ListBlock):
            bullet = ('1.' if block.ordered else '-')
            return '\n'.join(f"{i+1}. {it.text}" if block.ordered else f"- {it.text}" for i, it in enumerate(block.items))
        if isinstance(block, Image):
            return f"![{block.alt}]({block.src})"
        if isinstance(block, SvgBlock):
            return block.svg
        if isinstance(block, ThematicBreak):
            return '---'
        if isinstance(block, Table):
            header = '| ' + ' | '.join(block.headers) + ' |'
            divider = '| ' + ' | '.join('---' for _ in block.headers) + ' |'
            rows = ['| ' + ' | '.join(r) + ' |' for r in block.rows]
            return '\n'.join([header, divider] + rows)
        return ''


def get_converter(format_name: str, theme: Optional[Union[str, Theme]] = None, **opts) -> Converter:
    fmt = format_name.lower()
    if fmt == "html":
        from .html import HtmlConverter  # lazy import to avoid optional deps
        return HtmlConverter(theme)
    if fmt == "docx":
        from .docx import DocxConverter  # lazy import to avoid optional deps
        return DocxConverter(theme)
    if fmt == "pptx":
        from .pptx import PptxConverter  # lazy import to avoid optional deps
        return PptxConverter(theme)
    if fmt == "pdf":
        from .pdf import PdfConverter  # lazy import to avoid optional deps
        return PdfConverter(theme)
    raise NotImplementedError(f"No converter implemented for format: {format_name}")

__all__ = [
    "Converter",
    "get_converter",
    "HtmlConverter",
    "DocxConverter",
    "PptxConverter",
    "PdfConverter",
]


def __getattr__(name: str):  # lazy re-exports to keep optional deps optional
    if name == "HtmlConverter":
        from .html import HtmlConverter
        return HtmlConverter
    if name == "DocxConverter":
        from .docx import DocxConverter
        return DocxConverter
    if name == "PptxConverter":
        from .pptx import PptxConverter
        return PptxConverter
    if name == "PdfConverter":
        from .pdf import PdfConverter
        return PdfConverter
    raise AttributeError(name)
