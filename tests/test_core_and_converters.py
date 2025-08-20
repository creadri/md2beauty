from md2beauty.core import convert_markdown
from md2beauty.converters import HtmlConverter


def test_core_convert_markdown_html(tmp_path):
    md = "# Title\n\nHello"
    src = tmp_path / "in.md"
    src.write_text(md, encoding="utf-8")
    out = tmp_path / "out.html"
    convert_markdown(str(src), str(out), "html")
    assert out.exists()


def test_html_inline_emphasis_paragraphs():
    md = "This has **bold** and *it* and ~~gone~~"
    html = HtmlConverter().convert(md).decode("utf-8")
    assert "<strong>bold</strong>" in html
    assert "<em>it</em>" in html
    assert "<del>gone</del>" in html
