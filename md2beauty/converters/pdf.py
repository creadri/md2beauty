from __future__ import annotations

from typing import Iterable, Optional, Union

from weasyprint import HTML  # Import WeasyPrint for PDF generation
from ..theme import Theme
from . import Converter
from ..mdparser import parse_markdown, Document


class PdfConverter(Converter):
    def __init__(self, theme: Optional[Union[str, Theme]] = None):
        super().__init__(theme)

    def convert(self, md_text: str) -> bytes:  # type: ignore[override]
        # Parse once, reuse HTML converter on Document
        doc: Document = parse_markdown(md_text)
        from .html import HtmlConverter
        html_bytes = HtmlConverter(theme=self.theme).convert_document(doc)
        html_str = html_bytes.decode('utf-8')
        try:
            pdf_bytes = HTML(string=html_str).write_pdf()
            return pdf_bytes
        except Exception as e:
            raise RuntimeError(
                "Failed to generate PDF using WeasyPrint. Ensure WeasyPrint is installed and functional."
            ) from e
