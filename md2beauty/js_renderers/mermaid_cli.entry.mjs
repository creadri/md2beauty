// Mermaid CLI renderer entry (programmatic, no shell exec)
// Reads JSON from stdin: { code, format, options }
// Writes JSON to stdout: { ok, mime, data(base64) }
import { run as mmdcRun } from '@mermaid-js/mermaid-cli';
import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';

const readStdin = async () => {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  return Buffer.concat(chunks).toString('utf8');
};

(async () => {
  const payload = JSON.parse(await readStdin());
  const code = payload.code || '';
  const fmt = (payload.format || 'svg').toLowerCase();
  const opts = payload.options || {};

  const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'md2beauty-mermaid-'));
  const inFile = path.join(tmpDir, 'input.mmd');
  const ext = fmt === 'png' ? '.png' : (fmt === 'jpg' || fmt === 'jpeg') ? '.jpg' : '.svg';
  const outFile = path.join(tmpDir, 'output' + ext);

  // Write input Mermaid code
  await fs.writeFile(inFile, String(code), { encoding: 'utf8' });

  // Ensure puppeteer can run in containerized CI
  const puppeteerConfig = Object.assign({
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  }, opts.puppeteerConfig || {});

  const options = Object.assign(
    {
      quiet: true,
      puppeteerConfig,
    },
    opts || {}
  );

  try {
    await mmdcRun(inFile, outFile, options);
    const mime = ext === '.svg' ? 'image/svg+xml' : (ext === '.png' ? 'image/png' : 'image/jpeg');
    const data = await fs.readFile(outFile);
    const b64 = data.toString('base64');
    process.stdout.write(JSON.stringify({ ok: true, mime, data: b64 }));
  } catch (err) {
    process.stderr.write(String(err?.stack || err));
    process.exit(1);
  } finally {
    try {
      await fs.rm(tmpDir, { recursive: true, force: true });
    } catch {}
  }
})();
