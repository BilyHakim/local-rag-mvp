(() => {
  let current = null, busy = false, epoch = 0, loaded = false;
  const root = qs('#assistantMessages'), input = createChatEditor(qs('#assistantInput'));
  const endpoint = '/api/assistant';
  const popup = qs('#assistantHistoryPopup');
  const json = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const error = message => { qs('#assistantError').textContent = message; qs('#assistantError').hidden = !message; };

  function controls() {
    ['assistantNew', 'assistantHistoryOpen', 'assistantRefresh', 'assistantSend'].forEach(id => { qs('#' + id).disabled = busy; });
    qsa('.assistant-history-item').forEach(button => { button.disabled = busy; button.setAttribute('aria-current', String(button.dataset.id === current?.id)); });
    qs('#assistantDelete').disabled = busy || !current;
    input.disabled = busy;
    qs('#assistantForm').setAttribute('aria-busy', String(busy));
    qs('#assistantSendStatus').textContent = busy ? 'Menyiapkan jawaban...' : '';
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
      body.append(renderChatMarkdown(turn.content, copy));
      if (turn.role === 'assistant') {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'workspace-button';
        button.textContent = 'Salin jawaban'; button.addEventListener('click', () => copy(turn.content)); body.append(button);
      }
      article.append(body); root.append(article);
    }
    controls();
  }

  async function history() {
    const version = epoch;
    qs('#assistantHistoryStatus').textContent = 'Memuat riwayat...';
    try {
      const items = await api(endpoint + '/conversations');
      if (version !== epoch) return;
      qs('#assistantHistory').replaceChildren(...items.map(item => {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'assistant-history-item'; button.dataset.id = item.id;
        const title = document.createElement('strong'); title.textContent = item.title; button.append(title);
        if (item.updated_at && !Number.isNaN(Date.parse(item.updated_at))) {
          const date = document.createElement('small'); date.textContent = new Date(item.updated_at).toLocaleString('id-ID'); button.append(date);
        }
        button.addEventListener('click', () => selectConversation(item.id));
        return button;
      }));
      qs('#assistantHistoryStatus').textContent = items.length ? `${items.length} percakapan tersimpan.` : 'Belum ada percakapan. Kirim pesan pertama untuk memulai.';
      loaded = true;
      controls();
    } catch (e) { if (version === epoch) qs('#assistantHistoryStatus').textContent = e.message + ' Klik Muat ulang riwayat untuk mencoba lagi.'; }
  }

  async function run(action) {
    if (busy) return;
    const version = epoch;
    busy = true; error(''); controls();
    try { await action(version); }
    catch (e) { if (version === epoch) { error(e.message); if (popup.open) qs('#assistantHistoryStatus').textContent = e.message; } }
    finally { if (version === epoch) { busy = false; controls(); } }
  }

  qs('#assistantForm').addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    if (message.length > 12000) { error('Pesan maksimal 12.000 karakter. Persingkat pesan sebelum mengirim.'); return; }
    await run(async version => {
      const conversation = await api(endpoint + '/messages', json({ message, model: qs('#assistantModel').value || null,
        conversation_id: current?.id || null, revision: current?.revision || null }));
      if (version !== epoch) return;
      input.value = ''; render(conversation); await history();
      root.lastElementChild?.scrollIntoView({ block: 'nearest' });
    });
    if (qs('#assistantView').classList.contains('active')) input.focus({ preventScroll: true });
  });
  qs('#assistantNew').addEventListener('click', () => { render(null); error(''); input.value = ''; input.focus(); });
  qs('#assistantRefresh').addEventListener('click', () => run(() => history()));
  function selectConversation(id) {
    run(async version => {
      const conversation = id ? await api(`${endpoint}/conversations/${id}`) : null;
      if (version !== epoch) return;
      render(conversation); input.value = '';
      if (conversation?.model && [...qs('#assistantModel').options].some(option => option.value === conversation.model)) qs('#assistantModel').value = conversation.model;
      popup.close();
      root.scrollIntoView({ block: 'start' });
    });
  }
  qs('#assistantHistoryOpen').addEventListener('click', () => { popup.showModal(); run(() => history()); });
  qs('#assistantHistoryClose').addEventListener('click', () => popup.close());
  popup.addEventListener('click', event => {
    const rect = popup.getBoundingClientRect();
    if (event.target === popup && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) popup.close();
  });
  popup.addEventListener('close', () => { if (qs('#assistantView').classList.contains('active')) qs('#assistantHistoryOpen').focus({ preventScroll: true }); });
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
  document.addEventListener('workspace-view-changed', event => { if (event.detail.view === 'assistant') open(); else popup.close(); });
  document.addEventListener('workspace-identity-changed', () => {
    epoch++; busy = false; loaded = false; render(null); input.value = ''; error('');
    popup.close(); qs('#assistantHistory').replaceChildren();
    qs('#assistantModel').replaceChildren(new Option('Default server', ''));
    if (qs('#assistantView').classList.contains('active')) open();
  });
  workspaceReady.then(() => { if (qs('#assistantView').classList.contains('active')) open(); });
})();
