#!/usr/bin/env node
// Bundle the Mermaid JS renderer into a single .mjs file with esbuild
// Output: md2beauty/js_renderers/mermaid.bundle.mjs

import { build } from 'esbuild';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';
import { existsSync, mkdirSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const repoRoot = resolve(__dirname, '..');

const entry = resolve(repoRoot, 'md2beauty/js_renderers/mermaid.entry.mjs');
const outdir = resolve(repoRoot, 'md2beauty/js_renderers');
if (!existsSync(outdir)) mkdirSync(outdir, { recursive: true });

try {
  await build({
    entryPoints: [entry],
    outfile: resolve(outdir, 'mermaid.bundle.mjs'),
    bundle: true,
    format: 'esm',
    platform: 'node',
    sourcemap: false,
    external: [],
    target: ['es2020'],
    logLevel: 'info',
  });
  console.log('Bundled Mermaid renderer to md2beauty/js_renderers/mermaid.bundle.mjs');
} catch (err) {
  console.error(err);
  process.exit(1);
}
