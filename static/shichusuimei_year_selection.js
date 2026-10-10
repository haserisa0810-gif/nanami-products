/* Isolated selection UI. No storage, analytics, external fetch, or automatic AI send. */
(() => {
  'use strict';
  const config = JSON.parse(document.getElementById('selection-config').textContent);
  const en = config.lang === 'en';
  const form = document.getElementById('year-selection-form');
  const choices = document.getElementById('year-choices');
  const panel = document.getElementById('selection-result');
  const status = document.getElementById('selection-status');
  const submit = document.getElementById('create-selection');
  const preview = document.getElementById('selection-yaml');
  let result = null;
  let controller = null;
  let revision = 0;

  function message(text, error = false) {
    status.textContent = text;
    status.dataset.error = String(error);
  }
  function reset() {
    revision += 1;
    if (controller) controller.abort();
    controller = null;
    result = null;
    panel.hidden = true;
    preview.value = '';
    document.getElementById('selection-summary').textContent = '';
    submit.disabled = false;
    form.removeAttribute('aria-busy');
    message('');
    const selected = form.elements.mode.value === 'selected';
    choices.hidden = !selected;
    choices.disabled = !selected;
  }
  form.addEventListener('change', reset);

  form.addEventListener('submit', async event => {
    event.preventDefault();
    reset();
    const version = revision;
    const mode = form.elements.mode.value;
    const years = mode === 'selected'
      ? Array.from(form.querySelectorAll('input[name="years"]:checked'), el => Number(el.value)) : [];
    if (mode === 'selected' && !years.length) {
      message(en ? 'Choose at least one year.' : '鑑定したい年を1つ以上選んでください。', true);
      return;
    }
    controller = new AbortController();
    const currentController = controller;
    const timeout = setTimeout(() => currentController.abort(), 60000);
    submit.disabled = true;
    form.setAttribute('aria-busy', 'true');
    message(en ? 'Preparing your saved reading data…' : '保存データから鑑定用YAMLを作成しています…');
    try {
      const response = await fetch(config.extractUrl, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' }, signal: currentController.signal,
        body: JSON.stringify({ mode, years }),
      });
      const data = await response.json();
      if (version !== revision) return;
      if (!response.ok) {
        const fallback = response.status === 410
          ? (en ? 'This chart has expired.' : 'この鑑定データの利用期限が切れています。')
          : (en ? 'Could not prepare the data. Check the saved years or use the complete original.' : 'データを作成できませんでした。収録年を確認するか、完全原本をご利用ください。');
        message(en ? fallback : (data.error?.message || fallback), true);
        return;
      }
      result = data;
      preview.value = data.yaml_text;
      const label = mode === 'complete' ? (en ? 'Complete original' : '完全原本')
        : mode === 'basic' ? (en ? 'Basic reading' : '基本鑑定')
        : (en ? 'Basic + ' : '基本＋') + data.included_years.join('・') + (en ? '' : '年');
      document.getElementById('selection-summary').textContent =
        `${label} / ${data.characters.toLocaleString()} ${en ? 'characters' : '文字'} / ${data.bytes.toLocaleString()} bytes`;
      panel.hidden = false;
      message(en ? 'Ready. Copy or save the data below.' : '作成しました。下のボタンからコピー・保存できます。');
    } catch (error) {
      if (version === revision) message(en ? 'The connection failed or timed out. Try again.' : '通信に失敗、または時間がかかりすぎました。もう一度お試しください。', true);
    } finally {
      clearTimeout(timeout);
      if (version === revision) {
        submit.disabled = false;
        form.removeAttribute('aria-busy');
        controller = null;
      }
    }
  });

  async function copy(text) {
    if (navigator.clipboard?.writeText) {
      try { await navigator.clipboard.writeText(text); return; } catch (_) { /* fallback */ }
    }
    const field = document.createElement('textarea');
    field.value = text;
    field.readOnly = true;
    field.style.position = 'fixed';
    field.style.left = '-9999px';
    document.body.appendChild(field);
    field.select();
    field.setSelectionRange(0, text.length);
    try { if (!document.execCommand('copy')) throw new Error('copy failed'); }
    finally { field.remove(); }
  }
  function save(text, name, type) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  panel.addEventListener('click', async event => {
    const button = event.target.closest('button[data-action]');
    if (!button || !result) return;
    const data = result;
    const action = button.dataset.action;
    try {
      if (action.startsWith('copy-')) {
        await copy(action === 'copy-ai' ? data.ai_text : data.yaml_text);
        message(en ? 'Copied.' : 'コピーしました。');
      } else if (action === 'save-ai') {
        save(data.ai_text, `${data.filename}.txt`, 'text/plain;charset=utf-8');
      } else if (action === 'save-yaml') {
        save(data.yaml_text, `${data.filename}.yaml`, 'text/yaml;charset=utf-8');
      } else if (action === 'share-ai') {
        const file = new File([data.ai_text], `${data.filename}.txt`, { type: 'text/plain' });
        if (navigator.share && navigator.canShare?.({ files: [file] })) {
          await navigator.share({ files: [file], title: en ? 'Four Pillars reading data' : '四柱推命の鑑定用データ' });
        } else {
          save(data.ai_text, `${data.filename}.txt`, 'text/plain;charset=utf-8');
          message(en ? 'Saved TXT. Attach it to your AI chat.' : 'TXTを保存しました。利用するAIに添付してください。');
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') message(en ? 'Copy or share failed. Save TXT or YAML instead.' : 'コピー・共有に失敗しました。TXTまたはYAMLの保存をご利用ください。', true);
    }
  });
})();
