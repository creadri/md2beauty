import sys
import os
import pytest

from md2beauty.converters import get_converter


def test_pdf_converter_available_or_guidance(monkeypatch):
    md = "# T\n\nPara with **bold** and a table.\n\n| a | b |\n| - | - |\n| 1 | 2 |\n"
    conv = get_converter("pdf")
    try:
        out = conv.convert(md)
        assert isinstance(out, (bytes, bytearray))
        assert len(out) > 0
    except RuntimeError as e:
        # Dependency missing/guidance case (Playwright guidance)
        msg = str(e)
        assert ("Playwright" in msg and "install" in msg.lower())
