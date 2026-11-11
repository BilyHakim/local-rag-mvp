(() => {
  const settingsForm = qs('#waSettings');
  let config = null, timer = null, busy = false, generation = 0;
  const labels = { pending: 'Menunggu jadwal', generating: 'Menyusun jawaban', sending: 'Mengirim', sent: 'Diterima WAHA', failed: 'Gagal', uncertain: 'Belum pasti', skipped: 'Bukti belum cukup', cancelled: 'Dibatalkan' };
  const request = (path, data, method = 'POST') => api('/api/whatsapp' + path, { method, ...(data ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) } : {}) });

  function seal() {
    generation++;
    clearTimeout(timer); config = null;
    qs('#waContent').hidden = true;
    qs('#waUnlock').hidden = false;
    settingsForm.reset(); qs('#waReminder').reset(); qs('#waPassword').reset();
    qs('#waWebhook').value = ''; qs('#waJobs').replaceChildren();
    qs('#waConnectionStatus').textContent = '';
  }

  async function run(button, task) {
    if (busy) return;
    busy = true; button.disabled = true; qs('#waError').hidden = true;
    try { await task(); }
    catch (error) {
      if (error.message.includes('terkunci')) seal();
      showResult(qs('#waError'), error.message, true);
    } finally { busy = false; button.disabled = false; }
  }

  async function history() {
    const version = generation;
    const jobs = await api('/api/whatsapp/jobs');
    if (version !== generation || !qs('#whatsappView').classList.contains('active')) return;
    const root = qs('#waJobs'); root.replaceChildren();
    if (!jobs.length) { root.textContent = 'Belum ada reminder atau balasan WhatsApp.'; return; }
    for (const job of jobs) {
      const article = document.createElement('article'); article.className = 'wa-job';
      const heading = document.createElement('h3'); heading.textContent = `${job.kind === 'reply' ? 'Balasan' : 'Reminder'} · ${labels[job.status] || job.status}`;
      const meta = document.createElement('p'); meta.className = 'empty-note'; meta.textContent = `${job.target.replace('@c.us', '')} · ${new Date(job.due).toLocaleString('id-ID')}`;
      const topic = document.createElement('p'); topic.textContent = job.topic;
      article.append(heading, meta, topic);
      if (job.error) { const error = document.createElement('p'); error.textContent = job.error; article.append(error); }
      if (job.answer) { const details = document.createElement('details'), summary = document.createElement('summary'), answer = document.createElement('p'); summary.textContent = 'Lihat pesan'; answer.className = 'wa-message'; answer.textContent = job.answer; details.append(summary, answer); article.append(details); }
      if (job.kind === 'reminder' && job.status === 'pending') {
        const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'workspace-button'; cancel.textContent = 'Batalkan reminder';
        cancel.addEventListener('click', () => run(cancel, async () => { await request(`/jobs/${job.id}/cancel`); await history(); showToast('Reminder dibatalkan.'); }));
        article.append(cancel);
      }
      root.append(article);
    }
  }

  async function loadSettings() {
    const version = generation;
    const [saved, catalog, account] = await Promise.all([
      api('/api/whatsapp/settings'), api('/api/llm/models').catch(() => null), api('/api/account/profile')
    ]);
    if (version !== generation || !qs('#whatsappView').classList.contains('active')) return;
    config = saved;
    for (const name of ['url', 'session']) settingsForm.elements[name].value = config[name];
    settingsForm.elements.api_key.value = '';
    qs('#waKeyHint').textContent = config.api_key_configured ? 'API key tersimpan. Kosongkan untuk mempertahankannya.' : 'API key belum tersimpan.';
    settingsForm.elements.allowed_chats.value = config.allowed_chats.map(chat => chat.replace('@c.us', '')).join('\n');
    for (const name of ['enabled', 'reply_enabled']) settingsForm.elements[name].checked = config[name];
    const select = settingsForm.elements.model; select.replaceChildren(new Option('Default server', ''));
    if (catalog) {
      catalog.models.forEach(model => select.add(new Option(model, model)));
    } else { qs('#waStatus').textContent = 'Daftar model belum dapat dimuat; model tersimpan tetap digunakan.'; }
    if (config.model && ![...select.options].some(option => option.value === config.model)) select.add(new Option(config.model, config.model));
    select.value = config.model;
    const target = qs('#waReminder').elements.target; target.replaceChildren(new Option('Pilih nomor yang diizinkan', ''));
    config.allowed_chats.forEach(chat => target.add(new Option(chat.replace('@c.us', ''), chat)));
    qs('#waWebhook').value = JSON.stringify({ url: `${location.origin}/hooks/waha/${account.tenant}`, events: ['message'], hmac: { key: config.webhook_secret } }, null, 2);
    qs('#waContent').hidden = false; qs('#waUnlock').hidden = true;
    await history();
  }

  async function access() {
    seal(); qs('#waUnlock').hidden = true; qs('#waPasswordPanel').hidden = true;
    const version = generation;
    const status = await api('/api/whatsapp/access');
    if (version !== generation || !qs('#whatsappView').classList.contains('active')) return;
    qs('#waPasswordPanel').hidden = false;
    qs('#waPasswordTitle').textContent = status.configured ? 'Ganti password tambahan' : 'Buat password tambahan';
    qs('#waPasswordPanel').open = !status.configured;
    qs('#waOldPassword').hidden = !status.configured;
    qs('#waPassword').elements.old_password.required = status.configured;
    qs('#waStatus').textContent = status.configured ? 'Pengaturan memerlukan password tambahan. Mengunci halaman tidak menghentikan asisten.' : 'Buat password tambahan sebelum mengatur WAHA.';
    qs('#waUnlock').hidden = !status.configured;
    if (status.unlocked) {
      await loadSettings();
      timer = setTimeout(() => { seal(); qs('#waStatus').textContent = 'Sesi pengaturan berakhir. Masukkan kembali password tambahan.'; }, status.expires_in * 1000);
    }
  }

  qs('#waPassword').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(form.querySelector('button'), async () => { await request('/password', Object.fromEntries(new FormData(form))); form.reset(); await access(); showToast('Password tambahan disimpan.'); });
  });
  qs('#waUnlock').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(form.querySelector('button'), async () => { await request('/unlock', { password: form.elements.password.value }); form.reset(); await access(); settingsForm.elements.url.focus(); });
  });
  settingsForm.addEventListener('submit', event => {
    event.preventDefault();
    run(settingsForm.querySelector('[type="submit"]'), async () => {
      const data = Object.fromEntries(new FormData(settingsForm));
      data.revision = config.revision; data.enabled = settingsForm.elements.enabled.checked; data.reply_enabled = settingsForm.elements.reply_enabled.checked;
      data.allowed_chats = data.allowed_chats.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
      await request('/settings', data, 'PUT'); await loadSettings(); showToast('Pengaturan WhatsApp disimpan.');
    });
  });
  qs('#waReminder').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    run(form.querySelector('button'), async () => {
      await request('/reminders', { topic: form.elements.topic.value, target: form.elements.target.value, due: new Date(form.elements.due.value).toISOString() });
      form.reset(); await history(); showToast('Reminder dijadwalkan.');
    });
  });
  qs('#waConnection').addEventListener('click', event => run(event.currentTarget, async () => {
    const result = await api('/api/whatsapp/connection'); qs('#waConnectionStatus').textContent = `Status session WAHA: ${result.status}.`;
  }));
  qs('#waLock').addEventListener('click', event => run(event.currentTarget, async () => { await request('/lock'); seal(); qs('#waUnlock input').focus(); }));
  qs('#waReload').addEventListener('click', event => run(event.currentTarget, access));
  qs('#waHistoryReload').addEventListener('click', event => run(event.currentTarget, history));
  document.addEventListener('workspace-view-changed', event => {
    if (event.detail.view === 'whatsapp') run(qs('#waReload'), access);
    else { seal(); qs('#waUnlock').hidden = true; }
  });
  if (location.hash === '#whatsapp') run(qs('#waReload'), access);
})();
