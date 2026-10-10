// Dependency-free behavior tests for the isolated UI (no browser or network).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');

function harness() {
  const elements = {};
  function element(id) {
    return elements[id] ||= { hidden: false, disabled: false, value: '', textContent: '', dataset: {},
      handlers: {}, addEventListener(type, fn) { this.handlers[type] = fn; },
      setAttribute(k, v) { this[k] = v; }, removeAttribute(k) { delete this[k]; } };
  }
  element('selection-config').textContent = JSON.stringify({ extractUrl: '/chart/fictional/year-selection', lang: 'ja' });
  const form = element('year-selection-form');
  form.elements = { mode: { value: 'selected' } };
  form.querySelectorAll = () => state.years.map(value => ({ value: String(value) }));
  const state = { years: [2027], requests: [], copied: [], blobs: [], saved: [] };
  const document = {
    getElementById: element,
    body: { appendChild() {} },
    createElement(type) {
      return { click() { state.saved.push(this.download); }, remove() {} };
    },
  };
  const sandbox = {
    document, AbortController, Blob, File, console,
    navigator: { clipboard: { async writeText(text) { state.copied.push(text); } } },
    URL: { createObjectURL(blob) { state.blobs.push(blob); return 'blob:test'; }, revokeObjectURL() {} },
    setTimeout() { return 1; }, clearTimeout() {},
    fetch(url, options) {
      return new Promise((resolve, reject) => state.requests.push({ url, options, resolve, reject }));
    },
  };
  vm.runInNewContext(fs.readFileSync('static/shichusuimei_year_selection.js', 'utf8'), sandbox);
  return { state, elements, element, change: () => form.handlers.change(),
    submit: () => form.handlers.submit({ preventDefault() {} }),
    action: name => element('selection-result').handlers.click({ target: { closest: () => ({ dataset: { action: name } }) } }) };
}
function respond(request, years, ok = true) {
  const data = { included_years: years, yaml_text: `saved: ${years.join(',')}\n`,
    ai_text: `instructions\n---\nsaved: ${years.join(',')}\n`, filename: 'fictional-test', bytes: 15, characters: 15 };
  request.resolve({ ok, status: ok ? 200 : 422, async json() { return ok ? data : { error: { message: '未収録年' } }; } });
  return data;
}

test('empty year selection does not call API', async () => {
  const h = harness(); h.state.years = [];
  await h.submit();
  assert.equal(h.state.requests.length, 0);
  assert.match(h.element('selection-status').textContent, /1つ以上/);
});

test('copy and downloads use the displayed result, with matching AI instructions', async () => {
  const h = harness();
  const pending = h.submit();
  assert.deepEqual(JSON.parse(h.state.requests[0].options.body), { mode: 'selected', years: [2027] });
  const result = respond(h.state.requests[0], [2027]); await pending;
  assert.equal(h.element('selection-yaml').value, result.yaml_text);
  await h.action('copy-ai'); await h.action('copy-yaml');
  assert.deepEqual(h.state.copied, [result.ai_text, result.yaml_text]);
  await h.action('save-ai'); await h.action('save-yaml');
  assert.deepEqual(h.state.saved, ['fictional-test.txt', 'fictional-test.yaml']);
  assert.equal(await h.state.blobs[0].text(), result.ai_text);
  assert.equal(await h.state.blobs[1].text(), result.yaml_text);
});

test('changing a year invalidates old output and prevents copying it', async () => {
  const h = harness(); const pending = h.submit(); respond(h.state.requests[0], [2027]); await pending;
  h.state.years = [2030]; h.change();
  assert.equal(h.element('selection-result').hidden, true);
  assert.equal(h.element('selection-yaml').value, '');
  await h.action('copy-ai');
  assert.deepEqual(h.state.copied, []);
});

test('late response for an old selection cannot overwrite a newer result', async () => {
  const h = harness(); const old = h.submit();
  h.state.years = [2030, 2033]; h.change();
  assert.equal(h.state.requests[0].options.signal.aborted, true);
  const current = h.submit(); respond(h.state.requests[1], [2030, 2033]); await current;
  const expected = h.element('selection-yaml').value;
  respond(h.state.requests[0], [2027]); await old;
  assert.equal(h.element('selection-yaml').value, expected);
  assert.equal(h.element('selection-result').hidden, false);
  await h.action('copy-yaml'); assert.deepEqual(h.state.copied, [expected]);
});

test('request failure removes the previously valid output', async () => {
  const h = harness(); const first = h.submit(); respond(h.state.requests[0], [2027]); await first;
  const failed = h.submit(); respond(h.state.requests[1], [], false); await failed;
  assert.equal(h.element('selection-result').hidden, true);
  assert.equal(h.element('selection-yaml').value, '');
  assert.equal(h.element('create-selection').disabled, false);
  assert.equal(h.element('selection-status').dataset.error, 'true');
  await h.action('save-yaml'); assert.deepEqual(h.state.saved, []);
});

test('basic and complete modes send no checked years; share fallback saves matching TXT', async () => {
  for (const mode of ['basic', 'complete']) {
    const h = harness(); h.element('year-selection-form').elements.mode.value = mode;
    const pending = h.submit();
    assert.deepEqual(JSON.parse(h.state.requests[0].options.body), { mode, years: [] });
    const result = respond(h.state.requests[0], []); await pending;
    await h.action('share-ai');
    assert.equal(await h.state.blobs[0].text(), result.ai_text);
  }
});
