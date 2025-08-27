from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
import base64
import hashlib
import os
import tempfile
import pathlib


@dataclass
class RenderResult:
    path: str
    mime: str
    width: Optional[int] = None
    height: Optional[int] = None
    alt: Optional[str] = None

    def cleanup(self) -> None:
        if os.path.exists(self.path):
            os.unlink(self.path)


class AssetRenderer:
    kind: str = ""

    def can_render(self, kind: str) -> bool:
        return kind.lower() == self.kind.lower()

    def is_available(self) -> bool:
        return True

    def install_guidance(self) -> Optional[str]:
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
    def __init__(self) -> None:
        self._renderers: Dict[str, AssetRenderer] = {}

    def register(self, renderer: AssetRenderer) -> None:
        self._renderers[renderer.kind.lower()] = renderer

    def get(self, kind: str) -> Optional[AssetRenderer]:
        return self._renderers.get(kind.lower())


class DiagramService:
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
        r = self._registry.get(kind)
        return bool(r and r.is_available())

    def guidance(self, kind: str) -> Optional[str]:
        r = self._registry.get(kind)
        return r.install_guidance() if r else None


class MermaidUnavailableError(RuntimeError):
    def __init__(self, guidance: str) -> None:
        super().__init__(guidance)
        self.guidance = guidance


class MermaidRenderer(AssetRenderer):
    kind = "mermaid"

    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, str], Tuple[str, str]] = {}
        from .js_runtime import NodeBackend
        self._js = NodeBackend()
        base = pathlib.Path(__file__).resolve().parents[1] / "md2beauty" / "js_renderers"
        # Preferred: programmatic mermaid-cli ESM entry
        self._cli_entry = base / "mermaid_cli.entry.mjs"
        self._cli_bundle_mjs = base / "mermaid_cli.bundle.mjs"
        self._cli_bundle_cjs = base / "mermaid_cli.bundle.cjs"
        # Availability probe cache
        self._avail_checked = False
        self._avail_ok = False

    def _select_script(self) -> pathlib.Path|None:
        if self._cli_entry.exists():
            return self._cli_entry
        if self._cli_bundle_mjs.exists():
            return self._cli_bundle_mjs
        if self._cli_bundle_cjs.exists():
            return self._cli_bundle_cjs
        return None
    

    def is_available(self) -> bool:
        # First, require Node and at least one script present
        if not self._js.is_available():
            return False
        if not any(
            p.exists()
            for p in (
                self._cli_entry,
                self._cli_bundle_mjs,
                self._cli_bundle_cjs,
            )
        ):
            return False

        # Return cached probe result if already computed
        if self._avail_checked:
            return self._avail_ok

        # Probe run: ensure Puppeteer/CLI works in this environment
        try:
            script = str(self._select_script())
            self._js.run(script, {"code": "graph TD;A-->B;", "format": "svg"}, timeout=20)
            self._avail_ok = True
        except Exception:
            self._avail_ok = False
        finally:
            self._avail_checked = True

        return self._avail_ok

    def install_guidance(self) -> Optional[str]:
        return (
            "Mermaid renderer requires Node.js. Recommended: bundle once with esbuild:\n"
            "  1) Ensure Node is installed (node -v).\n"
            "  2) Run either: npm run bundle:mermaid-cli  (preferred) or npm run bundle:mermaid (fallback)\n"
            "This creates md2beauty/js_renderers/mermaid_cli.bundle.mjs (or mermaid.bundle.cjs)."
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
        if not self.is_available():
            strict = False
            if config and isinstance(config, dict):
                strict = bool(config.get("strict_diagrams"))
            if not strict:
                strict = os.getenv("MD2BEAUTY_STRICT_DIAGRAMS", "").lower() in ("1", "true", "yes", "on")
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
        script = str(self._select_script())
        result = self._js.run(script, {"code": code, "format": fmt})
        data_b64 = result.get("data")
        if not data_b64:
            return None
        if fmt == "png":
            mime = result.get("mime", "image/png")
            suffix = ".png"
        elif fmt in ("jpg", "jpeg"):
            mime = result.get("mime", "image/jpeg")
            suffix = ".jpg"
        else:
            mime = result.get("mime", "image/svg+xml")
            suffix = ".svg"
        raw = base64.b64decode(data_b64)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(raw)
        tmp.flush(); tmp.close()
        return RenderResult(path=tmp.name, mime=mime)


default_registry = RendererRegistry()
default_registry.register(MermaidRenderer())

default_diagram_service = DiagramService(default_registry)
