const form = document.querySelector('#loginForm');
const button = document.querySelector('#loginSubmit');
const error = document.querySelector('#loginError');
const themeButton = document.querySelector('#loginTheme');
function setLoginTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeButton.textContent = theme === 'dark' ? 'Mode terang' : 'Mode gelap';
}
setLoginTheme(localStorage.getItem('rag-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
themeButton.addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  setLoginTheme(theme); localStorage.setItem('rag-theme', theme);
});
document.querySelector('#showPassword').addEventListener('change', event => {
  form.elements.password.type = event.target.checked ? 'text' : 'password';
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (button.disabled) return;
  const username = form.elements.username.value.trim();
  const password = form.elements.password.value;
  button.disabled = true; button.textContent = 'Memeriksa...';
  form.setAttribute('aria-busy', 'true'); error.hidden = true;
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'workspace' },
      body: JSON.stringify({ username, password }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Periksa username dan password Anda.');
    form.elements.password.value = '';
    location.replace('/' + location.hash);
  } catch (failure) {
    error.textContent = failure instanceof TypeError ? 'Server tidak dapat dihubungi. Periksa koneksi lalu coba lagi.' : failure.message;
    error.hidden = false;
    form.elements.password.value = ''; form.elements.password.focus();
  } finally {
    button.disabled = false; button.textContent = 'Masuk'; form.setAttribute('aria-busy', 'false');
  }
});
