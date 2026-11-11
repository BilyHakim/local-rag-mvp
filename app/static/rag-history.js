(() => {
  const popup = qs('#ragHistoryPopup'), list = qs('#ragHistoryList'), status = qs('#ragHistoryStatus');
  let busy = false;
  function controls() {
    state.ragHistoryBusy = busy;
    qs('#sendButton').disabled = busy || state.busy;
    qs('#newChatButton').disabled = busy || state.busy;
    qs('#ragHistoryOpen').hidden = !state.account?.editable;
    qs('#ragHistoryOpen').disabled = busy || state.busy;
    qs('#ragHistoryRefresh').disabled = busy || state.busy;
    qs('#ragHistoryDelete').disabled = busy || state.busy || !state.ragConversation;
    list.querySelectorAll('button').forEach(button => { button.disabled = busy || state.busy; button.setAttribute('aria-current', String(button.dataset.id === state.ragConversation?.id)); });
  }
  async function run(action) {
    if (busy || state.busy) return;
    const version = state.ragEpoch; busy = true; controls();
    try { await action(version); }
    catch (error) { if (version === state.ragEpoch) status.textContent = error.message; }
    finally { if (version === state.ragEpoch) { busy = false; controls(); } }
  }
  function render(record) {
    state.ragConversation = record;
    qsa('.message', messages).forEach(item => item.remove()); welcome.hidden = !!record;
    for (const turn of record?.messages || []) appendMessage(turn.role, turn.content, turn.status === 'insufficient_evidence' ? [] : (turn.sources || []));
    questionInput.value = '';
    if (record?.model && [...qs('#llmModel').options].some(option => option.value === record.model)) qs('#llmModel').value = record.model;
    if (record && !record.model) qs('#llmModel').value = '';
    if (record?.top_k && [...qs('#topK').options].some(option => Number(option.value) === record.top_k)) qs('#topK').value = record.top_k;
    controls();
  }
  async function load(version) {
    status.textContent = 'Memuat riwayat...';
    const items = await api('/api/rag-history/conversations');
    if (version !== state.ragEpoch) return;
    list.replaceChildren(...items.map(item => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'assistant-history-item'; button.dataset.id = item.id;
      const title = document.createElement('strong'); title.textContent = item.title; button.append(title);
      if (item.updated_at && !Number.isNaN(Date.parse(item.updated_at))) { const date = document.createElement('small'); date.textContent = new Date(item.updated_at).toLocaleString('id-ID'); button.append(date); }
      button.addEventListener('click', () => run(async version => {
        const record = await api('/api/rag-history/conversations/' + item.id);
        if (version !== state.ragEpoch) return;
        render(record); popup.close(); messages.scrollIntoView({ block: 'start' });
      }));
      return button;
    }));
    status.textContent = items.length ? `${items.length} percakapan tersimpan.` : 'Belum ada percakapan RAG. Kirim pertanyaan pertama untuk memulai.';
  }
  qs('#ragHistoryOpen').addEventListener('click', () => { popup.showModal(); run(load); });
  qs('#ragHistoryClose').addEventListener('click', () => popup.close());
  qs('#ragHistoryRefresh').addEventListener('click', () => run(load));
  qs('#ragHistoryDelete').addEventListener('click', () => {
    if (!state.ragConversation || !window.confirm('Hapus percakapan RAG ini beserta jawaban dan sumber yang tersimpan?')) return;
    run(async version => {
      const record = state.ragConversation;
      await api(`/api/rag-history/conversations/${record.id}?revision=${record.revision}`, { method: 'DELETE' });
      if (version !== state.ragEpoch) return;
      render(null); await load(version); showToast('Percakapan RAG dihapus.');
    });
  });
  popup.addEventListener('click', event => {
    const rect = popup.getBoundingClientRect();
    if (event.target === popup && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) popup.close();
  });
  popup.addEventListener('close', () => { if (qs('#chatView').classList.contains('active')) qs('#ragHistoryOpen').focus({ preventScroll: true }); });
  function reset() {
    state.ragEpoch++; state.busy = false; busy = false; render(null); list.replaceChildren(); popup.close();
    qs('#sendButton').disabled = false; qs('#newChatButton').disabled = false;
  }
  document.addEventListener('rag-history-reset', reset);
  document.addEventListener('workspace-identity-changed', reset);
  document.addEventListener('rag-history-state', controls);
  document.addEventListener('workspace-view-changed', event => { if (event.detail.view !== 'chat') popup.close(); controls(); });
  workspaceReady.then(controls);
})();
