from md2beauty.theme import Theme
from md2beauty.core import convert_markdown
import tempfile, os


def test_theme_to_css_and_inject():
    theme_dict = {
        "styles": {
            "h1": {"color": "#123456", "font-size": "24pt"},
            "p": {"color": "#111111"}
        },
        "formats": {
            "html": {
                "p": {"color": "#222222"}
            }
        }
    }
    theme = Theme.from_dict(theme_dict)
    css = theme.to_css()
    assert "h1 {" in css and "color: #123456" in css
    assert "p {" in css and "color: #222222" in css  # html override applied

    md = "# Title\n\nPara"
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as f:
        f.write(md)
        f.flush()
        out_path = f.name + ".html"
        convert_markdown(f.name, out_path, "html", theme)
        with open(out_path, "r", encoding="utf-8") as h:
            html = h.read()
        assert "<style>" in html and "color: #222222" in html
    os.remove(f.name)
    os.remove(out_path)


def test_serialize_variants():
    theme_dict = {"h1": {"color": "#123"}, "p": {"color": "#111"}}
    theme = Theme.from_dict(theme_dict)
    css = theme.serialize("html")
    assert "h1 {" in css
    docx_map = theme.serialize("docx")
    assert isinstance(docx_map, dict)
    pptx_map = theme.serialize("pptx")
    assert isinstance(pptx_map, dict)
