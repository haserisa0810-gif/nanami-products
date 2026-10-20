// Exercise the actual rendered submit handlers without issuing a request.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const fixtures = JSON.parse(fs.readFileSync(process.env.NANAMI_REDEEM_FIXTURES, 'utf8'));

function harness(fixture, { insideForm = false, missingConfirm = false } = {}) {
  const main = { tagName: 'BUTTON', textContent: 'Generate', disabled: false, dataset: {} };
  const confirm = { tagName: 'BUTTON', textContent: 'Create with these details', disabled: false, dataset: {} };
  const state = { submits: [], overlays: [] };
  const form = { dataset: {}, querySelectorAll() { return insideForm ? [main, confirm] : [main]; },
    submit() { state.submits.push({ mainText: main.textContent, confirmText: confirm.textContent,
      mainDisabled: main.disabled, confirmDisabled: confirm.disabled }); } };
  const document = {
    getElementById(id) { return id === 'confirm-create' && !missingConfirm ? confirm : null; },
    createElement() { return { setAttribute() {} }; },
    body: { appendChild(overlay) { state.overlays.push(overlay); } },
  };
  const sandbox = { window: {}, document, form, syncTimezoneFields() {}, normalizeBirthDateField() {} };
  const start = fixture.html.indexOf('    (function () {');
  const end = fixture.html.indexOf('    }());', start) + '    }());'.length;
  assert.ok(start >= 0 && end > start);
  const submitStart = fixture.html.indexOf('    function submitConfirmedForm()');
  const submitEnd = fixture.html.indexOf('\n    function ', submitStart + 1);
  assert.ok(submitStart >= 0 && submitEnd > submitStart);
  vm.runInNewContext(fixture.html.slice(start, end) + '\n' + fixture.html.slice(submitStart, submitEnd), sandbox);
  return { main, confirm, state, sandbox };
}

for (const fixture of fixtures) {
  test(`${fixture.name}: visible final button changes before submission and blocks repeat submission`, () => {
    const h = harness(fixture);
    assert.equal(h.confirm.disabled, false);
    h.sandbox.submitConfirmedForm();
    assert.equal(h.state.submits.length, 1);
    assert.equal(h.confirm.textContent, fixture.loadingText);
    assert.equal(h.confirm.disabled, true);
    assert.equal(h.state.submits[0].confirmText, fixture.loadingText);
    assert.equal(h.state.submits[0].confirmDisabled, true);
    assert.equal(h.main.textContent, fixture.loadingText);
    assert.equal(h.main.disabled, true);
    h.sandbox.submitConfirmedForm();
    assert.equal(h.state.submits.length, 1);
    assert.equal(h.state.overlays.length, 1);
  });
  test(`${fixture.name}: a confirmation button inside the form is processed only once`, () => {
    const h = harness(fixture, { insideForm: true });
    h.sandbox.submitConfirmedForm();
    assert.equal(h.confirm.dataset.originalText, 'Create with these details');
    assert.equal(h.confirm.textContent, fixture.loadingText);
    assert.equal(h.state.submits.length, 1);
  });
  test(`${fixture.name}: absent confirmation or form does not throw or submit twice`, () => {
    const h = harness(fixture, { missingConfirm: true });
    h.sandbox.submitConfirmedForm(); h.sandbox.submitConfirmedForm();
    assert.equal(h.state.submits.length, 1);
    assert.equal(h.main.disabled, true);
    h.sandbox.form = null;
    h.sandbox.submitConfirmedForm();
    assert.equal(h.state.submits.length, 1);
    assert.equal(h.sandbox.window.prepareGeneratingSubmit(null, {}), false);
  });
}
