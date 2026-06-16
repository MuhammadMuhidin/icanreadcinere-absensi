(() => {
  const iconPaths = {
    info: '<circle cx="12" cy="12" r="9"></circle><path d="M12 10v6"></path><path d="M12 7h.01"></path>',
    success: '<path d="M20 6 9 17l-5-5"></path>',
    warning: '<path d="M10.3 3.6 2.4 17.2A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.8L13.7 3.6a2 2 0 0 0-3.4 0Z"></path><path d="M12 9v4"></path><path d="M12 16h.01"></path>',
    danger: '<path d="M12 9v4"></path><path d="M12 16h.01"></path><circle cx="12" cy="12" r="9"></circle>',
    question: '<circle cx="12" cy="12" r="9"></circle><path d="M9.8 9a2.4 2.4 0 1 1 3.8 1.9c-.9.6-1.6 1.1-1.6 2.1"></path><path d="M12 16h.01"></path>'
  };

  let activeResolver = null;
  let activeMode = 'alert';
  let lastFocused = null;

  function normaliseOptions(input, defaults = {}) {
    if (typeof input === 'string') return { ...defaults, message: input };
    return { ...defaults, ...(input || {}) };
  }

  function buildDialog() {
    if (document.getElementById('appDialog')) return document.getElementById('appDialog');

    const dialog = document.createElement('dialog');
    dialog.id = 'appDialog';
    dialog.className = 'dialog app-dialog';
    dialog.setAttribute('aria-labelledby', 'appDialogTitle');
    dialog.setAttribute('aria-describedby', 'appDialogMessage');
    dialog.innerHTML = `
      <div class="app-dialog-shell">
        <div class="app-dialog-accent" aria-hidden="true"></div>
        <button type="button" class="app-dialog-close" data-dialog-close aria-label="Close dialog">×</button>
        <div class="app-dialog-head">
          <div class="app-dialog-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" data-dialog-icon></svg>
          </div>
          <div>
            <h2 class="app-dialog-title" id="appDialogTitle"></h2>
          </div>
        </div>
        <p class="app-dialog-message" id="appDialogMessage"></p>
        <div class="app-dialog-field" data-dialog-field hidden>
          <label class="form-label" for="appDialogInput" data-dialog-input-label>Additional information</label>
          <textarea class="form-control app-dialog-input" id="appDialogInput" maxlength="500"></textarea>
          <span class="form-hint" data-dialog-input-hint hidden></span>
        </div>
        <div class="app-dialog-actions" data-dialog-actions>
          <button type="button" class="btn btn-ghost" data-dialog-cancel>Cancel</button>
          <button type="button" class="btn btn-primary" data-dialog-confirm>Continue</button>
        </div>
      </div>
    `;

    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      settle(activeMode === 'prompt' ? null : false);
    });

    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) settle(activeMode === 'prompt' ? null : false);
      if (event.target.closest('[data-dialog-close], [data-dialog-cancel]')) {
        settle(activeMode === 'prompt' ? null : false);
      }
      if (event.target.closest('[data-dialog-confirm]')) {
        if (activeMode === 'prompt') {
          const input = dialog.querySelector('#appDialogInput');
          if (input.required && !input.value.trim()) {
            input.focus();
            input.setAttribute('aria-invalid', 'true');
            return;
          }
          settle(input.value.trim());
        } else {
          settle(true);
        }
      }
    });

    dialog.querySelector('#appDialogInput').addEventListener('input', (event) => {
      event.target.removeAttribute('aria-invalid');
    });

    document.body.appendChild(dialog);
    return dialog;
  }

  function settle(value) {
    const dialog = document.getElementById('appDialog');
    if (!dialog?.open) return;
    dialog.close();
    const resolver = activeResolver;
    activeResolver = null;
    setTimeout(() => lastFocused?.focus?.({ preventScroll: true }), 0);
    resolver?.(value);
  }

  function open(options) {
    const dialog = buildDialog();
    if (dialog.open) dialog.close();

    lastFocused = document.activeElement;
    activeMode = options.mode || 'alert';
    dialog.dataset.tone = options.tone || 'info';

    const title = dialog.querySelector('#appDialogTitle');
    const message = dialog.querySelector('#appDialogMessage');
    const icon = dialog.querySelector('[data-dialog-icon]');
    const field = dialog.querySelector('[data-dialog-field]');
    const input = dialog.querySelector('#appDialogInput');
    const inputLabel = dialog.querySelector('[data-dialog-input-label]');
    const inputHint = dialog.querySelector('[data-dialog-input-hint]');
    const cancelButton = dialog.querySelector('[data-dialog-cancel]');
    const confirmButton = dialog.querySelector('[data-dialog-confirm]');
    const actions = dialog.querySelector('[data-dialog-actions]');

    title.textContent = options.title || 'Please confirm';
    message.textContent = options.message || '';
    icon.innerHTML = iconPaths[options.icon || options.tone] || iconPaths.info;

    confirmButton.textContent = options.confirmText || (activeMode === 'alert' ? 'Got it' : 'Continue');
    confirmButton.className = `btn ${options.confirmClass || (options.tone === 'danger' ? 'btn-danger' : options.tone === 'success' ? 'btn-success' : 'btn-primary')}`;

    cancelButton.textContent = options.cancelText || 'Cancel';
    cancelButton.hidden = activeMode === 'alert';
    actions.classList.toggle('single', activeMode === 'alert');

    const showField = activeMode === 'prompt';
    field.hidden = !showField;
    if (showField) {
      input.value = options.value || '';
      input.placeholder = options.placeholder || '';
      input.required = options.required !== false;
      inputLabel.textContent = options.inputLabel || 'Additional information';
      inputHint.textContent = options.inputHint || '';
      inputHint.hidden = !options.inputHint;
      input.removeAttribute('aria-invalid');
    }

    return new Promise((resolve) => {
      activeResolver = resolve;
      dialog.showModal();
      requestAnimationFrame(() => {
        if (showField) input.focus();
        else confirmButton.focus();
      });
    });
  }

  window.appDialog = {
    alert(input) {
      return open(normaliseOptions(input, {
        mode: 'alert',
        tone: 'info',
        icon: 'info',
        title: 'Information',
        confirmText: 'Got it'
      }));
    },
    confirm(input) {
      return open(normaliseOptions(input, {
        mode: 'confirm',
        tone: 'warning',
        icon: 'question',
        title: 'Please confirm',
        confirmText: 'Continue',
        cancelText: 'Cancel'
      }));
    },
    prompt(input) {
      return open(normaliseOptions(input, {
        mode: 'prompt',
        tone: 'warning',
        icon: 'question',
        title: 'Additional information',
        confirmText: 'Continue',
        cancelText: 'Cancel',
        required: true
      }));
    },
    success(input) {
      return open(normaliseOptions(input, {
        mode: 'alert',
        tone: 'success',
        icon: 'success',
        title: 'Completed',
        confirmText: 'Done'
      }));
    },
    error(input) {
      return open(normaliseOptions(input, {
        mode: 'alert',
        tone: 'danger',
        icon: 'danger',
        title: 'Unable to continue',
        confirmText: 'Close'
      }));
    }
  };
})();
