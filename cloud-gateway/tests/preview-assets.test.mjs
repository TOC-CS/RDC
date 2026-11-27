import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

test('published preview assets are compact and tool metadata selects v9', () => {
  const assets = JSON.parse(readFileSync(new URL('../lib/rdc-assets.json', import.meta.url), 'utf8'));
  const tool = assets.catalog.find(item => item.name === 'rdc_preview_open');
  assert.equal(tool._meta.ui.resourceUri, 'ui://rdc/preview-v9.html');
  assert.equal(tool._meta['openai/outputTemplate'], 'ui://rdc/preview-v9.html');
  assert.ok(Buffer.byteLength(assets.resourceHtml) < 800_000);
  assert.ok(Buffer.from(assets.iconDataUri.split(',')[1], 'base64').length < 60_000);
  assert.ok(assets.resourceHtml.includes('0.1.0a8-preview.9'));
  assert.equal(assets.resourceHtml, readFileSync(new URL('../../rdc/embedded/preview.html', import.meta.url), 'utf8'));
});
