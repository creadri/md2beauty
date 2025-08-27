from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable
import base64
import hashlib
import os
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
        if os.path.exists(self.path):
            os.unlink(self.path)

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

        # JS backend and script paths (prefer bundled .cjs, fallback to .mjs or entry)
        from .js_runtime import NodeBackend
        self._js = NodeBackend()
        project_root = pathlib.Path(__file__).resolve().parents[1]
        base = project_root / "md2beauty" / "js_renderers"
        self._bundle_cjs = base / "mermaid.bundle.cjs"
        self._bundle_mjs = base / "mermaid.bundle.mjs"
        self._entry = base / "mermaid.entry.mjs"

    def is_available(self) -> bool:  # type: ignore[override]
        # Available if Node is present and any script exists
        return bool(
            self._js.is_available()
            and (self._bundle_cjs.exists() or self._bundle_mjs.exists() or self._entry.exists())
        )

    def install_guidance(self) -> Optional[str]:  # type: ignore[override]
        return (
            "Mermaid JS renderer requires Node.js. Recommended: bundle the renderer once with esbuild:\n"
            "  1) Ensure Node is installed (node -v).\n"
            "  2) Run: node scripts/bundle-mermaid.mjs\n"
            "This creates md2beauty/js_renderers/mermaid.bundle.cjs used at runtime (ESM .mjs fallback)."
        )

    def _hash(self, code: str, attrs: Optional[Dict[str, Any]]) -> str:
        h = hashlib.sha256()
        h.update(code.encode("utf-8"))
        if attrs:
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
        if not self.is_available():
            strict = False
            if config and isinstance(config, dict):
                strict = bool(config.get("strict_diagrams"))
            if not strict:
                import os as _os
                strict = _os.getenv("MD2BEAUTY_STRICT_DIAGRAMS", "").lower() in ("1", "true", "yes", "on")
            if strict:
                raise MermaidUnavailableError(self.install_guidance() or "Mermaid renderer not available")
            return None

        preferred = [f.lower() for f in (preferred_formats or ["svg", "png"])]
        digest = self._hash(code, attrs)

        for fmt in preferred:
            if fmt not in ("svg", "png", "jpeg", "jpg"):
                continue
            key = (digest, fmt)
            if key in self._cache:
                path, mime = self._cache[key]
                return RenderResult(path=path, mime=mime)

            rr = self._render_with_js(code, fmt)
            if rr:
                self._cache[key] = (rr.path, rr.mime)
                return rr

        for fmt in ("svg", "png"):
            key = (digest, fmt)
            if key in self._cache:
                path, mime = self._cache[key]
                return RenderResult(path=path, mime=mime)
            rr = self._render_with_js(code, fmt)
            if rr:
                self._cache[key] = (rr.path, rr.mime)
                return rr

        return None

    def _render_with_js(self, code: str, fmt: str) -> Optional[RenderResult]:
        script_path = (
            self._bundle_cjs if self._bundle_cjs.exists() else (
                self._bundle_mjs if self._bundle_mjs.exists() else self._entry
            )
        )
        script = str(script_path)

        result = self._js.run(script, {"code": code, "format": "svg"})

        data_b64 = result.get("data")
        mime = result.get("mime", "image/svg+xml")
        if not data_b64:
            return None
        raw = base64.b64decode(data_b64)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".svg")
        tmp.write(raw)
        tmp.flush(); tmp.close()
        return RenderResult(path=tmp.name, mime=mime)

# Set up a default registry with the Mermaid renderer registered
default_registry = RendererRegistry()
default_registry.register(MermaidRenderer())

default_diagram_service = DiagramService(default_registry)


# Set up a default registry with the Mermaid renderer registered
default_registry = RendererRegistry()
default_registry.register(MermaidRenderer())

default_diagram_service = DiagramService(default_registry)
