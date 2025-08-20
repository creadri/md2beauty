from typing import Optional, Union
from .theme import Theme
from .converters import get_converter


def convert_markdown(input_path, output_path: Optional[str] = None, output_format: str = "html", theme: Optional[str] = None):
    
    if not theme:
        theme = Theme.from_named_theme("default")
    
    # Stream the input file to avoid loading entire markdown into memory
    converter = get_converter(output_format, theme=theme)
    with open(input_path, "r", encoding="utf-8") as f:
        out_bytes = converter.convert_stream(f)

    if output_path:
        with open(output_path, "wb") as out:
            out.write(out_bytes)
    else:
        # print as text when no path given
        try:
            print(out_bytes.decode("utf-8"))
        except Exception:
            print(out_bytes)
