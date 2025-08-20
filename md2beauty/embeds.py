from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
import hashlib
import os
import shutil
import subprocess
import tempfile
import pathlib


@dataclass
class RenderResult:
    """Portable asset produced by a renderer.

    path: filesystem path to the produced asset (e.g., image file)
    mime: MIME type, e.g., 'image/svg+xml' or 'image/png'
    width/height: optional pixel dimensions if known
    alt: optional alt text
    """

    path: str
    mime: str
    width: Optional[int] = None
    height: Optional[int] = None
    alt: Optional[str] = None

    def cleanup(self) -> None:
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
        except Exception:
            pass


class AssetRenderer:
    """Strategy interface for rendering special blocks into assets."""

    kind: str = ""

    def can_render(self, kind: str) -> bool:
        return kind.lower() == self.kind.lower()

    def render(
        self,
        code: str,
        attrs: Optional[Dict[str, Any]] = None,
        preferred_formats: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[RenderResult]:
        raise NotImplementedError()


class RendererRegistry:
    """Global registry for asset renderers (mermaid, plantuml, ...)."""

    def __init__(self) -> None:
        self._renderers: Dict[str, AssetRenderer] = {}

    def register(self, renderer: AssetRenderer) -> None:
        self._renderers[renderer.kind.lower()] = renderer

    def get(self, kind: str) -> Optional[AssetRenderer]:
        return self._renderers.get(kind.lower())


class DiagramService:
    """Facade to render diagrams using registered renderers.

    preferred_formats: ordered list of desired output formats (e.g., ["svg", "png"]).
    """

    def __init__(self, registry: RendererRegistry) -> None:
        self._registry = registry

    def render(
        self,
        kind: str,
        code: str,
        attrs: Optional[Dict[str, Any]] = None,
        preferred_formats: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[RenderResult]:
        r = self._registry.get(kind)
        if not r:
            return None
        return r.render(code=code, attrs=attrs, preferred_formats=preferred_formats, config=config)


class MermaidRenderer(AssetRenderer):
    kind = "mermaid"

    def __init__(self) -> None:
        # In-process cache to avoid re-rendering identical diagrams in a single run
        # Key: (hash, format) -> (path, mime)
        self._cache: Dict[Tuple[str, str], Tuple[str, str]] = {}

        # Resolve executables once
        project_root = pathlib.Path(__file__).resolve().parents[1]
        local_mmdc = project_root / "node_modules" / ".bin" / "mmdc"
        mmdc_exe = shutil.which("mmdc")
        if not mmdc_exe and local_mmdc.exists():
            mmdc_exe = str(local_mmdc)
        self._mmdc = mmdc_exe
        self._npx = shutil.which("npx")

    def _hash(self, code: str, attrs: Optional[Dict[str, Any]]) -> str:
        h = hashlib.sha256()
        h.update(code.encode("utf-8"))
        if attrs:
            # shove a deterministic repr of attrs into the hash
            items = ",".join(f"{k}={attrs[k]}" for k in sorted(attrs.keys()))
            h.update(items.encode("utf-8"))
        return h.hexdigest()

    def render(
        self,
        code: str,
        attrs: Optional[Dict[str, Any]] = None,
        preferred_formats: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[RenderResult]:
        # Ensure we have a way to render
        if not self._mmdc and not self._npx:
            return None

        preferred = [f.lower() for f in (preferred_formats or ["svg", "png"])]
        digest = self._hash(code, attrs)

        # Try requested formats in order
        for fmt in preferred:
            if fmt not in ("svg", "png", "jpeg", "jpg"):
                continue
            key = (digest, fmt)
            if key in self._cache:
                path, mime = self._cache[key]
                return RenderResult(path=path, mime=mime)

            rr = self._render_with_cli(code, fmt)
            if rr:
                self._cache[key] = (rr.path, rr.mime)
                return rr

        # If none of the preferred formats worked, try a simple fallback order
        for fmt in ("svg", "png"):
            key = (digest, fmt)
            if key in self._cache:
                path, mime = self._cache[key]
                return RenderResult(path=path, mime=mime)
            rr = self._render_with_cli(code, fmt)
            if rr:
                self._cache[key] = (rr.path, rr.mime)
                return rr

        return None

    def _render_with_cli(self, code: str, fmt: str) -> Optional[RenderResult]:
        # Prepare temp files
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "diagram.mmd")
            out_path = os.path.join(tmpdir, f"diagram.{fmt}")
            with open(in_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Build command
            try:
                if self._mmdc:
                    cmd = [self._mmdc, "-i", in_path, "-o", out_path]
                else:
                    cmd = [self._npx, "@mermaid-js/mermaid-cli", "-i", in_path, "-o", out_path]  # type: ignore[list-item]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception:
                return None

            if not os.path.exists(out_path):
                return None

            # Persist to a temp file for caller ownership
            suffix = ".svg" if fmt == "svg" else (".png" if fmt == "png" else f".{fmt}")
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            with open(out_path, "rb") as src:
                tmp.write(src.read())
            tmp.flush()
            tmp.close()

            mime = (
                "image/svg+xml" if fmt == "svg" else (
                    "image/png" if fmt == "png" else (
                        "image/jpeg" if fmt in ("jpg", "jpeg") else "application/octet-stream"
                    )
                )
            )
            return RenderResult(path=tmp.name, mime=mime)


# Set up a default registry with the Mermaid renderer registered
default_registry = RendererRegistry()
default_registry.register(MermaidRenderer())

default_diagram_service = DiagramService(default_registry)
