from __future__ import annotations

from typing import Optional, Union

from ..theme import Theme

class Converter:
    def __init__(self, theme: Optional[Union[str, Theme, dict]] = None):
        if theme is None or isinstance(theme, Theme):
            self.theme = theme
        elif isinstance(theme, dict):
            self.theme = Theme.from_dict(theme)
        else:
            self.theme = Theme.from_json_file(theme)

    def convert(self, md_text: str) -> bytes:
        import io as _io
        return self.convert_stream(_io.StringIO(md_text))

    def convert_stream(self, lines):  # pragma: no cover - interface only
        raise NotImplementedError()


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
