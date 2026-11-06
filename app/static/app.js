const qs = (selector, root = document) => root.querySelector(selector);
const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = { busy: false };
const appShell = qs('.app-shell');
const sidebar = qs('.sidebar');
const messages = qs('#messages');
const welcome = qs('#welcomeState');
const questionInput = qs('#questionInput');
const toast = qs('#toast');
qs('#logoutButton').addEventListener('click', async event => {
  event.currentTarget.disabled = true;
  try {
    await api('/api/auth/logout', { method: 'POST' });
    location.replace('/login');
  } catch (error) { showToast(error.message); qs('#logoutButton').disabled = false; }
});

function escapeHtml(value = '') {
  const div = document.createElement('div');
  div.textContent = String(value);
  return div.innerHTML;
}

async function api(path, options = {}) {
  options.headers = new Headers(options.headers || {});
  options.credentials = 'same-origin';
  options.headers.set('X-Requested-With', 'workspace');
  const response = await fetch(path, options);
  let body = {};
  try { body = await response.json(); } catch (_) { /* empty response */ }
  if (response.status === 401) location.replace('/login' + location.hash);
  if (!response.ok) throw new Error(Array.isArray(body.detail) ? body.detail.map(item => item.msg).join('; ') : body.detail || 'Terjadi kesalahan pada server.');
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

function switchView(name, focus = true) {
  if (!qs(`#${name}View`)) return;
  qsa('.nav-item').forEach(item => {
    const active = item.dataset.view === name;
    item.classList.toggle('active', active);
    if (active) item.setAttribute('aria-current', 'page'); else item.removeAttribute('aria-current');
  });
  qsa('.view').forEach(view => view.classList.toggle('active', view.id === `${name}View`));
  sidebar.classList.remove('open');
  if (window.matchMedia('(max-width: 760px)').matches) updateSidebarButtons(true);
  history.replaceState(null, '', `#${name}`);
  document.title = `${qs(`#${name}View h1`).textContent} | Local RAG`;
  if (focus) {
    const heading = qs(`#${name}View h1`);
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
  document.dispatchEvent(new CustomEvent('workspace-view-changed', { detail: { view: name } }));
}

qsa('.nav-item').forEach(item => item.addEventListener('click', () => switchView(item.dataset.view)));
function updateSidebarButtons(hidden) {
  const direction = hidden ? 'M13 9l3 3-3 3' : 'M15 9l-3 3 3 3';
  const label = hidden ? 'Buka menu samping' : 'Tutup menu samping';
  const title = hidden ? 'Buka sidebar' : 'Tutup sidebar';
  qsa('.mobile-menu, [data-mobile-menu]').forEach(toggle => {
    toggle.setAttribute('aria-label', label);
    toggle.setAttribute('title', title);
    toggle.setAttribute('aria-controls', 'workspaceSidebar');
    toggle.setAttribute('aria-expanded', String(!hidden));
    toggle.innerHTML = `<svg class="sidebar-toggle-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18${direction}"/></svg><span class="menu-text">Menu</span>`;
  });
  const collapse = qs('#sidebarCollapse');
  if (collapse) {
    collapse.setAttribute('aria-label', hidden ? 'Perluas menu samping' : 'Ciutkan menu samping');
    collapse.setAttribute('title', hidden ? 'Perluas sidebar' : 'Ciutkan sidebar');
    collapse.setAttribute('aria-expanded', String(!hidden));
  }
  const mobile = window.matchMedia('(max-width: 760px)').matches;
  sidebar.inert = mobile && hidden;
  qs('#mainContent').inert = mobile && !hidden;
  qs('#sidebarBackdrop').hidden = !mobile || hidden;
}

let menuTrigger = null;
function closeMobileMenu() {
  sidebar.classList.remove('open');
  updateSidebarButtons(true);
  if (menuTrigger) menuTrigger.focus();
}

qs('#sidebarCollapse').addEventListener('click', () => {
  if (window.matchMedia('(max-width: 760px)').matches) {
    closeMobileMenu();
    return;
  }
  const hidden = appShell.classList.toggle('sidebar-hidden');
  localStorage.setItem('rag-sidebar-hidden', String(hidden));
  updateSidebarButtons(hidden);
});

qsa('.mobile-menu, [data-mobile-menu]').forEach(button => button.addEventListener('click', () => {
  if (window.matchMedia('(max-width: 760px)').matches) {
    const open = sidebar.classList.toggle('open');
    menuTrigger = button;
    updateSidebarButtons(!open);
    if (open) qs('#sidebarCollapse').focus();
    return;
  }
  const hidden = appShell.classList.toggle('sidebar-hidden');
  localStorage.setItem('rag-sidebar-hidden', String(hidden));
  updateSidebarButtons(hidden);
}));
qs('#sidebarBackdrop').addEventListener('click', closeMobileMenu);
qs('.brand').addEventListener('click', event => { event.preventDefault(); switchView('chat'); });
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if (sidebar.classList.contains('open')) closeMobileMenu();
  }
  if (event.key === 'Tab' && sidebar.classList.contains('open') && window.matchMedia('(max-width: 760px)').matches) {
    const controls = qsa('button:not(:disabled), a[href]', sidebar).filter(el => !el.hidden && el.getClientRects().length);
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});
window.matchMedia('(max-width: 760px)').addEventListener('change', () => {
  sidebar.classList.remove('open');
  updateSidebarButtons(window.matchMedia('(max-width: 760px)').matches || appShell.classList.contains('sidebar-hidden'));
});

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
updateSidebarButtons(window.matchMedia('(max-width: 760px)').matches || appShell.classList.contains('sidebar-hidden'));
qs('#themeToggle').addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(theme);
  localStorage.setItem('rag-theme', theme);
});

