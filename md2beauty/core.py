from typing import Optional, Union
from . import is_debug
from .theme import Theme
from .converters import get_converter

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
    # Read full markdown (parsing now done up-front, streaming deprecated)
    converter = get_converter(output_format, theme=theme)

    with open(input_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    try:
        out_bytes = converter.convert(md_text)
    except Exception as e:
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
