// Exercise the production share functions offline with fictional payloads.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');

const template = fs.readFileSync('templates/chart_page.html', 'utf8');
const functions = template.slice(template.indexOf('    function canUseFileShare('),
  template.indexOf('    function openFallbackShare('));
const builder = template.slice(template.indexOf('    function buildAiTextFromYaml('),
  template.indexOf('    async function buildAiText('));
const fixtures = process.env.NANAMI_SHARE_FIXTURES
  ? JSON.parse(fs.readFileSync(process.env.NANAMI_SHARE_FIXTURES, 'utf8'))
  : Object.fromEntries(['shichu_basic', 'shichu_full', 'shichu_full_basic',
    'shichu_full_selected', 'western_full_light'].map((name, i) => [name, {
      prompt: 'Fictional reading instructions: preserve candidate status.',
      yaml: `fixture: ${name}\nstatus: candidate\nnote: ` + 'fictional data '.repeat(i === 4 ? 400 : 16000),
    }]));

function harness(fixture, options = {}) {
  const state = { ...fixture, mode: 'paste', calls: [], activation: true };
  const elements = { 'copy-status': { textContent: '' }, 'fallback-share': { open: false } };
  const sandbox = {
    Blob, File, Intl, Date,
    navigator: {
      canShare() { if (options.canShareThrows) throw new TypeError('unsupported'); return options.files !== false; },
      async share(payload) {
        if (!state.activation) throw new DOMException('expired activation', 'NotAllowedError');
        state.calls.push(payload);
        if (options.error) throw new DOMException('fictional share error', options.error);
      },
    },
    document: { getElementById: id => elements[id] || null },
    setTimeout() {},
    DEBUG_SHARE: false, TXT_SHARE_TEST_MODE: false,
    HAS_LONG_TERM_TRANSITS: false,
    UI_TEXT: { shareTxtTitle: 'AI reading TXT', shareTextTitle: 'AI reading text',
      shareUnavailable: 'Use copy or TXT.', shareLargeUnavailable: 'Use TXT for large data.',
      yamlDataIntro: 'Fictional YAML follows.' },
    preparedAiTextFiles: { paste: null, asteroids: null, full: null },
    getSelectedAiMode: () => state.mode,
    getCompanionPrompt: () => state.prompt,
    getPasteYaml: () => state.yaml,
    get fullYamlCache() { return state.yaml; },
    get asteroidYamlCache() { return state.yaml; },
    selectAiMode(mode) { state.mode = mode; sandbox.prepareAiTextFile(mode); },
    async buildSelectedAiText(mode) { return sandbox.buildAiTextFromYaml(state.yaml, mode); },
  };
  if (options.noShare) delete sandbox.navigator.share;
  vm.runInNewContext(builder + '\n' + functions, sandbox);
  return { state, sandbox, elements,
    text: () => sandbox.buildAiTextFromYaml(state.yaml, state.mode),
    flush: () => new Promise(resolve => setImmediate(resolve)) };
}

for (const [name, fixture] of Object.entries(fixtures)) {
  test(`${name}: TXT carries complete instructions and data without duplicate share text`, async () => {
    const h = harness(fixture);
    h.sandbox.shareDefaultAiText();
    // The native share must be called inside the button's activation, before any wait.
    assert.equal(h.state.calls.length, 1);
    h.state.activation = false;
    await h.flush();
    const payload = h.state.calls[0];
    assert.deepEqual(Object.keys(payload).sort(), ['files', 'title']);
    assert.equal(payload.files.length, 1);
    assert.equal(payload.files[0].type, 'text/plain');
    assert.match(payload.files[0].name, /^nanami_ai_paste_.*\.txt$/);
    assert.equal(await payload.files[0].text(), h.text());
    assert.equal(payload.files[0].size, Buffer.byteLength(h.text(), 'utf8'));
    assert.ok((await payload.files[0].text()).includes(fixture.yaml));
    assert.equal(h.elements['fallback-share'].open, false);
  });
}

test('selected full output and consultation instructions use the same file-only path', async () => {
  const h = harness({ prompt: 'Fictional consultation instructions', yaml: 'selected_year: 2030\nstatus: ambiguous\n' });
  h.state.mode = 'full';
  await h.sandbox.shareSelectedAiText();
  const payload = h.state.calls[0];
  assert.equal(Object.hasOwn(payload, 'text'), false);
  assert.equal(await payload.files[0].text(), h.text());
  assert.match(payload.files[0].name, /^nanami_ai_full_/);
});

test('changing the selected year or reading mode does not share a stale cached file', async () => {
  const h = harness({ prompt: 'Reading', yaml: 'year: 2027\n' });
  h.sandbox.prepareAiTextFile('paste');
  h.state.yaml = 'year: 2030\n'; h.state.prompt = 'Consultation';
  h.sandbox.shareDefaultAiText(); await h.flush();
  assert.equal(await h.state.calls[0].files[0].text(), h.text());
  assert.doesNotMatch(await h.state.calls[0].files[0].text(), /2027/);
});

for (const options of [{ files: false }, { canShareThrows: true }]) {
  test(`text-only sharing remains available: ${JSON.stringify(options)}`, async () => {
    const h = harness({ prompt: 'Fictional instructions', yaml: 'short: true\n' }, options);
    h.sandbox.shareDefaultAiText(); await h.flush();
    assert.equal(h.state.calls.length, 1);
    assert.deepEqual(Object.keys(h.state.calls[0]).sort(), ['text', 'title']);
    assert.equal(h.state.calls[0].text, h.text());
    assert.equal(h.elements['fallback-share'].open, false);
  });
}

test('missing Web Share opens copy and TXT fallback without data loss', async () => {
  const h = harness({ prompt: 'Instructions', yaml: 'data: fictional\n' }, { noShare: true });
  h.sandbox.shareDefaultAiText(); await h.flush();
  assert.equal(h.state.calls.length, 0);
  assert.equal(h.elements['fallback-share'].open, true);
  assert.equal(await h.sandbox.getPreparedAiTextFile('paste').text(), h.text());
});

for (const error of ['NotAllowedError', 'DataError', 'TypeError']) {
  test(`${error}: keep the original TXT and offer fallback without automatically retrying`, async () => {
    const h = harness({ prompt: 'Instructions', yaml: 'data: fictional\n' }, { error });
    h.sandbox.shareDefaultAiText(); await h.flush();
    assert.equal(h.state.calls.length, 1);
    assert.equal(h.elements['fallback-share'].open, true);
    assert.equal(await h.sandbox.getPreparedAiTextFile('paste').text(), h.text());
  });
}

test('user cancellation does not retry or show a failure', async () => {
  const h = harness({ prompt: 'Instructions', yaml: 'data: fictional\n' }, { error: 'AbortError' });
  h.sandbox.shareDefaultAiText(); await h.flush();
  assert.equal(h.state.calls.length, 1);
  assert.equal(h.elements['fallback-share'].open, false);
  assert.equal(h.elements['copy-status'].textContent, '');
});
