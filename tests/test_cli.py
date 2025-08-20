import sys
from md2beauty.cli import main as cli_main

def test_cli_runs_html(tmp_path, monkeypatch):
    md = "# T\n\nPara"
    src = tmp_path / "in.md"
    src.write_text(md, encoding="utf-8")
    out = tmp_path / "out.html"
    monkeypatch.setattr(sys, "argv", ["md2beauty", str(src), "-f", "html", "-o", str(out)])
    cli_main()
    assert out.exists() and out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
