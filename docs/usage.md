# Usage

## CLI

```bash
md2beauty -f pdf -i sample.md -o sample.pdf
```

## Python API

```python
from md2beauty.core import convert_markdown
convert_markdown("input.md", "output.pdf", "pdf")
```

## Mermaid diagrams

This project now renders Mermaid using the official mermaid-cli (mmdc) binary directly (no JS bundling).

- Install Node.js, then install the CLI:

```bash
npm i -D @mermaid-js/mermaid-cli
```

- Ensure `mmdc` is on your PATH (e.g., `./node_modules/.bin`), or set an explicit path via the environment variable:

```bash
export MD2BEAUTY_MMDC=/absolute/path/to/node_modules/.bin/mmdc
```

- In headless CI/Linux, Chromium may require sandbox flags. We pass `--no-sandbox --disable-setuid-sandbox` automatically.

- If `mmdc` or browser dependencies are missing, Mermaid rendering is skipped by default. To make this a hard error, set:

```bash
export MD2BEAUTY_STRICT_DIAGRAMS=1
```
