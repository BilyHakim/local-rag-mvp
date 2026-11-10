const chatMarkdown = window.markdownit({ html: false, breaks: true, linkify: false, typographer: false });
chatMarkdown.validateLink = value => {
  try { return ['http:', 'https:', 'mailto:'].includes(new URL(value).protocol); }
  catch (_) { return false; }
};
chatMarkdown.renderer.rules.image = (tokens, index) => chatMarkdown.utils.escapeHtml(tokens[index].content);
chatMarkdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  tokens[index].attrSet('target', '_blank');
  tokens[index].attrSet('rel', 'noopener noreferrer');
  return renderer.renderToken(tokens, index, options);
};
for (const rule of ['heading_open', 'heading_close']) {
  chatMarkdown.renderer.rules[rule] = (tokens, index, options, env, renderer) => {
    tokens[index].tag = 'h' + Math.min(6, Number(tokens[index].tag.slice(1)) + 1);
    return renderer.renderToken(tokens, index, options);
  };
}

function renderChatMarkdown(text, copyText) {
  const content = document.createElement('div'); content.className = 'markdown-body';
  content.innerHTML = chatMarkdown.render(text);
  content.querySelectorAll('table').forEach(table => {
    const region = document.createElement('div'); region.className = 'markdown-table';
    region.tabIndex = 0; region.setAttribute('role', 'region'); region.setAttribute('aria-label', 'Tabel jawaban');
    table.before(region); region.append(table);
  });
  content.querySelectorAll('pre').forEach(pre => {
    const code = pre.querySelector('code');
    const block = document.createElement('div'); block.className = 'markdown-code';
    const toolbar = document.createElement('div'); toolbar.className = 'markdown-code-toolbar';
    const language = document.createElement('span'); language.textContent = code.className.replace(/^language-/, '') || 'Kode';
    const button = document.createElement('button'); button.type = 'button'; button.className = 'workspace-button';
    button.textContent = 'Salin kode'; button.addEventListener('click', () => copyText(code.textContent));
    toolbar.append(language, button); pre.before(block); block.append(toolbar, pre);
    pre.tabIndex = 0; pre.setAttribute('role', 'region'); pre.setAttribute('aria-label', 'Blok kode ' + language.textContent);
  });
  return content;
}
