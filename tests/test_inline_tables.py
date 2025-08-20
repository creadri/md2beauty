from md2beauty.converters import HtmlConverter


def test_html_table_inline_emphasis():
    md = """
| A | B |
| - | - |
| **bold** | *it* and ~~x~~ |
"""
    html = HtmlConverter().convert(md).decode("utf-8")
    assert "<strong>bold</strong>" in html
    assert "<em>it</em>" in html
    assert "<del>x</del>" in html
