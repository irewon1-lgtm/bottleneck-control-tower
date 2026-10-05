const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {createHash, webcrypto} = require('node:crypto');
const source = fs.readFileSync('docs/app.js', 'utf8');
const reader = source.slice(source.indexOf('  async function readStoredJSON('), source.indexOf('  async function loadTracking('));

function read(files) {
  return vm.runInNewContext(reader + ';readStoredJSON', {
    crypto: webcrypto, TextEncoder,
    fetch: async url => {
      const text = files[new URL(url).pathname.split('/').slice(1).join('/')];
      return {ok: text !== undefined, json: async () => JSON.parse(text), text: async () => text};
    },
  })('https://example.org/', 'future-candidates.json', {});
}

function fixture() {
  const path = `future-candidates.shards/${'0'.repeat(64)}/future-candidates.part-001.json`;
  const raw = JSON.stringify({format: 'bct-json-shard-v1', items: [
    {field: 'version', key: null, value: 1},
    {field: 'results', key: 'd', value: {id: 'd', quantity: null}},
    {field: 'history', key: 0, value: 'keep'},
  ]});
  const manifest = {format: 'bct-sharded-sidecar-v1', document_sha256: '0'.repeat(64),
    fields: [{name: 'version', kind: 'value'}, {name: 'results', kind: 'dict'}, {name: 'history', kind: 'list'}],
    shards: [{path, sha256: createHash('sha256').update(raw).digest('hex'), item_count: 3}],
    item_counts: {version: 1, results: 1, history: 1}, total_item_count: 3};
  return {'future-candidates.json': JSON.stringify(manifest), [path]: raw};
}

test('browser reads legacy single and verified shard snapshots', async () => {
  const expected = {version: 1, results: {d: {id: 'd', quantity: null}}, history: ['keep']};
  assert.equal(JSON.stringify(await read({'future-candidates.json': JSON.stringify(expected)})), JSON.stringify(expected));
  assert.equal(JSON.stringify(await read(fixture())), JSON.stringify(expected));
});

test('browser rejects missing, corrupted and wrong-count shards', async () => {
  for (const fault of ['missing', 'hash', 'count']) {
    const files = fixture(), manifest = JSON.parse(files['future-candidates.json']);
    const path = manifest.shards[0].path;
    if (fault === 'missing') delete files[path];
    if (fault === 'hash') files[path] += ' ';
    if (fault === 'count') manifest.total_item_count++;
    files['future-candidates.json'] = JSON.stringify(manifest);
    await assert.rejects(read(files));
  }
});
