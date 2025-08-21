import pathlib
import pytest
import os
from md2beauty.core import convert_markdown
from md2beauty.converters import get_converter

SAMPLES_DIR = pathlib.Path(__file__).parent / "samples"


def _available_formats():
    fmts = []
    for fmt in ["html", "docx", "pptx", "pdf"]:
        try:
            get_converter(fmt)
        except NotImplementedError:
            continue
        else:
            fmts.append(fmt)
    return fmts


def test_convert_all_samples_to_available_formats(tmp_path):
    if not SAMPLES_DIR.exists():
        pytest.skip(f"samples directory {SAMPLES_DIR} missing")
    fmts = _available_formats()
    assert fmts, "no available formats detected"

    samples = sorted(SAMPLES_DIR.glob("*.md"))
    if not samples:
        pytest.skip("no markdown samples found")

    for sample in samples:
        for fmt in fmts:
            out = tmp_path / f"{sample.stem}.{fmt}"
            # If the sample output already exists, delete it in order to see if a new one is created
            if out.exists():
                os.remove(out)
            convert_markdown(str(sample), str(out), fmt)
            assert out.exists(), f"Output not created for {sample.name} -> {fmt}"
            data = out.read_bytes()
            assert data, f"Empty output for {sample.name} -> {fmt}"
            if fmt == "html":
                s = data.decode("utf-8")
                assert "<html" in s or "<!DOCTYPE html>" in s
