from __future__ import annotations

import base64
import mimetypes
import os
import pathlib
import tempfile
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import Optional


@dataclass
class MediaFetchResult:
    path: str
    content_type: Optional[str]
    cached: bool = False  # True if stored in persistent cache (don't delete)


class MediaFetcher:
    """Fetch media by URL (data:, file:, local path, http/https) using temporary files.

    Remote resources are downloaded into the OS temporary directory and marked cached=False
    so callers can delete them when done. Local paths are returned as-is with cached=True.

    Example usage:
        fetcher = MediaFetcher()
        res = fetcher.fetch(src)
        if res and not res.cached:
            os.unlink(res.path)  # cleanup temporary file
    """

    def __init__(self, cache_dir: Optional[str] = None):
        # cache_dir kept for backward compatibility, but not used unless explicitly provided
        self.cache_dir = pathlib.Path(cache_dir) if cache_dir else None

    def fetch(self, src: str, timeout: int = 10) -> Optional[MediaFetchResult]:
        if not src:
            return None

        # data URI
        if src.startswith("data:"):
            try:
                header, data = src.split(",", 1)
                is_base64 = header.endswith(";base64")
                mime = header[5:].split(";")[0] if header.startswith("data:") else None
                if is_base64:
                    b = base64.b64decode(data)
                else:
                    b = urllib.parse.unquote_to_bytes(data)
                ext = mimetypes.guess_extension(mime or "application/octet-stream") or ""
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                tmp.write(b)
                tmp.flush()
                tmp.close()
                return MediaFetchResult(path=tmp.name, content_type=mime, cached=False)
            except Exception:
                return None

        # file:// or local path
        if src.startswith("file://") or os.path.exists(src):
            path = src[7:] if src.startswith("file://") else src
            if os.path.exists(path):
                mime, _ = mimetypes.guess_type(path)
                return MediaFetchResult(path=path, content_type=mime, cached=True)
            return None

        # remote HTTP/HTTPS
        if src.lower().startswith("http://") or src.lower().startswith("https://"):
            # attempt to preserve extension from URL or content-type
            parsed = urllib.parse.urlparse(src)
            guess_ext = os.path.splitext(parsed.path)[1] or ""
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                    ctype = resp.headers.get_content_type() if hasattr(resp.headers, 'get_content_type') else resp.getheader('Content-Type')
                # choose extension and create a temporary file
                ext = guess_ext or (mimetypes.guess_extension(ctype or "") or "")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                tmp.write(data)
                tmp.flush()
                tmp.close()
                return MediaFetchResult(path=tmp.name, content_type=ctype, cached=False)
            except urllib.error.URLError:
                return None
            except Exception:
                return None

        # unknown scheme
        return None
