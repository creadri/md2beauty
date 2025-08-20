from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable
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

    def is_available(self) -> bool:
        """Whether this renderer has the necessary tooling to operate.

        Default to True; concrete implementations can override.
        """
        return True

    def install_guidance(self) -> Optional[str]:
        """Optional human-readable guidance on how to enable this renderer."""
        return None

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

    def has(self, kind: str) -> bool:
        """Return True if a renderer exists and is available for the given kind."""
        r = self._registry.get(kind)
        return bool(r and r.is_available())

    def guidance(self, kind: str) -> Optional[str]:
        r = self._registry.get(kind)
        return r.install_guidance() if r else None


class MermaidUnavailableError(RuntimeError):
    """Raised when Mermaid rendering is requested but tooling is unavailable."""

    def __init__(self, guidance: str) -> None:
        super().__init__(guidance)
        self.guidance = guidance


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
        self._available = bool(self._mmdc or self._npx)

    def is_available(self) -> bool:  # type: ignore[override]
        return self._available

    def install_guidance(self) -> Optional[str]:  # type: ignore[override]
        return (
            "Mermaid CLI not found. To enable Mermaid diagram rendering, install Node.js and then either:\n"
            "  - Global install: npm i -g @mermaid-js/mermaid-cli\n"
            "  - Or use npx (no global install): npx @mermaid-js/mermaid-cli -i input.mmd -o output.svg\n"
            "Verify with: node -v && npm -v. Set MD2BEAUTY_STRICT_DIAGRAMS=1 to fail if unavailable."
        )

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
        if not self._available:
            strict = False
            if config and isinstance(config, dict):
                strict = bool(config.get("strict_diagrams"))
            if not strict:
                # Env var override allows strict mode without threading config
                import os as _os
                strict = _os.getenv("MD2BEAUTY_STRICT_DIAGRAMS", "").lower() in ("1", "true", "yes", "on")
            if strict:
                raise MermaidUnavailableError(self.install_guidance() or "Mermaid CLI not available")
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
