from typing import Optional, Union
from . import is_debug
from .theme import Theme
from .converters import get_converter
from .embeds import default_diagram_service


def _file_contains_mermaid(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("```mermaid"):
                    return True
    except Exception:
        if is_debug():
            raise
    return False


def convert_markdown(
    input_path,
    output_path: Optional[str] = None,
    output_format: str = "html",
    theme: Optional[Union[str, Theme, dict]] = None,
):
    
    if not theme:
        theme = Theme.from_named_theme("default")
    
    # Normalize theme dicts to Theme
    if isinstance(theme, dict):
        theme = Theme.from_dict(theme)
    # Stream the input file to avoid loading entire markdown into memory
    converter = get_converter(output_format, theme=theme)
    # Preflight: if document uses Mermaid but renderer unavailable, warn once with guidance
    try:
        wants_mermaid = _file_contains_mermaid(input_path)
        if wants_mermaid and not default_diagram_service.has("mermaid"):
            guidance = default_diagram_service.guidance("mermaid") or (
                "Mermaid CLI not found. Install with: npm i -g @mermaid-js/mermaid-cli or use npx @mermaid-js/mermaid-cli"
            )
            import os as _os
            if _os.getenv("MD2BEAUTY_SILENCE_HINTS", "").lower() not in ("1", "true", "yes", "on"):
                print(guidance)
    except Exception:
        # Preflight is best-effort; ignore errors unless debug
        if is_debug():
            raise
    with open(input_path, "r", encoding="utf-8") as f:
        try:
            out_bytes = converter.convert_stream(f)
        except Exception as e:
            # Bubble up guidance if the diagram renderer chose to fail strictly
            msg = str(e)
            if "Mermaid CLI" in msg or "Mermaid" in msg:
                print(msg)
            raise

    if output_path:
        with open(output_path, "wb") as out:
            out.write(out_bytes)
    else:
        # print as text when no path given
        try:
            print(out_bytes.decode("utf-8"))
        except Exception:
            if is_debug():
                raise
            print(out_bytes)
