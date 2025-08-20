import pathlib
import tempfile
import os
import pytest

from md2beauty.converters import get_converter


SAMPLES_DIR = pathlib.Path(__file__).parent / "samples"


def test_convert_all_samples():
    assert SAMPLES_DIR.exists(), "samples directory missing"

    formats = ["html", "docx", "pptx"]

    for sample in sorted(SAMPLES_DIR.glob("*.md")):
        with open(sample, "r", encoding="utf-8") as f:
            md_text = f.read()

        any_converted = False
        for fmt in formats:
            try:
                conv = get_converter(fmt)
            except NotImplementedError:
                # converter not yet implemented; skip
                continue

            out = conv.convert(md_text)
            # should produce bytes
            assert isinstance(out, (bytes, bytearray))
            assert len(out) > 0
            any_converted = True

            if fmt == "html":
                try:
                    s = out.decode("utf-8")
                except Exception:
                    pytest.fail(f"HTML output for {sample.name} not UTF-8")
                # basic sanity checks
                assert "<h1" in s or "<h2" in s or "<p" in s

        assert any_converted, f"No converters available for sample {sample}"
