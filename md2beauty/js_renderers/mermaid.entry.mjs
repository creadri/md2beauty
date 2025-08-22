// Mermaid JS renderer entry (to be bundled with esbuild)
// Requires dev-time deps: @mermaid-js/mermaid, @xmldom/xmldom
import mermaid from '@mermaid-js/mermaid';
import { DOMImplementation } from '@xmldom/xmldom';

const readStdin = async () => {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  return Buffer.concat(chunks).toString('utf8');
};

(async () => {
  const payload = JSON.parse(await readStdin());
  const code = payload.code || '';
  const options = payload.options || {};
  const format = payload.format || 'svg';

  // Minimal DOM shim
  const dom = new DOMImplementation();
  global.document = dom.createDocument(null, null, null);
  global.window = { document: global.document };

  mermaid.initialize({
    startOnLoad: false,
    theme: options.theme || 'default',
    securityLevel: 'strict',
  });

  try {
    const id = 'm' + Math.random().toString(36).slice(2);
    const { svg } = await mermaid.render(id, code);
    const mime = 'image/svg+xml';
    const data = Buffer.from(svg, 'utf8').toString('base64');
    process.stdout.write(JSON.stringify({ ok: true, mime, data }));
  } catch (err) {
    process.stderr.write(String(err?.stack || err));
    process.exit(1);
  }
})();
