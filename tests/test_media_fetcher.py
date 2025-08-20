import base64
import os
from md2beauty.media import MediaFetcher


def test_fetch_data_uri_base64_png(tmp_path):
    # tiny transparent PNG 1x1
    png_bytes = base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    fetcher = MediaFetcher()
    res = fetcher.fetch(data_uri)
    assert res and os.path.exists(res.path)
    assert res.content_type == "image/png"
    assert res.cached is False
    os.unlink(res.path)


def test_fetch_local_file(tmp_path):
    p = tmp_path / "file.txt"
    p.write_text("hello")
    fetcher = MediaFetcher()
    res = fetcher.fetch(str(p))
    assert res and res.cached is True
    assert res.content_type and res.content_type.startswith("text/")


def test_fetch_unknown_scheme_returns_none():
    fetcher = MediaFetcher()
    assert fetcher.fetch("ftp://example.com/file.txt") is None
