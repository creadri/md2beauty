import os
import pathlib
import pytest

from md2beauty.embeds import MermaidRenderer, MermaidUnavailableError


def test_mermaid_renderer_svg(tmp_path):
    # Ensure debug mode so JS errors are surfaced during the test
    os.environ["MD2BEAUTY_DEBUG"] = "1"

    r = MermaidRenderer()

    if not r.is_available():
        pytest.skip(r.install_guidance() or "Mermaid renderer not available")

    code = """
    graph TD
      A[Start] --> B{Decision}
      B -->|Yes| C[Do X]
      B -->|No| D[Do Y]
    """.strip()

    rr = r.render(code, preferred_formats=["svg"])
    assert rr is not None, "MermaidRenderer returned None"
    assert rr.mime.lower().startswith("image/svg"), f"Unexpected mime: {rr.mime}"

    p = pathlib.Path(rr.path)
    assert p.exists() and p.is_file(), "Output file missing"

    data = p.read_text(encoding="utf-8")
    assert "<svg" in data.lower(), "SVG content not found in output"

    rr.cleanup()
    assert not p.exists(), "Temp file was not cleaned up"
