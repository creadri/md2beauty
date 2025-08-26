# md2beauty

**md2beauty** is an open-source tool designed to convert Markdown files into beautiful and professional formats such as HTML, DOCX, PPTX, and PDF. It supports themes and advanced diagram rendering using tools like Mermaid.

## Purpose and Scope

The purpose of this library is to be able to "render" markdown document beautifully in a variety of `legacy` formats such as Microsoft Word (.docx), Microsoft PowerPoint (.pptx) and PDF.

## Features
- **Multi-format Conversion**: Convert Markdown to HTML, DOCX, PPTX, and PDF.
- **Theme Support**: Apply custom themes to your output formats for a polished look.
- **Diagram Rendering**: Supports JS-based diagrams like Mermaid for visual content.
- **CLI Integration**: Easy-to-use command-line interface for seamless conversions.
- **Beautiful out of the box:** Avoid having to tweak the files afterwards enabling a fast and easy use.

## Installation

### Using PIP

For all output formats:

```bash
pip install md2beauty[all]
```

For specific output format only:

```bash
pip install md2beauty[docx,pptx,pdf,html]
```
> Use only the ones you are interested in.

### Mermaid (JS) renderer

Mermaid rendering uses a tiny Node-based JS backend. Bundle once, then it works without extra CLI tools:

1) Ensure Node.js is installed:
```bash
node -v
npm -v
```

2) Install dev deps and bundle the renderer:
```bash
npm install
node scripts/bundle-mermaid.mjs
```
This produces `md2beauty/js_renderers/mermaid.bundle.mjs` used at runtime.

If Mermaid isn’t bundled and Node/scripts aren’t available at runtime, diagrams are skipped unless strict mode is enabled.


## Usage
Convert Markdown files using the CLI:
```bash
python -m md2beauty.cli -f <format> -i <input_file> -o <output_file>
```
- `<format>`: Output format (`html`, `docx`, `pptx`, `pdf`).
  - Default is `html`
- `<input_file>`: Path to the Markdown file.
- `<output_file>`: Path to save the converted file.
  - Optional, if not present, base name of `input_file` with `format` as an extension.

### Example
Convert a Markdown file to PDF:
```bash
python cli.py -f pdf -i example.md -o example.pdf
```

## Roadmap
- [x] CLI tool
- [x] HTML conversion
- [x] DOCX/PPTX conversion
- [x] PDF conversion (using WeasyPrint)
- [x] Theme system
- [x] Mermaid/diagram support
- [x] Adding code languages highlighting support
- [x] Prepare for PIP packaging and dividing into output and render features to lower dependencies depending on needs
- [ ] Make Documentation actually useful
- [ ] First release on piphub
- [ ] Advanced customization options
- [ ] Plugin system for additional 

## Other Known Libraries:

| Name              | Description                                                                 | License Type      | Main Language |
|-------------------|-----------------------------------------------------------------------------|-------------------|---------------|
| Jupyter nbconvert | Converts Jupyter notebooks (Markdown + code) to HTML, PDF, and more          | BSD               | Python       |
| MkDocs            | Fast, simple and downright gorgeos static site generator                     | BSD               | Python       |
| Grip              | Preview GitHub-flavored Markdown with export to HTML                         | MIT               | Python       |
| Pandoc            | Universal document converter supporting Markdown to many formats (HTML, DOCX, PDF, etc.) | GPL              | Haskell       |
| Marp              | Markdown presentation tool converting Markdown to slides (HTML, PPTX, PDF)   | MIT               | TypeScript   |
| Typora            | Markdown editor with export options to DOCX, PDF, and HTML                   | Proprietary       | JavaScript   |
| md-to-pdf         | Node.js tool to convert Markdown files directly to PDF                       | MIT               | JavaScript   |
| markdown-pdf      | Node.js utility for converting Markdown to PDF                               | MIT               | JavaScript   |
| remarkable        | Markdown parser and compiler with plugins for various output formats         | MIT               | JavaScript   |
| reveal-md         | Create reveal.js presentations from Markdown files                           | MIT               | JavaScript   |

### Other less known libraries:

| Name              | Description                                                                 | License Type      | Main Language |
|-------------------|-----------------------------------------------------------------------------|-------------------|---------------|
| readme2readall    | Converts Markdown to Word with Mermaid Support                              | MIT               | Python       |

### In what this is different ?

* Offline capacity: No relying on github API calls to render markdown

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request.

## License
This project is licensed under the MIT License.

### Third party Licences
This project includes a distribution bundle of:
- [mermaid(https://github.com/mermaid-js/mermaid)] under MIT License.
