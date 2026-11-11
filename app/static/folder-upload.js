(() => {
  const input = qs('#folderInput'), form = qs('#folderUploadForm');
  let formats = null, loading = false, items = [], running = false, paused = false, wakeRetry = null;
  const terminal = item => ['success', 'duplicate', 'failed'].includes(item.status);
  const eligible = () => items.filter(item => item.status !== 'skipped');

  function controls() {
    input.disabled = !formats || loading || state.knowledgeUploadBusy;
    const ready = items.some(item => item.status === 'ready');
    qs('#folderStart').disabled = !formats || !ready || state.knowledgeUploadBusy;
    qs('#folderStart').textContent = eligible().some(terminal) && ready ? 'Lanjutkan folder' : 'Unggah & indeks folder';
    qs('#folderPause').disabled = !running || paused;
    qs('#folderRetry').hidden = !items.some(item => item.status === 'failed');
    qs('#folderRetry').disabled = state.knowledgeUploadBusy;
    qs('#folderFormatsRetry').disabled = loading || state.knowledgeUploadBusy;
  }

  function progress() {
    const files = eligible(), done = files.filter(terminal).length;
    const percent = files.length ? Math.floor(done / files.length * 100) : 0;
    qs('#folderProgressArea').hidden = !files.length;
    qs('#folderProgress').value = percent; qs('#folderProgress').textContent = percent + '%';
    qs('#folderPercent').textContent = `${percent}% (${done}/${files.length} file)`;
  }

  function mark(item, status, message) {
    item.status = status; item.message = message;
    item.result.textContent = `${item.extension.slice(1).toUpperCase() || 'Tanpa ekstensi'} · ${message}`;
    item.result.classList.toggle('folder-file-error', status === 'failed');
  }

  async function loadFormats() {
    if (loading || formats) return;
    loading = true; controls();
    try {
      const data = await api('/api/documents/formats');
      if (!Array.isArray(data.extensions) || !Number.isFinite(data.max_upload_bytes) || data.max_upload_bytes <= 0) throw new Error('Konfigurasi format server tidak valid.');
      if (!('webkitdirectory' in input)) throw new Error('Browser ini belum mendukung pemilihan folder. Gunakan browser terbaru atau unggah satu file.');
      formats = data;
      qs('#folderHelp').textContent = `${data.extensions.map(extension => extension.slice(1).toUpperCase()).join(', ')}. Maksimal ${(data.max_upload_bytes / 1024 / 1024).toLocaleString('id-ID')} MB per file. Format lain, file kosong, dan file terlalu besar dilewati. Nama subfolder dipertahankan sebagai sumber knowledge.`;
      qs('#folderFormatsRetry').hidden = true;
    } catch (error) {
      qs('#folderHelp').textContent = `${error.message} Periksa koneksi dan pastikan backend terbaru sudah dijalankan.`;
      qs('#folderFormatsRetry').hidden = false;
    } finally { loading = false; controls(); }
  }

  input.addEventListener('change', () => {
    if (!formats || state.knowledgeUploadBusy) return;
    items = []; qs('#folderResult').hidden = true;
    const list = document.createDocumentFragment();
    for (const file of input.files) {
      const item = { file, path: file.webkitRelativePath || file.name, extension: file.name.match(/\.[^.]+$/)?.[0].toLowerCase() || '', status: 'ready' };
      const row = document.createElement('li'), name = document.createElement('strong');
      name.textContent = item.path; item.result = document.createElement('small'); row.append(name, item.result); list.append(row);
      if (!formats.extensions.includes(item.extension)) mark(item, 'skipped', 'Dilewati: format tidak didukung.');
      else if (!file.size) mark(item, 'skipped', 'Dilewati: file kosong.');
      else if (file.size > formats.max_upload_bytes) mark(item, 'skipped', 'Dilewati: melebihi batas ukuran.');
      else mark(item, 'ready', 'Siap diunggah.');
      items.push(item);
    }
    qs('#folderFileList').replaceChildren(list);
    qs('#folderDetails').hidden = !items.length;
    qs('#folderScan').textContent = `${items.length} file ditemukan: ${eligible().length} siap diproses, ${items.filter(item => item.status === 'skipped').length} dilewati.`;
    qs('#folderCurrent').textContent = 'Belum ada file yang diproses.';
    progress(); controls();
  });

  function sendFile(item) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      let lastPercent = -1;
      xhr.upload.addEventListener('progress', event => {
        if (!event.lengthComputable) return;
        const percent = Math.floor(event.loaded / event.total * 10) * 10;
        if (percent !== lastPercent) {
          lastPercent = percent;
          qs('#folderCurrent').textContent = `Mengirim ${item.path}: ${percent}% data terkirim.`;
        }
      });
      xhr.upload.addEventListener('load', () => {
        mark(item, 'indexing', 'Data terkirim; membaca dan mengindeks dokumen...');
        qs('#folderCurrent').textContent = `Mengindeks ${item.path}. Menunggu konfirmasi server...`;
      });
      xhr.open('POST', '/api/documents/upload');
      xhr.withCredentials = true; xhr.setRequestHeader('X-Requested-With', 'workspace');
      xhr.onload = () => {
        let data = {};
        try { data = JSON.parse(xhr.responseText); } catch (_) { /* rejected below */ }
        if (xhr.status === 401) location.replace('/login' + location.hash);
        if (xhr.status < 200 || xhr.status >= 300) {
          const error = new Error(Array.isArray(data.detail) ? data.detail.map(item => item.msg).join('; ') : data.detail || 'Server belum dapat memproses file.');
          error.status = xhr.status; error.retryAfter = Number(xhr.getResponseHeader('Retry-After')) || 1; reject(error);
        } else if (typeof data.indexed_chunks !== 'number') reject(new Error('Respons server tidak valid. Ulangi file untuk memeriksa hasilnya.'));
        else resolve(data);
      };
      xhr.onerror = xhr.onabort = () => reject(new Error('Pengiriman terputus. Ulangi file untuk memeriksa apakah sudah terindeks.'));
      const body = new FormData(); body.append('file', item.file, item.file.name); body.append('relative_path', item.path);
      xhr.send(body);
    });
  }

  async function waitForRetry(seconds) {
    await new Promise(resolve => {
      const timer = setTimeout(() => { wakeRetry = null; resolve(); }, seconds * 1000 + 250);
      wakeRetry = () => { clearTimeout(timer); wakeRetry = null; resolve(); };
    });
  }

  async function processFolder(queue = items) {
    if (state.knowledgeUploadBusy || !formats) return;
    running = true; paused = false; state.knowledgeUploadBusy = true;
    qs('#folderResult').hidden = true; form.setAttribute('aria-busy', 'true');
    document.dispatchEvent(new Event('knowledge-upload-state')); progress(); controls();
    try {
      for (const item of queue) {
        if (paused) break;
        if (item.status !== 'ready') continue;
        for (let attempt = 0; attempt < 3; attempt++) {
          mark(item, 'uploading', 'Sedang diunggah...');
          qs('#folderCurrent').textContent = `Mengunggah ${item.path}...`;
          try {
            const data = await sendFile(item);
            mark(item, data.skipped_duplicate ? 'duplicate' : 'success', data.skipped_duplicate ? 'Duplikat: sudah terindeks.' : `Terindeks: ${data.indexed_chunks} chunk, ${data.total_pages} halaman.`);
            break;
          } catch (error) {
            if (error.status === 429 && attempt < 2) {
              if (paused) { mark(item, 'ready', 'Belum diproses; lanjutkan setelah jeda.'); break; }
              const delay = Math.max(1, Math.min(60, error.retryAfter));
              mark(item, 'waiting', `Menunggu batas request ${delay} detik...`);
              qs('#folderCurrent').textContent = `${item.path}: batas request tercapai. Mencoba lagi dalam ${delay} detik.`;
              await waitForRetry(delay);
              if (paused) { mark(item, 'ready', 'Belum diproses; lanjutkan setelah jeda.'); break; }
              continue;
            }
            mark(item, 'failed', `Gagal: ${error.message}`);
            if ([401, 403, 429].includes(error.status)) paused = true;
            break;
          }
        }
        progress(); controls();
      }
    } finally {
      running = false; state.knowledgeUploadBusy = false; form.setAttribute('aria-busy', 'false');
      document.dispatchEvent(new Event('knowledge-upload-state')); progress(); controls();
      const count = status => items.filter(item => item.status === status).length;
      const pending = count('ready'), failed = count('failed');
      qs('#folderResult').hidden = false; qs('#folderResult').classList.toggle('error', failed > 0);
      qs('#folderResult').textContent = `${pending ? 'Proses dijeda.' : 'Pemrosesan selesai.'} ${count('success')} berhasil, ${count('duplicate')} duplikat, ${failed} gagal, ${count('skipped')} dilewati, ${pending} menunggu.`;
      qs('#folderCurrent').textContent = pending ? 'Klik Lanjutkan folder untuk memproses file yang menunggu.' : failed ? 'Ada file gagal. Periksa daftar hasil, lalu gunakan Ulangi file gagal.' : 'Seluruh file yang memenuhi syarat sudah selesai diproses.';
    }
  }

  form.addEventListener('submit', event => { event.preventDefault(); processFolder(); });
  qs('#folderPause').addEventListener('click', () => { paused = true; wakeRetry?.(); controls(); qs('#folderCurrent').textContent = 'Jeda diminta. File yang sedang diproses diselesaikan terlebih dahulu.'; });
  qs('#folderRetry').addEventListener('click', () => {
    if (state.knowledgeUploadBusy) return;
    const failed = items.filter(item => item.status === 'failed');
    failed.forEach(item => mark(item, 'ready', 'Siap dicoba ulang.'));
    processFolder(failed);
  });
  qs('#folderFormatsRetry').addEventListener('click', loadFormats);
  document.addEventListener('knowledge-upload-state', controls);
  document.addEventListener('workspace-view-changed', event => { if (event.detail.view === 'knowledge') loadFormats(); });
  workspaceReady.then(() => { if (qs('#knowledgeView').classList.contains('active')) loadFormats(); });
})();
