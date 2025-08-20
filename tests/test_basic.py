from md2beauty.core import convert_markdown
import tempfile
import os

def test_html_conversion():
    md = "# Hello\n\nThis is a test."
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as f:
        f.write(md)
        f.flush()
        out_path = f.name + ".html"
        convert_markdown(f.name, out_path, "html")
        with open(out_path) as out:
            html = out.read()
    assert "<h1" in html and ">Hello</h1>" in html
    assert "This is a test." in html
    os.remove(f.name)
    os.remove(out_path)
