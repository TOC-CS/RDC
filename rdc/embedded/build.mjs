// Rebuild the self-contained MCP Apps resource. Runtime requires no Node or CDN.
import { build } from 'esbuild';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const result = await build({
  entryPoints: [join(here, 'src', 'app.js')],
  bundle: true,
  write: false,
  format: 'iife',
  minify: true,
  target: ['es2022'],
  legalComments: 'eof',
  metafile: true,
});
const [template, css, logo] = await Promise.all([
  readFile(join(here, 'src', 'index.html'), 'utf8'),
  readFile(join(here, 'src', 'styles.css'), 'utf8'),
  readFile(join(here, '..', 'assets', 'rdc-logo.png')),
]);
const script = result.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
// Callback replacements keep JavaScript's literal $&, $`, and $' sequences
// from being treated as replacement-string substitutions.
const html = template.replace('/* RDC_STYLES */', () => css)
  .replace('/* RDC_SCRIPT */', () => script)
  .replaceAll('RDC_LOGO_DATA', () => `data:image/png;base64,${logo.toString('base64')}`);
await writeFile(join(here, 'preview.html'), html);

// Preserve the licenses of all bundled packages, not development-only tooling.
const packages = new Set();
for (const input of Object.keys(result.metafile.inputs)) {
  const normalized = input.replaceAll('\\', '/');
  const match = normalized.match(/node_modules\/((?:@[^/]+\/)?[^/]+)/);
  if (match) packages.add(match[1]);
}
let notices = 'RDC embedded preview third-party notices\n\n';
for (const name of [...packages].sort()) {
  const root = join(here, 'node_modules', name);
  const info = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
  let license;
  for (const file of ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'LICENSE-MIT', 'license']) {
    try { license = await readFile(join(root, file), 'utf8'); break; } catch {}
  }
  if (!license) throw new Error(`Missing bundled license for ${name}`);
  notices += `${name} ${info.version}\n${'='.repeat(64)}\n${license}\n\n`;
}
await writeFile(join(here, 'THIRD_PARTY_NOTICES.txt'), notices);
await mkdir(join(here, 'src'), {recursive: true});
console.log(`Built embedded preview: ${Buffer.byteLength(html)} bytes; ${packages.size} bundled package licenses.`);
