from md2beauty.converters import HtmlConverter

def test_html_code_highlighting_includes_div_highlight():
    md = """
# Sample

```python
def add(a, b):
    return a + b
```
""".strip()
    html = HtmlConverter().convert(md).decode("utf-8")
    # Either Pygments is installed (then we expect the highlight wrapper)
    # or fallback pre/code with language class. Accept either but prefer highlight.
    assert ("<div class=\"highlight\">" in html) or ("<pre><code class=\"language-python\"" in html)
    # If Pygments ran, CSS should be injected
    if "<div class=\"highlight\">" in html:
        assert ".highlight" in html
