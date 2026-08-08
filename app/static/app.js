const qs = (selector, root = document) => root.querySelector(selector);
const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = { busy: false };
const appShell = qs('.app-shell');
const sidebar = qs('.sidebar');
const messages = qs('#messages');
const welcome = qs('#welcomeState');
const questionInput = qs('#questionInput');
const toast = qs('#toast');

function escapeHtml(value = '') {
  const div = document.createElement('div');
  div.textContent = String(value);
  return div.innerHTML;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let body = {};
  try { body = await response.json(); } catch (_) { /* empty response */ }
  if (!response.ok) throw new Error(body.detail || 'Terjadi kesalahan pada server.');
  return body;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('show'), 3200);
}

function showResult(element, message, isError = false) {
  element.hidden = false;
  element.textContent = message;
  element.classList.toggle('error', isError);
}

function switchView(name) {
  qsa('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === name));
  qsa('.view').forEach(view => view.classList.toggle('active', view.id === `${name}View`));
  sidebar.classList.remove('open');
  if (window.matchMedia('(max-width: 760px)').matches) updateSidebarButtons(true);
}

qsa('.nav-item').forEach(item => item.addEventListener('click', () => switchView(item.dataset.view)));
function updateSidebarButtons(hidden) {
  const direction = hidden ? 'M13 9l3 3-3 3' : 'M15 9l-3 3 3 3';
  const label = hidden ? 'Buka menu samping' : 'Tutup menu samping';
  const title = hidden ? 'Buka sidebar' : 'Tutup sidebar';
  qsa('.mobile-menu, [data-mobile-menu]').forEach(toggle => {
    toggle.setAttribute('aria-label', label);
    toggle.setAttribute('title', title);
    toggle.innerHTML = `<svg class="sidebar-toggle-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18${direction}"/></svg>`;
  });
}

qsa('.mobile-menu, [data-mobile-menu]').forEach(button => button.addEventListener('click', () => {
  if (window.matchMedia('(max-width: 760px)').matches) {
    const open = sidebar.classList.toggle('open');
    updateSidebarButtons(!open);
    return;
  }
  const hidden = appShell.classList.toggle('sidebar-hidden');
  localStorage.setItem('rag-sidebar-hidden', String(hidden));
  updateSidebarButtons(hidden);
}));

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const dark = theme === 'dark';
  qs('#themeLabel').textContent = dark ? 'Mode terang' : 'Mode gelap';
  qs('#themeToggle').setAttribute('aria-label', dark ? 'Aktifkan mode terang' : 'Aktifkan mode gelap');
}

const storedTheme = localStorage.getItem('rag-theme');
const preferredTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
applyTheme(storedTheme || preferredTheme);
if (localStorage.getItem('rag-sidebar-hidden') === 'true' && !window.matchMedia('(max-width: 760px)').matches) {
  appShell.classList.add('sidebar-hidden');
  updateSidebarButtons(true);
}
if (window.matchMedia('(max-width: 760px)').matches) updateSidebarButtons(true);
qs('#themeToggle').addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(theme);
  localStorage.setItem('rag-theme', theme);
});

async function checkHealth() {
  const dot = qs('#statusDot');
  const label = qs('#statusText');
  try {
    await api('/api/health');
    dot.className = 'status-dot online';
    label.textContent = 'Online';
  } catch (_) {
    dot.className = 'status-dot offline';
    label.textContent = 'Tidak terhubung';
  }
}

function appendMessage(role, content, sources = []) {
  if (welcome) welcome.hidden = true;
  const item = document.createElement('article');
  item.className = `message ${role}`;
  if (role === 'user') {
    item.innerHTML = `<div class="message-content"><p>${escapeHtml(content)}</p></div>`;
  } else {
    const sourceMarkup = sources.length ? `
      <button class="source-toggle" type="button">${sources.length} sumber digunakan</button>
      <div class="source-list" hidden>${sources.map(source => {
        const page = source.page_number ? ` · Hal. ${source.page_number}` : '';
        const table = source.table_name ? ` · ${source.table_name}` : '';
        return `<div class="source-card"><strong>${escapeHtml(source.source_name || source.filename || 'Sumber tanpa nama')}</strong><span class="source-meta">Skor ${(source.score * 100).toFixed(0)}%${page}${table}</span><p>${escapeHtml(source.text)}</p></div>`;
      }).join('')}</div>` : '';
    item.innerHTML = `<div class="message-avatar">AI</div><div class="message-content"><p>${escapeHtml(content)}</p>${sourceMarkup}</div>`;
    const toggle = qs('.source-toggle', item);
    if (toggle) toggle.addEventListener('click', () => {
      const list = qs('.source-list', item);
      list.hidden = !list.hidden;
      toggle.textContent = `${sources.length} sumber ${list.hidden ? 'digunakan' : '· sembunyikan'}`;
    });
  }
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

function appendTyping() {
  const item = document.createElement('article');
  item.className = 'message assistant';
  item.innerHTML = '<div class="message-avatar">AI</div><div class="message-content"><div class="typing"><span></span><span></span><span></span></div></div>';
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

async function ask(question) {
  if (state.busy || !question.trim()) return;
  state.busy = true;
  qs('#sendButton').disabled = true;
  appendMessage('user', question.trim());
  questionInput.value = '';
  questionInput.style.height = 'auto';
  const typing = appendTyping();
  try {
    const data = await api('/api/chat-rag', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question.trim(), top_k: Number(qs('#topK').value) })
    });
    typing.remove();
    appendMessage('assistant', data.answer, data.sources || []);
  } catch (error) {
    typing.remove();
    appendMessage('assistant', `Maaf, pertanyaan belum dapat diproses. ${error.message}`);
  } finally {
    state.busy = false;
    qs('#sendButton').disabled = false;
    questionInput.focus();
  }
}

