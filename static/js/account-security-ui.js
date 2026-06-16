(() => {
  const dialog = document.getElementById('accountSecurityDialog');
  const form = document.getElementById('accountSecurityForm');
  const nextValue = document.getElementById('nextCredential');
  const confirmValue = document.getElementById('confirmCredential');

  if (!dialog || !form || !nextValue || !confirmValue) return;

  document.addEventListener('open-account-security', () => {
    if (!dialog.open) dialog.showModal();
  });

  document.addEventListener('click', (event) => {
    const toggle = event.target.closest('[data-secure-toggle]');
    if (toggle) {
      const input = document.getElementById(toggle.dataset.secureToggle);
      const visible = input.classList.toggle('secure-entry-visible');
      toggle.textContent = visible ? 'Hide' : 'Show';
      input.focus({ preventScroll: true });
    }

    if (event.target.closest('[data-security-cancel]')) {
      dialog.close();
    }
  });

  function updateStrength() {
    const value = nextValue.value;
    let score = 0;
    if (value.length >= 8) score += 1;
    if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score += 1;
    if (/\d/.test(value)) score += 1;
    if (/[^A-Za-z0-9]/.test(value)) score += 1;
    document.querySelector('[data-secure-strength]').dataset.score = String(score);
  }

  function validateMatch() {
    confirmValue.setCustomValidity(
      confirmValue.value && nextValue.value !== confirmValue.value
        ? 'The confirmation does not match.'
        : ''
    );
  }

  nextValue.addEventListener('input', () => {
    updateStrength();
    validateMatch();
  });
  confirmValue.addEventListener('input', validateMatch);

  form.addEventListener('api-form-success', (event) => {
    document.querySelector('[data-secure-strength]').dataset.score = '0';
    document.querySelectorAll('.secure-entry-visible').forEach((input) => input.classList.remove('secure-entry-visible'));
    document.dispatchEvent(new CustomEvent('account-security-updated', { detail: event.detail }));
  });
})();
