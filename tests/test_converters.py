from md2beauty.converters import HtmlConverter


def test_html_converter_basic():
    c = HtmlConverter()
    out = c.convert("# Hi\n\nHello")
    assert isinstance(out, bytes)
    s = out.decode()
    assert "<h1" in s and "Hello" in s


def test_html_converter_with_theme():
    theme = {"styles": {"h1": {"color": "#123456"}}}
    c = HtmlConverter(theme)
    out = c.convert("# T")
    assert b"<style>" in out and b"color: #123456" in out
