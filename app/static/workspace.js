(() => {
  let selected = null, dirty = false, busy = false, previewUrl = null, currentAudit = null;
  let identityEpoch = 0;
  const base = '/api/workspace';
  const labels = { draft: 'Draft', approved: 'Disetujui', scheduled: 'Terjadwal', publishing: 'Menerbitkan', published: 'Terbit', failed: 'Gagal', uncertain: 'Perlu diperiksa' };
  const json = (body, method = 'POST') => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const date = value => value ? new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Jakarta' }).format(new Date(value)) + ' WIB' : 'Belum dijadwalkan';
  const readable = value => escapeHtml(value ?? '');
  const safeLink = value => { try { const u = new URL(value); return u.protocol === 'https:' ? u.href : null; } catch { return null; } };
  const sourcesHTML = sources => sources?.length ? `<details><summary>Referensi knowledge (${sources.length})</summary>${sources.map(s => `<p><strong>${readable(s.source || s.source_id)}</strong></p><p class="workspace-copy">${readable(s.text)}</p>`).join('')}</details>` : '<p>Tidak ada referensi dokumen yang digunakan.</p>';

  async function run(button, task) {
    if (busy) return;
    const epoch = identityEpoch;
    busy = true;
    qs('#workspaceFeedback').hidden = true;
    const text = button?.textContent;
    if (button) button.textContent = 'Memproses...';
    refreshActions();
    try { await task(epoch); }
    catch (error) {
      if (epoch === identityEpoch) {
        showResult(qs('#workspaceFeedback'), error.message, true);
        showToast(error.message);
      }
    }
    finally {
      busy = false;
      if (button && text) button.textContent = text;
      qs('#generateSocial').textContent = selected ? 'Revisi draft konten' : 'Buat draft konten';
      refreshActions();
    }
  }

  async function status() {
    const epoch = identityEpoch;
    const s = await api(base + '/status');
    if (epoch !== identityEpoch) return;
    const entries = [
      ['Model teks', `${s.text_provider === 'ollama' ? 'Ollama lokal' : 'API'} / ${s.text_model}`],
      ['Gambar', s.image_configured ? 'Dikonfigurasi' : 'Belum dikonfigurasi'],
      ['Instagram', s.instagram_configured && s.public_media_configured ? 'Dikonfigurasi' : 'Belum lengkap'],
      ['Website', s.wordpress_configured ? 'WordPress dikonfigurasi' : 'Belum dikonfigurasi'],
      ['Penjadwalan', s.scheduler_enabled ? 'Scheduler aktif' : 'Scheduler nonaktif'],
    ];
    qsa('[data-workspace-status]').forEach(el => { el.innerHTML = entries.map(([label, value]) => `<div class="connection-item"><span>${readable(label)}</span><strong>${readable(value)}</strong></div>`).join(''); });
    qsa('[data-connection-caption]').forEach(el => { el.textContent = `${s.text_provider === 'ollama' ? 'AI lokal' : 'AI via API'} · ${s.scheduler_enabled ? 'penjadwalan aktif' : 'penjadwalan nonaktif'}`; });
  }

  async function loadProfile() {
    const epoch = identityEpoch;
    const profile = await api(base + '/profile');
    if (epoch !== identityEpoch) return;
    const form = qs('#brandForm');
    Object.entries(profile).forEach(([key, value]) => { if (form.elements[key]) form.elements[key].value = value; });
  }

  qs('#brandForm').addEventListener('submit', event => {
    event.preventDefault();
    run(event.submitter, async epoch => {
      await api(base + '/profile', json(Object.fromEntries(new FormData(event.target)), 'PUT'));
      if (epoch === identityEpoch) showToast('Profil perusahaan tersimpan.');
    });
  });

  async function loadAudits() {
    const epoch = identityEpoch;
    qs('#seoHistory').textContent = 'Memuat riwayat audit...';
    const items = await api(base + '/seo/audits');
    if (epoch !== identityEpoch) return;
    qs('#seoHistory').innerHTML = items.length ? items.map(a => `<button class="workspace-history-item" data-audit-id="${readable(a.id)}">${readable(a.observations.title || a.input_url)}<small>${readable(date(a.updated_at))}</small></button>`).join('') : '<p class="empty-note">Belum ada audit.</p>';
  }

  function renderAudit(a) {
    currentAudit = a;
    const o = a.observations, analysis = a.analysis;
    qs('#seoResult').innerHTML = `<div class="panel"><div class="workspace-row"><h3>Hasil pemeriksaan</h3><button class="workspace-button" id="downloadAudit" type="button">Unduh JSON</button></div><p class="workspace-copy">${readable(o.url)}</p><div class="audit-metrics"><div>HTTP<strong>${readable(o.http_status)}</strong></div><div>H1<strong>${o.h1.length}</strong></div><div>Internal link<strong>${o.internal_links}</strong></div><div>Gambar<strong>${o.images}</strong></div><div>Tanpa atribut alt<strong>${o.missing_alt}</strong></div><div>Temuan<strong>${o.findings.length}</strong></div></div><p class="empty-note">${readable(a.scope)}</p>${o.findings.length ? o.findings.map(f => `<article class="audit-finding"><span class="post-badge">${readable(f.priority)}</span><h4>${readable(f.issue)}</h4><p>${readable(f.recommendation)}</p><small>Bukti: ${readable(f.evidence)}</small></article>`).join('') : '<p>Tidak ada temuan dari pemeriksaan dasar ini. Ini bukan jaminan semua aspek SEO sudah optimal.</p>'}<details><summary>Title, deskripsi, canonical, robots dan sitemap</summary><p class="workspace-copy">${readable(JSON.stringify({ title: o.title, description: o.description, canonical: o.canonical, robots: o.robots, discovery: o.discovery }, null, 2))}</p></details></div><div class="panel"><h3>Analisis dan usulan AI</h3>${analysis ? `<p class="workspace-copy">${readable(analysis.summary)}</p><ol>${analysis.recommendations.map(r => `<li class="workspace-copy">${readable(r)}</li>`).join('')}</ol><h4>Usulan title</h4><p>${readable(analysis.suggested_title)}</p><h4>Usulan meta description</h4><p>${readable(analysis.suggested_description)}</p>` : `<p>${readable(a.analysis_error)}</p>`}${a.warnings.map(w => `<p class="workspace-error">${readable(w)}</p>`).join('')}${sourcesHTML(a.sources)}</div>`;
  }

  qs('#seoHistory').addEventListener('click', event => {
    const button = event.target.closest('[data-audit-id]');
    if (button) run(button, async epoch => { const a = await api(base + '/seo/audits/' + button.dataset.auditId); if (epoch === identityEpoch) renderAudit(a); });
  });
  qs('#seoResult').addEventListener('click', event => {
    if (!event.target.closest('#downloadAudit') || !currentAudit) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(currentAudit, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = `seo-audit-${currentAudit.id}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  qs('#seoForm').addEventListener('submit', event => {
    event.preventDefault();
    run(event.submitter, async epoch => {
      const f = event.target.elements;
      const a = await api(base + '/seo/audits', json({ url: f.url.value, goal: f.goal.value, use_knowledge: f.use_knowledge.checked }));
      if (epoch !== identityEpoch) return;
      renderAudit(a); await loadAudits();
    });
  });

  function clearImage() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    qs('#socialImage').hidden = true; qs('#socialImage').removeAttribute('src');
    qs('#imageEmpty').hidden = false;
  }

  async function renderPost(post) {
    selected = post; dirty = false;
    const editor = qs('#postEditor').elements;
    ['title', 'caption', 'image_prompt'].forEach(k => { editor[k].value = post[k] || ''; });
    editor.hashtags.value = (post.hashtags || []).join(' ');
    qs('#socialForm').elements.channel.value = post.channel;
    qs('#socialBriefTitle').textContent = 'Revisi melalui chat';
    qs('#generateSocial').textContent = 'Revisi draft konten';
    qs('#socialConversation').innerHTML = (post.history || []).map(turn => `<div class="social-turn"><strong>Anda</strong>\n${readable(turn.instruction)}\n\n<strong>Specialist</strong>\n${readable(turn.result.title)}\n${readable(turn.result.caption)}</div>`).join('');
    qs('#socialConversation').scrollTop = qs('#socialConversation').scrollHeight;
    qs('#socialNotes').innerHTML = `<p class="workspace-copy">${readable(post.notes)}</p>${(post.warnings || []).map(w => `<p class="workspace-error">${readable(w)}</p>`).join('')}${sourcesHTML(post.sources)}`;
    qs('#resolveForm').reset();
    clearImage(); refreshActions();
    const epoch = identityEpoch;
    if (post.image_id) {
      try {
        const response = await fetch(`${base}/social/posts/${post.id}/image`, { headers: accessKey ? { Authorization: `Bearer ${accessKey}` } : {} });
        if (!response.ok) throw new Error('Preview gambar belum dapat dimuat.');
        const blob = await response.blob();
        if (epoch !== identityEpoch || selected?.id !== post.id || selected?.revision !== post.revision) return;
        previewUrl = URL.createObjectURL(blob); qs('#socialImage').src = previewUrl; qs('#socialImage').hidden = false;
        qs('#imageEmpty').hidden = true;
      } catch (error) { if (epoch === identityEpoch) showToast(error.message); }
    }
  }

  function refreshActions() {
    const editable = !!selected && ['draft', 'approved', 'scheduled', 'failed'].includes(selected.status);
    qs('#saveDraft').disabled = busy || !editable || !dirty;
    qs('#generateImage').disabled = busy || !editable || dirty;
    qs('#postImageFile').disabled = busy || !editable || dirty;
    qs('#uploadPostImage').disabled = busy || !editable || dirty;
    qs('#manualSocial').disabled = busy;
    qs('#approvePost').disabled = busy || dirty || !selected || !['draft', 'failed'].includes(selected.status);
    qs('#publishPost').disabled = busy || dirty || selected?.status !== 'approved';
    qs('#schedulePost').disabled = busy || dirty || selected?.status !== 'approved';
    qs('#generateSocial').disabled = busy || (!!selected && !editable);
    qs('#socialForm').elements.channel.disabled = !!selected || busy;
    qs('#seoForm button[type=submit]').disabled = busy;
    qs('#brandForm button[type=submit]').disabled = busy;
    qs('#postEditor').querySelectorAll('input, textarea').forEach(input => { input.disabled = busy || !editable; });
    qs('#newSocial').disabled = busy;
    qs('#cancelSchedule').hidden = !selected || !['approved', 'scheduled'].includes(selected.status);
    qs('#cancelSchedule').disabled = busy;
    qs('#resolveForm').hidden = selected?.status !== 'uncertain';
    qs('#resolveForm button').disabled = busy;
    qs('#postStatus').textContent = selected ? `${labels[selected.status]} · v${selected.revision}${dirty ? ' · belum disimpan' : ''}` : 'Belum ada draft';
    qs('#postMessage').textContent = selected ? [selected.error, selected.scheduled_at ? date(selected.scheduled_at) : '', dirty ? 'Simpan perubahan sebelum membuat gambar atau menyetujui versi ini.' : 'Perubahan materi membatalkan persetujuan dan jadwal.', selected.status === 'published' ? `ID publikasi: ${selected.external_id || '-'}` : ''].filter(Boolean).join(' ') : 'Buat draft untuk mulai mengedit dan menyiapkan publikasi.';
    if (selected && ['approved', 'scheduled', 'uncertain', 'failed'].includes(selected.status)) qs('#publicationSection').open = true;
  }

  function resetPost() {
    selected = null; dirty = false;
    qs('#postEditor').reset(); qs('#socialForm').reset(); qs('#scheduleForm').reset();
    qs('#socialBriefTitle').textContent = 'Mulai dengan brief';
    qs('#generateSocial').textContent = 'Buat draft konten';
    qs('#socialConversation').textContent = ''; qs('#socialNotes').textContent = '';
    clearImage(); refreshActions();
    qs('#publicationSection').open = false;
  }

  function tab(name) {
    qs('#socialManual').hidden = name !== 'manual'; qs('#socialPlanner').hidden = name !== 'planner';
    qsa('[data-social-tab]').forEach(b => {
      const active = b.dataset.socialTab === name;
      b.classList.toggle('active', active);
      b.setAttribute('aria-pressed', String(active));
    });
  }
  qsa('[data-social-tab]').forEach(button => button.addEventListener('click', () => {
    tab(button.dataset.socialTab);
    if (button.dataset.socialTab === 'planner') loadPosts().catch(e => showToast(e.message));
  }));
  qs('#newSocial').addEventListener('click', () => { resetPost(); tab('manual'); });
  qs('#manualSocial').addEventListener('click', event => {
    if (dirty) { showToast('Simpan perubahan editor sebelum membuat draft baru.'); return; }
    run(event.currentTarget, async epoch => {
      const post = await api(base + '/social/posts', json({ channel: qs('#socialForm').elements.channel.value }));
      if (epoch !== identityEpoch) return;
      await renderPost(post); await loadPosts();
      showToast('Draft dibuat tanpa AI. Isi caption, simpan, lalu unggah gambar.');
    });
  });
  qs('#imageUploadForm').addEventListener('submit', event => {
    event.preventDefault();
    if (!selected || dirty) return;
    const file = qs('#postImageFile').files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { showToast('Gambar maksimal 10 MB.'); return; }
    run(event.submitter, async epoch => {
      const body = new FormData();
      body.append('file', file); body.append('revision', String(selected.revision));
      const post = await api(`${base}/social/posts/${selected.id}/image-upload`, { method: 'POST', body });
      if (epoch !== identityEpoch) return;
      event.target.reset(); await renderPost(post); await loadPosts();
      showToast('Gambar diunggah. Tinjau dan setujui versi ini sebelum menerbitkan.');
    });
  });
  qs('#postEditor').addEventListener('input', () => { dirty = true; refreshActions(); });

  qs('#socialForm').addEventListener('submit', event => {
    event.preventDefault();
    if (dirty) { showToast('Simpan perubahan editor sebelum meminta revisi.'); return; }
    run(event.submitter, async epoch => {
      const f = event.target.elements;
      const post = await api(base + '/social/generate', json({ brief: f.brief.value, channel: f.channel.value,
        use_knowledge: f.use_knowledge.checked, post_id: selected?.id || null, revision: selected?.revision || null }));
      if (epoch !== identityEpoch) return;
      f.brief.value = ''; await renderPost(post); await loadPosts();
    });
  });

  qs('#postEditor').addEventListener('submit', event => {
    event.preventDefault(); if (!selected) return;
    run(event.submitter, async epoch => {
      const f = event.target.elements;
      const post = await api(`${base}/social/posts/${selected.id}`, json({ revision: selected.revision, title: f.title.value,
        caption: f.caption.value, image_prompt: f.image_prompt.value, hashtags: f.hashtags.value.split(/\s+/).filter(Boolean) }, 'PUT'));
      if (epoch !== identityEpoch) return;
      await renderPost(post); await loadPosts(); showToast('Perubahan tersimpan sebagai draft.');
    });
  });

  async function postAction(action, button, extra = {}) {
    if (!selected || dirty) return;
    await run(button, async epoch => {
      const post = await api(`${base}/social/posts/${selected.id}/${action}`, json({ revision: selected.revision, ...extra }));
      if (epoch !== identityEpoch) return;
      await renderPost(post); await loadPosts();
      showToast(action === 'image' ? 'Gambar dibuat. Tinjau sebelum menyetujui.' : `Status: ${labels[post.status]}`);
    });
  }
  qs('#generateImage').addEventListener('click', e => postAction('image', e.currentTarget));
  qs('#approvePost').addEventListener('click', e => postAction('approve', e.currentTarget));
  qs('#publishPost').addEventListener('click', e => postAction('publish', e.currentTarget));
  qs('#cancelSchedule').addEventListener('click', e => postAction('cancel', e.currentTarget));
  qs('#scheduleForm').addEventListener('submit', event => {
    event.preventDefault();
    const value = event.target.elements.scheduled_at.value;
    if (!value) return;
    postAction('schedule', event.submitter, { scheduled_at: value + ':00+07:00' });
  });
  qs('#resolveForm').addEventListener('submit', event => {
    event.preventDefault();
    postAction('resolve', event.submitter, Object.fromEntries(new FormData(event.target)));
  });

  async function loadPosts() {
    const epoch = identityEpoch;
    qs('#plannerList').textContent = 'Memuat rencana publikasi...';
    const posts = await api(base + '/social/posts');
    if (epoch !== identityEpoch) return;
    qs('#plannerList').innerHTML = posts.length ? posts.map(p => {
      const link = safeLink(p.external_url);
      return `<article class="panel planner-card"><div><span class="post-badge">${readable(labels[p.status])}</span> <small>${readable(p.channel)}</small><h3>${readable(p.title)}</h3><p>${readable(p.caption.slice(0, 240))}${p.caption.length > 240 ? '…' : ''}</p><p>${readable(date(p.scheduled_at))}</p>${p.error ? `<p class="workspace-error">${readable(p.error)}</p>` : ''}${link ? `<a href="${readable(link)}" target="_blank" rel="noopener noreferrer">Lihat posting</a>` : ''}</div><button class="workspace-button" data-post-id="${readable(p.id)}" type="button">Buka / kelola</button></article>`;
    }).join('') : '<div class="panel"><h3>Rencana publikasi masih kosong</h3><p class="empty-note">Mulai dari tab Buat konten. Setelah materi ditinjau dan disetujui, tetapkan jadwal publikasinya di editor.</p></div>';
  }
  qs('#refreshPlanner').addEventListener('click', e => run(e.currentTarget, loadPosts));
  qs('#plannerList').addEventListener('click', event => {
    const button = event.target.closest('[data-post-id]');
    if (!button) return;
    run(button, async epoch => {
      const post = await api(`${base}/social/posts/${button.dataset.postId}`);
      if (epoch !== identityEpoch) return;
      await renderPost(post); tab('manual');
    });
  });

  function loadView(view) {
    if (!['brand', 'seo', 'social'].includes(view)) return;
    const epoch = identityEpoch;
    status().catch(error => {
      if (epoch !== identityEpoch) return;
      qsa('[data-workspace-status]').forEach(el => { el.textContent = `${error.message} Periksa kunci akses, lalu buka kembali menu ini.`; });
      qsa('[data-connection-caption]').forEach(el => { el.textContent = 'Periksa akses workspace'; });
    });
    const task = view === 'brand' ? loadProfile : view === 'seo' ? loadAudits : loadPosts;
    task().catch(error => {
      if (epoch !== identityEpoch) return;
      const target = view === 'seo' ? '#seoHistory' : view === 'social' ? '#plannerList' : '#workspaceFeedback';
      showResult(qs(target), `${error.message} Periksa koneksi atau kunci akses, lalu muat ulang menu ini.`, true);
    });
  }
  document.addEventListener('workspace-view-changed', event => loadView(event.detail.view));
  document.addEventListener('workspace-identity-changed', () => {
    identityEpoch++;
    resetPost(); currentAudit = null; qs('#brandForm').reset();
    ['seoResult', 'seoHistory', 'plannerList'].forEach(id => { qs('#' + id).textContent = ''; });
    qsa('[data-workspace-status]').forEach(el => { el.textContent = 'Pilih menu untuk memuat workspace.'; });
    qs('#workspaceFeedback').hidden = true;
    loadView(qs('.nav-item.active').dataset.view);
  });
  refreshActions();
  loadView(qs('.nav-item.active').dataset.view);
})();
