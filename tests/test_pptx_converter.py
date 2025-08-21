from md2beauty.converters import get_converter

md = """
# Title

This is a paragraph with **bold** and *italic*.

- First item
- Second item

```mermaid
graph TD; A-->B;
```

```python
print("hi")
```

| H1 | H2 |
| --- | --- |
| a   | b   |

![x](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5cxpEAAAAASUVORK5CYII=)
"""

def test_pptx_converter_basic():
    conv = get_converter("pptx")
    out = conv.convert(md)
    assert isinstance(out, (bytes, bytearray))
    assert len(out) > 0
