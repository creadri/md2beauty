from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import os
import tempfile
import shutil
import subprocess

@dataclass
class RenderResult:
    path: str
    mime: str

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

    def render(self, code: str, attrs: Optional[Dict[str, Any]] = None) -> Optional[RenderResult]:
        raise NotImplementedError()

class RendererRegistry:
    _instance: Optional["RendererRegistry"] = None
    
    def __init__(self) -> None:
        self._renderers = {}
        self.register(MermaidRenderer())

    def __new__(cls) -> "RendererRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._renderers = {}
        return cls._instance

    def register(self, renderer: AssetRenderer) -> None:
        self._renderers[renderer.kind.lower()] = renderer

    def get(self, kind: str) -> Optional[AssetRenderer]:
        return self._renderers.get(kind.lower())

class MermaidRenderer(AssetRenderer):
    kind = "mermaid"

    def __init__(self) -> None:
        self._mmdc_path = self._find_mmdc_path()

    def is_available(self) -> bool:
        return bool(self._mmdc_path)

    def install_guidance(self) -> Optional[str]:
        return (
            "Mermaid rendering requires mermaid-cli (mmdc).\n"
            "Install Node.js, then: npm install -g @mermaid-js/mermaid-cli\n"
            "Ensure 'mmdc' is on PATH or set MD2BEAUTY_MMDC to its full path."
        )

    def render(self, code: str, attrs: Optional[Dict[str, Any]] = None) -> Optional[RenderResult]:
        if not self.is_available():
            raise RuntimeError(self.install_guidance() or "Mermaid renderer not available")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mmd") as tmp_in, tempfile.NamedTemporaryFile(
            delete=False, suffix=".svg"
        ) as tmp_out:
            tmp_in.write(code.encode("utf-8"))
            tmp_in.flush()

            cmd = [self._mmdc_path, "-i", tmp_in.name, "-o", tmp_out.name]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)

            if proc.returncode != 0 or not os.path.exists(tmp_out.name):
                raise RuntimeError(
                    f"Mermaid rendering failed (exit code {proc.returncode}):\n"
                    f"stdout:\n{proc.stdout.decode('utf-8')}\n"
                    f"stderr:\n{proc.stderr.decode('utf-8')}"
                )

            return RenderResult(path=tmp_out.name, mime="image/svg+xml")

    def _find_mmdc_path(self) -> Optional[str]:
        env_path = os.getenv("MD2BEAUTY_MMDC")
        if env_path and shutil.which(env_path):
            return env_path
        return shutil.which("mmdc")
