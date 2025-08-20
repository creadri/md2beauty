from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import pathlib
import tempfile
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


@dataclass
class MediaFetchResult:
    path: str
    content_type: Optional[str]
    cached: bool = False  # True if stored in persistent cache (don't delete)


class MediaFetcher:
    """Fetch media by URL (data:, file:, local path, http/https) with simple caching.

    Example usage:
        fetcher = MediaFetcher()
        res = fetcher.fetch(src)
        if res:
            # use res.path (local file)
            if not res.cached:
                os.unlink(res.path)  # cleanup if not cached
    """

    def __init__(self, cache_dir: Optional[str] = None):
        project_root = pathlib.Path(__file__).resolve().parents[1]
        if cache_dir:
            self.cache_dir = pathlib.Path(cache_dir)
        else:
            self.cache_dir = project_root / ".cache" / "md2beauty" / "media"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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
            key = hashlib.sha256(src.encode("utf-8")).hexdigest()
            # try to use cached file if exists
            # attempt to preserve extension from URL or content-type
            parsed = urllib.parse.urlparse(src)
            guess_ext = os.path.splitext(parsed.path)[1] or ""
            if guess_ext:
                cached_path = self.cache_dir / f"{key}{guess_ext}"
            else:
                cached_path = self.cache_dir / key

            if cached_path.exists():
                mime, _ = mimetypes.guess_type(str(cached_path))
                return MediaFetchResult(path=str(cached_path), content_type=mime, cached=True)

            req = urllib.request.Request(src, headers={"User-Agent": "md2beauty/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                    ctype = resp.headers.get_content_type() if hasattr(resp.headers, 'get_content_type') else resp.getheader('Content-Type')
                    # choose extension
                    ext = guess_ext or mimetypes.guess_extension(ctype or "") or ""
                    path = str(cached_path) if guess_ext else str(self.cache_dir / f"{key}{ext}")
                    with open(path, "wb") as f:
                        f.write(data)
                    return MediaFetchResult(path=path, content_type=ctype, cached=True)
            except urllib.error.URLError:
                return None
            except Exception:
                return None

        # unknown scheme
        return None
