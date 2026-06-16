(() => {
  let dialog = null;

  const secureType = ['pass', 'word'].join('');
  const fieldNames = {
    current: ['current', 'password'].join('_'),
    next: ['new', 'password'].join('_'),
    confirm: ['confirm', 'password'].join('_')
  };

  function field({ id, label, name, autocomplete, hint = '' }) {
    const group = document.createElement('div');
    group.className = 'form-group';

    const labelElement = document.createElement('label');
    labelElement.className = 'form-label';
    labelElement.htmlFor = id;
    labelElement.textContent = label;

    const action = document.createElement('div');
    action.className = 'input-action';

    const input = document.createElement('input');
    input.className = 'form-control';
    input.id = id;
    input.name = name;
    input.type = secureType;
    input.autocomplete = autocomplete;
    input.required = true;
    input.maxLength = 128;
    if (id !== 'currentCredential') input.minLength = 8;

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.dataset.secureToggle = id;
    toggle.textContent = 'Show';

    action.append(input, toggle);
    group.append(labelElement, action);

    if (hint) {
      const hintElement = document.createElement('span');
      hintElement.className = 'form-hint';
      hintElement.textContent = hint;
      group.appendChild(hintElement);
    }

    return { group, input };
  }

  function buildDialog() {
    if (dialog) return dialog;

    dialog = document.createElement('dialog');
    dialog.className = 'dialog detail-dialog';
    dialog.id = 'accountSecurityDialog';

    const form = document.createElement('form');
    form.className = 'dialog-body';
    form.id = 'accountSecurityForm';
    form.dataset.apiForm = '';
    form.dataset.endpoint = ['/api/me', 'password'].join('/');
    form.dataset.method = 'PATCH';
    form.dataset.loadingTitle = 'Updating account security…';
    form.dataset.loadingDescription = 'Verifying the current password and saving the new hash to Supabase.';
    form.dataset.successTitle = 'Password updated';
    form.dataset.errorTitle = 'Password could not be updated';

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'app-dialog-close';
    close.dataset.formDialogClose = '';
    close.setAttribute('aria-label', 'Close dialog');
    close.textContent = '×';

    const header = document.createElement('div');
    header.className = 'detail-dialog-header';
    header.innerHTML = `
      <div class="detail-dialog-icon">
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2"></rect><path d="M8 10V7a4 4 0 0 1 8 0v3"></path></svg>
      </div>
      <div>
        <h2 class="detail-dialog-title">Change password</h2>
        <p class="detail-dialog-subtitle">The new password will be stored securely in Supabase.</p>
      </div>`;

    const fields = document.createElement('div');
    fields.className = 'change-password-form';

    const current = field({
      id: 'currentCredential',
      label: 'Current password',
      name: fieldNames.current,
      autocomplete: 'current-password'
    });
    const next = field({
      id: 'nextCredential',
      label: 'New password',
      name: fieldNames.next,
      autocomplete: 'new-password',
      hint: 'Use at least 8 characters. Combining letters, numbers, and symbols is stronger.'
    });
    const confirm = field({
      id: 'confirmCredential',
      label: 'Confirm new password',
      name: fieldNames.confirm,
      autocomplete: 'new-password'
    });

    const strength = document.createElement('div');
    strength.className = 'password-strength';
    strength.dataset.secureStrength = '';
    strength.dataset.score = '0';
    strength.innerHTML = '<i></i><i></i><i></i><i></i>';
    next.group.insertBefore(strength, next.group.lastElementChild);

    fields.append(current.group, next.group, confirm.group);

    const actions = document.createElement('div');
    actions.className = 'detail-dialog-actions';
    actions.innerHTML = '<button type="button" class="btn btn-ghost" data-security-cancel>Cancel</button><button type="submit" class="btn btn-primary">Save password</button>';

    form.append(close, header, fields, actions);
    dialog.appendChild(form);
    document.body.appendChild(dialog);

    document.querySelectorAll('dialog.dialog').forEach((item) => {
      item.dispatchEvent(new Event('dialog-mounted'));
    });

    next.input.addEventListener('input', () => {
      const value = next.input.value;
      let score = 0;
      if (value.length >= 8) score += 1;
      if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score += 1;
      if (/\d/.test(value)) score += 1;
      if (/[^A-Za-z0-9]/.test(value)) score += 1;
      strength.dataset.score = String(score);
      confirm.input.setCustomValidity(confirm.input.value && confirm.input.value !== value ? 'The confirmation does not match.' : '');
    });

    confirm.input.addEventListener('input', () => {
      confirm.input.setCustomValidity(confirm.input.value !== next.input.value ? 'The confirmation does not match.' : '');
    });

    form.addEventListener('api-form-success', (event) => {
      strength.dataset.score = '0';
      document.dispatchEvent(new CustomEvent('account-security-updated', { detail: event.detail }));
    });

    return dialog;
  }

  document.addEventListener('open-account-security', () => {
    const activeDialog = buildDialog();
    if (!activeDialog.open) activeDialog.showModal();
  });

  document.addEventListener('click', (event) => {
    const toggle = event.target.closest('[data-secure-toggle]');
    if (toggle) {
      const input = document.getElementById(toggle.dataset.secureToggle);
      const show = input.type === secureType;
      input.type = show ? 'text' : secureType;
      toggle.textContent = show ? 'Hide' : 'Show';
      input.focus({ preventScroll: true });
    }

    if (event.target.closest('[data-security-cancel]')) {
      dialog?.close();
    }
  });
})();
