(() => {
  const enhancedDialogs = new WeakSet();
  const triggers = new WeakMap();

  function enhance(dialog) {
    if (!(dialog instanceof HTMLDialogElement) || dialog.classList.contains('app-dialog') || enhancedDialogs.has(dialog)) return;
    enhancedDialogs.add(dialog);

    const body = dialog.querySelector('.dialog-body');
    if (body && !body.querySelector('[data-form-dialog-close]')) {
      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'app-dialog-close';
      close.dataset.formDialogClose = 'true';
      close.setAttribute('aria-label', 'Close dialog');
      close.textContent = '×';
      body.prepend(close);
    }

    dialog.addEventListener('click', (event) => {
      if (event.target === dialog || event.target.closest('[data-form-dialog-close]')) dialog.close();
    });

    dialog.addEventListener('close', () => {
      const trigger = triggers.get(dialog);
      requestAnimationFrame(() => trigger?.focus?.({ preventScroll: true }));
    });
  }

  document.querySelectorAll('dialog.dialog').forEach(enhance);

  const originalShowModal = HTMLDialogElement.prototype.showModal;
  HTMLDialogElement.prototype.showModal = function showModalWithFocusReturn() {
    if (!this.classList.contains('app-dialog')) {
      triggers.set(this, document.activeElement);
      enhance(this);
    }
    return originalShowModal.call(this);
  };

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
      if (!(node instanceof Element)) return;
      if (node.matches('dialog.dialog')) enhance(node);
      node.querySelectorAll?.('dialog.dialog').forEach(enhance);
    }));
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
