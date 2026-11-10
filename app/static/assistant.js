(() => {
  let current = null, busy = false, epoch = 0, loaded = false;
  const root = qs('#assistantMessages'), input = qs('#assistantInput');
  const endpoint = '/api/assistant';
  const json = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const error = message => { qs('#assistantError').textContent = message; qs('#assistantError').hidden = !message; };

  function controls() {
    ['assistantNew', 'assistantHistory', 'assistantRefresh', 'assistantSend'].forEach(id => { qs('#' + id).disabled = busy; });
    qs('#assistantDelete').disabled = busy || !current;
    input.disabled = busy;
    qs('#assistantForm').setAttribute('aria-busy', String(busy));
    qs('#assistantSendStatus').textContent = busy ? 'CommandCode sedang menyiapkan jawaban...' : 'Enter untuk mengirim · Shift + Enter untuk baris baru';
  }

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); showToast('Teks disalin.'); }
    catch (_) { showToast('Browser belum mengizinkan penyalinan. Pilih teks lalu salin secara manual.'); }
  }

  function render(conversation) {
    current = conversation;
    qsa('.message', root).forEach(item => item.remove());
    qs('#assistantWelcome').hidden = !!conversation;
    qs('#assistantContext').hidden = !conversation?.context_limited;
    for (const turn of conversation?.messages || []) {
      const article = document.createElement('article');
      article.className = `message ${turn.role}`;
      const body = document.createElement('div'); body.className = 'message-content';
      const label = document.createElement('strong'); label.textContent = turn.role === 'user' ? 'Anda' : 'Ruang Chat';
      body.append(label);
      const parts = turn.role === 'assistant' ? turn.content.split(/```[^\n]*\n([\s\S]*?)```/g) : [turn.content];
      parts.forEach((text, index) => {
        const block = document.createElement(index % 2 ? 'pre' : 'p');
        if (index % 2) {
          const code = document.createElement('code'); code.textContent = text; block.append(code);
        } else {
          block.innerHTML = escapeHtml(text).replace(/\*\*([^\n]+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`\n]+)`/g, '<code>$1</code>');
        }
        body.append(block);
      });
      if (turn.role === 'assistant') {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'workspace-button';
        button.textContent = 'Salin jawaban'; button.addEventListener('click', () => copy(turn.content)); body.append(button);
      }
      article.append(body); root.append(article);
    }
    qs('#assistantHistory').value = conversation?.id || '';
    controls();
  }

  async function history() {
    const version = epoch;
    qs('#assistantHistoryStatus').textContent = 'Memuat riwayat...';
    try {
      const items = await api(endpoint + '/conversations');
      if (version !== epoch) return;
      qs('#assistantHistory').replaceChildren(new Option('Percakapan baru', ''), ...items.map(item => new Option(item.title, item.id)));
      qs('#assistantHistory').value = current?.id || '';
      qs('#assistantHistoryStatus').textContent = items.length ? `${items.length} percakapan tersimpan.` : 'Belum ada percakapan. Kirim pesan pertama untuk memulai.';
      loaded = true;
    } catch (e) { if (version === epoch) qs('#assistantHistoryStatus').textContent = e.message + ' Klik Muat ulang riwayat untuk mencoba lagi.'; }
  }

  async function run(action) {
    if (busy) return;
    const version = epoch;
    busy = true; error(''); controls();
    try { await action(version); }
    catch (e) { if (version === epoch) error(e.message); }
    finally { if (version === epoch) { busy = false; controls(); qs('#assistantHistory').value = current?.id || ''; } }
  }

  qs('#assistantForm').addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    await run(async version => {
      const conversation = await api(endpoint + '/messages', json({ message, model: qs('#assistantModel').value || null,
        conversation_id: current?.id || null, revision: current?.revision || null }));
      if (version !== epoch) return;
      input.value = ''; render(conversation); await history();
      root.lastElementChild?.scrollIntoView({ block: 'nearest' });
    });
    if (qs('#assistantView').classList.contains('active')) input.focus({ preventScroll: true });
  });
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); qs('#assistantForm').requestSubmit(); }
  });
  qs('#assistantNew').addEventListener('click', () => { render(null); error(''); input.value = ''; input.focus(); });
  qs('#assistantRefresh').addEventListener('click', () => run(() => history()));
  qs('#assistantHistory').addEventListener('change', event => {
    const id = event.target.value;
    run(async version => {
      const conversation = id ? await api(`${endpoint}/conversations/${id}`) : null;
      if (version !== epoch) return;
      render(conversation); input.value = '';
      if (conversation?.model && [...qs('#assistantModel').options].some(option => option.value === conversation.model)) qs('#assistantModel').value = conversation.model;
    });
  });
  qs('#assistantDelete').addEventListener('click', () => {
    if (!current || !window.confirm('Hapus percakapan ini beserta seluruh pesannya?')) return;
    run(async version => {
      await api(`${endpoint}/conversations/${current.id}?revision=${current.revision}`, { method: 'DELETE' });
      if (version !== epoch) return;
      render(null); await history(); input.value = ''; showToast('Percakapan dihapus.');
    });
  });
  qs('#assistantModelsRefresh').addEventListener('click', () => loadModels('assistantModel', 'assistantModelsRefresh', 'assistantModelStatus'));
  function open() {
    if (!loaded) { history(); loadModels('assistantModel', 'assistantModelsRefresh', 'assistantModelStatus'); }
  }
  document.addEventListener('workspace-view-changed', event => { if (event.detail.view === 'assistant') open(); });
  document.addEventListener('workspace-identity-changed', () => {
    epoch++; busy = false; loaded = false; render(null); input.value = ''; error('');
    qs('#assistantHistory').replaceChildren(new Option('Percakapan baru', ''));
    qs('#assistantModel').replaceChildren(new Option('Default server', ''));
    if (qs('#assistantView').classList.contains('active')) open();
  });
  if (qs('#assistantView').classList.contains('active')) open();
})();
