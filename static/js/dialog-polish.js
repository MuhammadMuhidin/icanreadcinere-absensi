(() => {
  const enhancedDialogs = new WeakSet();
  const triggers = new WeakMap();

  const themeIcons = {
    light: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>',
    dark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20.5 14.3A8.5 8.5 0 0 1 9.7 3.5 8.5 8.5 0 1 0 20.5 14.3Z"></path></svg>'
  };

  function renderThemeIcons() {
    const dark = document.documentElement.dataset.theme === 'dark';
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      button.innerHTML = dark ? themeIcons.light : themeIcons.dark;
      button.setAttribute('aria-label', dark ? 'Use light mode' : 'Use dark mode');
      button.setAttribute('title', dark ? 'Use light mode' : 'Use dark mode');
    });
  }

  function syncDialogLayout(dialog) {
    const actions = dialog.querySelector('.dialog-actions');
    if (!actions) return;
    actions.style.display = 'grid';
    actions.style.gridTemplateColumns = window.matchMedia('(max-width: 520px)').matches
      ? '1fr'
      : 'repeat(2, minmax(0, 1fr))';
    actions.querySelectorAll('.btn').forEach((button) => button.style.width = '100%');
  }

  function enhance(dialog) {
    if (!(dialog instanceof HTMLDialogElement) || dialog.classList.contains('app-dialog') || enhancedDialogs.has(dialog)) return;
    enhancedDialogs.add(dialog);

    const body = dialog.querySelector('.dialog-body');
    if (body) body.style.position = 'relative';
    if (body && !body.querySelector('[data-form-dialog-close]')) {
      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'app-dialog-close';
      close.dataset.formDialogClose = 'true';
      close.setAttribute('aria-label', 'Close dialog');
      close.textContent = '×';
      body.prepend(close);
    }

    syncDialogLayout(dialog);

    dialog.addEventListener('click', (event) => {
      if (event.target === dialog || event.target.closest('[data-form-dialog-close]')) dialog.close();
    });

    dialog.addEventListener('close', () => {
      const trigger = triggers.get(dialog);
      requestAnimationFrame(() => trigger?.focus?.({ preventScroll: true }));
    });
  }

  document.querySelectorAll('dialog.dialog').forEach(enhance);
  renderThemeIcons();

  const originalShowModal = HTMLDialogElement.prototype.showModal;
  HTMLDialogElement.prototype.showModal = function showModalWithFocusReturn() {
    if (!this.classList.contains('app-dialog')) {
      triggers.set(this, document.activeElement);
      enhance(this);
      syncDialogLayout(this);
    }
    return originalShowModal.call(this);
  };

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-theme-toggle]')) requestAnimationFrame(renderThemeIcons);
  });

  window.addEventListener('resize', () => {
    document.querySelectorAll('dialog.dialog:not(.app-dialog)').forEach(syncDialogLayout);
  }, { passive: true });

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
      if (!(node instanceof Element)) return;
      if (node.matches('dialog.dialog')) enhance(node);
      node.querySelectorAll?.('dialog.dialog').forEach(enhance);
      if (node.matches('[data-theme-toggle]') || node.querySelector?.('[data-theme-toggle]')) renderThemeIcons();
    }));
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
