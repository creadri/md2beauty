import argparse
from .core import convert_markdown
import os

def main():
    parser = argparse.ArgumentParser(description="Convert Markdown to HTML, DOCX, PPTX or PDF with theme and extension support.")
    parser.add_argument("input", help="Input Markdown file")
    parser.add_argument("-f", "--format", choices=["html", "docx", "pptx", "pdf"], default="html", help="Output format")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-t", "--theme", help="Theme name or path")
    args = parser.parse_args()

    if not args.output:
        base, _ = os.path.splitext(args.input)
        args.output = f"{base}.{args.format}"
    
    convert_markdown(args.input, args.output, args.format, args.theme)

if __name__ == "__main__":
    main()
