(() => {
  document.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-api-form]');
    if (!form) return;
    event.preventDefault();

    const endpoint = form.dataset.endpoint;
    const method = form.dataset.method || 'POST';
    if (!endpoint || !endpoint.startsWith('/')) return;

    const submitButton = form.querySelector('[type="submit"]');
    const originalLabel = submitButton?.textContent;
    const payload = Object.fromEntries(new FormData(form).entries());

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = form.dataset.loadingLabel || 'Saving…';
    }
    window.appLoading.show(
      form.dataset.loadingTitle || 'Saving changes…',
      form.dataset.loadingDescription || 'Please keep this page open.'
    );

    try {
      const response = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'same-origin'
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.message || 'The request could not be completed');

      form.closest('dialog')?.close();
      form.reset();
      form.dispatchEvent(new CustomEvent('api-form-success', { bubbles: true, detail: result }));
      await window.appDialog.success({
        title: form.dataset.successTitle || 'Changes saved',
        message: result.message || form.dataset.successMessage || 'The changes were saved successfully.'
      });
    } catch (error) {
      form.dispatchEvent(new CustomEvent('api-form-error', { bubbles: true, detail: error }));
      await window.appDialog.error({
        title: form.dataset.errorTitle || 'Unable to save changes',
        message: error.message
      });
    } finally {
      window.appLoading.hide();
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = originalLabel;
      }
    }
  });
})();
