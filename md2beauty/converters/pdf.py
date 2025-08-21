from __future__ import annotations

from typing import Iterable, Optional, Union

from ..theme import Theme
from . import Converter


class PdfConverter(Converter):
    def __init__(self, theme: Optional[Union[str, Theme]] = None):
        super().__init__(theme)

    def convert_stream(self, lines: Iterable[str]) -> bytes:
        # Reuse HTML converter then render to PDF via Playwright
        from .html import HtmlConverter
        html_bytes = HtmlConverter(theme=self.theme).convert_stream(lines)
        html_str = html_bytes.decode('utf-8')
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Playwright is required for PDF export. Install with 'pip install md2beauty[pdf]' and run 'python -m playwright install chromium'."
            ) from e
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(html_str, wait_until="load")
                pdf_bytes = page.pdf(format="A4")
                browser.close()
                return pdf_bytes
        except Exception as e:
            raise RuntimeError(
                "Failed to generate PDF. Ensure Playwright browsers are installed: 'python -m playwright install chromium'."
            ) from e