async function checkHealth() {
  const dot = qs('#statusDot');
  const label = qs('#statusText');
  try {
    const health = await api('/api/health');
    qs('#apiDocsLink').hidden = health.env !== 'local';
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
        return `<div class="source-card"><strong>${escapeHtml(source.source_name || source.filename || 'Sumber tanpa nama')}</strong><span class="source-meta">Bukti terpilih${page}${table}</span><p>${escapeHtml(source.text)}</p></div>`;
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
  item.innerHTML = '<div class="message-avatar">AI</div><div class="message-content"><p class="typing" role="status">Mencari jawaban dari knowledge...</p></div>';
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
      body: JSON.stringify({ question: question.trim(), top_k: Number(qs('#topK').value), model: qs('#llmModel').value || null })
    });
    typing.remove();
    appendMessage('assistant', data.answer, data.status === 'insufficient_evidence' ? [] : (data.sources || []));
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
qs('#resizeComposer').addEventListener('click', () => {
  const expanded = qs('#chatForm').classList.toggle('expanded');
  const button = qs('#resizeComposer');
  const label = expanded ? 'Perkecil kotak pertanyaan' : 'Perbesar kotak pertanyaan';
  button.setAttribute('aria-expanded', String(expanded));
  button.setAttribute('aria-label', label);
  button.title = label;
  button.querySelector('path').setAttribute('d', expanded
    ? 'M20 10h-6V4M14 10l7-7M4 14h6v6M10 14l-7 7'
    : 'M14 4h6v6M20 4l-7 7M10 20H4v-6M4 20l7-7');
  questionInput.focus({ preventScroll: true });
});
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
      <article class="result-item"><header><strong>${escapeHtml(item.source_name || item.filename || 'Tanpa nama')}</strong><span class="score">Skor pencarian: ${Number(item.score).toFixed(3)}</span></header><p>${escapeHtml(item.text)}</p></article>
    `).join('') : '<p class="empty-note">Tidak ada hasil yang cocok.</p>';
  } catch (error) { container.innerHTML = `<p class="empty-note">${escapeHtml(error.message)}</p>`; showToast(error.message); }
});

document.addEventListener('workspace-identity-changed', () => {
  qsa('.message', messages).forEach(message => message.remove());
  welcome.hidden = false;
  qs('#searchResults').textContent = 'Cari knowledge untuk melihat sumber pada workspace ini.';
});
qsa('.nav-item').forEach(item => { item.setAttribute('aria-label', item.textContent.trim()); });
qsa('svg').forEach(icon => icon.setAttribute('aria-hidden', 'true'));
const initialView = location.hash.slice(1);
if (['chat', 'knowledge', 'seo', 'social', 'brand'].includes(initialView)) switchView(initialView, false);
const modelLoadVersions = new Map();
async function loadModels(selectId = 'llmModel', refreshId = 'refreshModels', statusId = 'modelStatus') {
  const version = (modelLoadVersions.get(selectId) || 0) + 1;
  modelLoadVersions.set(selectId, version);
  const select = qs(`#${selectId}`);
  const refresh = qs(`#${refreshId}`);
  const status = qs(`#${statusId}`);
  const previous = select.value;
  select.disabled = true;
  refresh.disabled = true;
  refresh.setAttribute('aria-busy', 'true');
  status.textContent = 'Memuat daftar model...';
  try {
    const data = await api('/api/llm/models');
    if (version !== modelLoadVersions.get(selectId)) return;
    select.replaceChildren(new Option(`Default server${data.default_model ? `: ${data.default_model}` : ''}`, ''));
    for (const model of data.models) select.add(new Option(model, model));
    if (data.models.includes(previous)) select.value = previous;
    select.disabled = !data.models.length;
    status.textContent = data.models.length
      ? ''
      : 'Daftar model kosong. Menggunakan model default server.';
  } catch (error) {
    if (version !== modelLoadVersions.get(selectId)) return;
    select.replaceChildren(new Option('Default server', ''));
    status.textContent = `${error.message} Menggunakan model default server. Coba muat ulang model.`;
  } finally {
    if (version === modelLoadVersions.get(selectId)) {
      refresh.disabled = false;
      refresh.setAttribute('aria-busy', 'false');
    }
  }
}
const loadSocialModels = () => loadModels('socialModel', 'refreshSocialModels', 'socialModelStatus');
const loadCampaignModels = () => loadModels('campaignModel', 'refreshCampaignModels', 'campaignModelStatus');
qs('#refreshModels').addEventListener('click', () => loadModels());
qs('#refreshSocialModels').addEventListener('click', loadSocialModels);
qs('#refreshCampaignModels').addEventListener('click', loadCampaignModels);
document.addEventListener('workspace-identity-changed', () => {
  qs('#llmModel').replaceChildren(new Option('Default server', ''));
  qs('#socialModel').replaceChildren(new Option('Default server', ''));
  qs('#campaignModel').replaceChildren(new Option('Default server', ''));
  loadModels();
  loadSocialModels();
  loadCampaignModels();
});
loadModels();
loadSocialModels();
loadCampaignModels();
checkHealth();
api('/api/auth/me').then(user => { qs('#accessStatus').textContent = user.username || 'API key'; }).catch(() => {});
