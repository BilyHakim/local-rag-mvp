(() => {
  const form = qs('#accountForm'), passwordForm = qs('#accountPasswordForm');
  let profile = null, busy = false;
  const showError = message => { qs('#accountError').textContent = message; qs('#accountError').hidden = !message; if (message) qs('#accountError').scrollIntoView({ block: 'nearest' }); };

  function controls() {
    const editable = !!profile?.editable && !busy;
    form.querySelectorAll('input:not([readonly]), textarea, button').forEach(input => {
      input.disabled = !editable || (input.name === 'enabled_features' && !profile.available_features.includes(input.value));
    });
    passwordForm.querySelectorAll('input, button').forEach(input => { input.disabled = !editable; });
    qs('#accountReload').disabled = busy;
    form.setAttribute('aria-busy', String(busy));
    passwordForm.setAttribute('aria-busy', String(busy));
  }

  function render(data) {
    profile = data;
    if (data) {
      ['username', 'display_name', 'email', 'bio'].forEach(key => { form.elements[key].value = data[key] || ''; });
      form.elements.role.value = data.role === 'admin' ? 'Administrator' : 'Pembaca';
      form.querySelectorAll('[name="enabled_features"]').forEach(input => { input.checked = data.enabled_features.includes(input.value); });
      qs('#accountStatus').textContent = data.editable ? 'Perubahan disimpan untuk akun Anda dan tetap berlaku setelah login kembali.' : 'Login dengan akun workspace untuk mengedit profil dan password. Akses API key hanya dapat melihat informasi akun.';
    } else {
      qs('#accountStatus').textContent = 'Profil belum dapat dimuat. Klik Muat ulang profil untuk mencoba lagi.';
      showError(state.accountError || 'Periksa koneksi backend.');
    }
    controls();
  }

  async function run(button, task) {
    if (busy) return;
    busy = true; showError(''); const label = button.textContent; button.textContent = 'Memproses...'; controls();
    try { await task(); }
    catch (error) { showError(error.message); }
    finally { busy = false; button.textContent = label; controls(); }
  }

  qs('#accountReload').addEventListener('click', event => run(event.currentTarget, async () => {
    const data = await api('/api/account/profile'); applyAccountProfile(data); render(data); showToast('Profil dimuat ulang.');
  }));
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (!profile?.editable) return;
    run(qs('#accountSave'), async () => {
      const fields = form.elements;
      const data = await api('/api/account/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ revision: profile.revision, display_name: fields.display_name.value, email: fields.email.value, bio: fields.bio.value,
          enabled_features: [...form.querySelectorAll('[name="enabled_features"]:checked')].map(input => input.value) }) });
      applyAccountProfile(data); render(data); showToast('Profil dan pilihan fitur disimpan.');
    });
  });
  passwordForm.addEventListener('submit', event => {
    event.preventDefault();
    const fields = passwordForm.elements;
    if (fields.new_password.value !== fields.confirm_password.value) { showError('Ulangi password baru dengan nilai yang sama.'); fields.confirm_password.focus(); return; }
    run(qs('#accountPasswordSave'), async () => {
      try {
        const result = await api('/api/account/password', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ current_password: fields.current_password.value, new_password: fields.new_password.value }) });
        qs('#accountStatus').textContent = result.message; showToast(result.message);
      } finally { passwordForm.reset(); }
    });
  });
  workspaceReady.then(render);
})();