qs('#chatForm').addEventListener('submit', event => { event.preventDefault(); ask(questionInput.value); });
questionInput.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); qs('#chatForm').requestSubmit(); }
});
questionInput.addEventListener('input', () => {
  questionInput.style.height = 'auto';
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 130)}px`;
});
qsa('[data-question]').forEach(button => button.addEventListener('click', () => ask(button.dataset.question)));
qs('#newChatButton').addEventListener('click', () => {
  qsa('.message', messages).forEach(message => message.remove());
  welcome.hidden = false;
  questionInput.focus();
});

const fileInput = qs('#fileInput');
const dropzone = qs('#dropzone');
fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  qs('#fileLabel').textContent = file ? file.name : 'Pilih file atau tarik ke sini';
  qs('#uploadButton').disabled = !file;
});
['dragenter', 'dragover'].forEach(name => dropzone.addEventListener(name, event => { event.preventDefault(); dropzone.classList.add('dragging'); }));
['dragleave', 'drop'].forEach(name => dropzone.addEventListener(name, event => { event.preventDefault(); dropzone.classList.remove('dragging'); }));
dropzone.addEventListener('drop', event => {
  if (!event.dataTransfer.files.length) return;
  fileInput.files = event.dataTransfer.files;
  fileInput.dispatchEvent(new Event('change'));
});

qs('#uploadForm').addEventListener('submit', async event => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) return;
  if (file.size > 25 * 1024 * 1024) return showResult(qs('#uploadResult'), 'Ukuran file melebihi 25 MB.', true);
  const button = qs('#uploadButton');
  button.disabled = true; button.textContent = 'Mengindeks dokumen...';
  const formData = new FormData(); formData.append('file', file);
  try {
    const data = await api('/api/documents/upload', { method: 'POST', body: formData });
    const detail = data.skipped_duplicate ? data.message : `${data.message} ${data.indexed_chunks} chunk dari ${data.total_pages} halaman.`;
    showResult(qs('#uploadResult'), detail);
    event.target.reset(); qs('#fileLabel').textContent = 'Pilih file atau tarik ke sini';
  } catch (error) { showResult(qs('#uploadResult'), error.message, true); }
  finally { button.disabled = !fileInput.files.length; button.textContent = 'Unggah & indeks'; }
});

qs('#manualForm').addEventListener('submit', async event => {
  event.preventDefault();
  const button = qs('#saveButton'); button.disabled = true; button.textContent = 'Menyimpan...';
  try {
    const data = await api('/api/knowledge', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: qs('#knowledgeText').value.trim(), source_name: qs('#sourceName').value.trim() || null })
    });
    showResult(qs('#saveResult'), data.message || 'Knowledge berhasil disimpan.');
    if (!data.skipped_duplicate) event.target.reset();
  } catch (error) { showResult(qs('#saveResult'), error.message, true); }
  finally { button.disabled = false; button.textContent = 'Simpan knowledge'; }
});

qs('#searchForm').addEventListener('submit', async event => {
  event.preventDefault();
  const container = qs('#searchResults');
  container.innerHTML = '<p class="empty-note">Mencari...</p>';
  try {
    const data = await api('/api/knowledge/search', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: qs('#searchInput').value.trim(), top_k: 5 })
    });
    container.innerHTML = data.results.length ? data.results.map(item => `
      <article class="result-item"><header><strong>${escapeHtml(item.source_name || item.filename || 'Tanpa nama')}</strong><span class="score">${(item.score * 100).toFixed(0)}% cocok</span></header><p>${escapeHtml(item.text)}</p></article>
    `).join('') : '<p class="empty-note">Tidak ada hasil yang cocok.</p>';
  } catch (error) { container.innerHTML = `<p class="empty-note">${escapeHtml(error.message)}</p>`; showToast(error.message); }
});

checkHealth();
