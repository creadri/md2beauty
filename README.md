# md-2-beauty

**md-2-beauty** is an open-source tool designed to convert Markdown files into beautiful and professional formats such as HTML, DOCX, PPTX, and PDF. It supports themes, Markdown extensions, and advanced diagram rendering using tools like Mermaid.

## Features
- **Multi-format Conversion**: Convert Markdown to HTML, DOCX, PPTX, and PDF.
- **Theme Support**: Apply custom themes to your output formats for a polished look.
- **Diagram Rendering**: Supports JS-based diagrams like Mermaid for visual content.
- **Markdown Extensions**: Fully compatible with Python's `markdown` library extensions.
- **CLI Integration**: Easy-to-use command-line interface for seamless conversions.

## Installation
1. Clone the repository:
   ```bash
   git clone git@github.com:creadri/md2beauty.git
   cd md2beauty
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

## Usage
Convert Markdown files using the CLI:
```bash
python cli.py -f <format> -i <input_file> -o <output_file>
```
- `<format>`: Output format (`html`, `docx`, `pptx`, `pdf`).
- `<input_file>`: Path to the Markdown file.
- `<output_file>`: Path to save the converted file.

### Example
Convert a Markdown file to PDF:
```bash
python cli.py -f pdf -i example.md -o example.pdf
```

## Roadmap
- [x] CLI tool
- [x] HTML conversion
- [x] DOCX/PPTX conversion
- [x] PDF conversion (using Playwright)
- [x] Theme system
- [x] Mermaid/diagram support
- [ ] Adding code languages highlighting support
- [ ] Prepare for PIP packaging and dividing into output and render features to lower dependencies depending on needs
- [ ] Advanced customization options
- [ ] Plugin system for additional formats

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request.

## License
This project is licensed under the MIT License.
