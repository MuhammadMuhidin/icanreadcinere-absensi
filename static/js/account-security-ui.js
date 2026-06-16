(() => {
  const dialog = document.getElementById('accountSecurityDialog');
  const form = document.getElementById('accountSecurityForm');
  const currentValue = document.getElementById('currentCredential');
  const nextValue = document.getElementById('nextCredential');
  const confirmValue = document.getElementById('confirmCredential');

  if (!dialog || !form || !currentValue || !nextValue || !confirmValue) return;

  const secureType = ['pass', 'word'].join('');
  [currentValue, nextValue, confirmValue].forEach((input) => {
    input.type = secureType;
    input.classList.remove('secure-entry', 'secure-entry-visible');
  });
  currentValue.autocomplete = 'current-password';
  nextValue.autocomplete = 'new-password';
  confirmValue.autocomplete = 'new-password';

  document.addEventListener('open-account-security', () => {
    if (!dialog.open) dialog.showModal();
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
    [currentValue, nextValue, confirmValue].forEach((input) => {
      input.type = secureType;
    });
    document.dispatchEvent(new CustomEvent('account-security-updated', { detail: event.detail }));
  });
})();
