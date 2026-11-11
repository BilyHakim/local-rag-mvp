function createChatEditor(element) {
  let formatting = false;
  const escape = text => text.replace(/([\\`*_[\]<>])/g, '\\$1');
  function markdown(node) {
    if (node.nodeType === Node.TEXT_NODE) return escape(node.textContent);
    const children = () => [...node.childNodes].map(markdown).join('');
    switch (node.nodeName) {
      case 'BR': return '\n';
      case 'B': case 'STRONG': return `**${children()}**`;
      case 'I': case 'EM': return `*${children()}*`;
      case 'CODE': return '`' + node.textContent.replace(/`/g, '\\`') + '`';
      case 'OL': case 'UL': {
        const start = Number(node.getAttribute('start')) || 1;
        return '\n' + [...node.children].map((item, index) => {
          const text = markdown(item).trim();
          return (node.nodeName === 'OL' ? `${start + index}. ` : '- ') + text.replace(/\n/g, '\n   ');
        }).join('\n') + '\n\n';
      }
      case 'BLOCKQUOTE': return '\n' + children().trim().split('\n').map(line => '> ' + line).join('\n') + '\n\n';
      case 'H1': case 'H2': case 'H3': case 'H4': case 'H5': case 'H6':
        return '\n' + '#'.repeat(Number(node.nodeName[1])) + ' ' + children() + '\n\n';
      case 'DIV': case 'P': return children() + '\n';
      default: return children();
    }
  }
  const value = () => [...element.childNodes].map(markdown).join('').trim();
  function currentBlock() {
    const selection = getSelection();
    if (!selection.rangeCount || !element.contains(selection.anchorNode)) return null;
    let node = selection.anchorNode.nodeType === Node.TEXT_NODE ? selection.anchorNode.parentElement : selection.anchorNode;
    return node.closest('li, p, div, h1, h2, h3, h4, h5, h6, blockquote');
  }
  function rules(event) {
    if (event.isComposing) return;
    if (!element.textContent.trim()) { element.replaceChildren(); return; }
    const selection = getSelection();
    if (!selection.isCollapsed || !selection.rangeCount) return;
    const block = currentBlock();
    if (!block || block.closest('li, pre')) return;
    const range = selection.getRangeAt(0);
    const before = range.cloneRange(); before.selectNodeContents(block); before.setEnd(range.endContainer, range.endOffset);
    const text = before.toString();
    const match = text.match(/^(\d{1,6})\.\s?(?=\S)|^(\d{1,6})\.\s$|^([-+*])\s$|^(#{1,6})\s$|^(>)\s$/);
    if (match && range.endContainer.nodeType === Node.TEXT_NODE) {
      const prefix = range.cloneRange(); prefix.setStart(range.endContainer, 0); prefix.setEnd(range.endContainer, match[0].length);
      selection.removeAllRanges(); selection.addRange(prefix);
      document.execCommand('delete');
      if (match[1] || match[2] || match[3]) {
        document.execCommand(match[3] ? 'insertUnorderedList' : 'insertOrderedList');
        const list = currentBlock()?.closest('ol');
        if (list && Number(match[1] || match[2]) !== 1) list.start = Number(match[1] || match[2]);
      } else document.execCommand('formatBlock', false, match[4] ? 'h' + match[4].length : 'blockquote');
      const active = currentBlock();
      if (active) { selection.selectAllChildren(active); selection.collapseToEnd(); }
    }
    const node = selection.anchorNode;
    if (node?.nodeType !== Node.TEXT_NODE || node.parentElement.closest('code')) return;
    const inline = node.textContent.slice(0, selection.anchorOffset).match(/\*\*([^*\n]+)\*\*$|(?<!\*)\*([^*\n]+)\*$|`([^`\n]+)`$/);
    if (!inline) return;
    const replacement = document.createElement(inline[1] ? 'strong' : inline[2] ? 'em' : 'code');
    replacement.textContent = inline[1] || inline[2] || inline[3];
    const target = document.createRange(); target.setStart(node, selection.anchorOffset - inline[0].length); target.setEnd(node, selection.anchorOffset);
    selection.removeAllRanges(); selection.addRange(target);
    document.execCommand('insertHTML', false, replacement.outerHTML);
    const tail = document.createTextNode('\u200b');
    const anchor = selection.anchorNode;
    const formatted = (anchor.nodeType === Node.TEXT_NODE ? anchor.parentElement : anchor).closest('strong, em, code');
    if (formatted) formatted.after(tail);
    else selection.getRangeAt(0).insertNode(tail);
    selection.collapse(tail, 1);
  }
  element.addEventListener('input', event => {
    if (formatting) return;
    formatting = true;
    try { rules(event); }
    finally { formatting = false; }
  });
  element.addEventListener('paste', event => {
    event.preventDefault();
    document.execCommand('insertText', false, event.clipboardData.getData('text/plain'));
  });
  element.addEventListener('drop', event => event.preventDefault());
  element.addEventListener('keydown', event => {
    if (event.isComposing || event.key !== 'Enter') return;
    if (event.ctrlKey || event.metaKey || (!event.shiftKey && !currentBlock()?.closest('li, blockquote, h1, h2, h3, h4, h5, h6'))) {
      event.preventDefault(); element.closest('form').requestSubmit();
    }
  });
  return {
    get value() { return value().replace(/\u200b/g, ''); },
    set value(text) { element.textContent = text; },
    set disabled(disabled) { element.contentEditable = String(!disabled); element.setAttribute('aria-disabled', String(disabled)); },
    focus(options) { element.focus(options); }
  };
}
