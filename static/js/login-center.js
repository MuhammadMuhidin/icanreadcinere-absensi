(() => {
  const panel = document.querySelector('.login-panel');
  const brand = document.querySelector('.login-brand');
  if (!panel || !brand) return;

  function updateLoginCardCenter() {
    const viewportHeight = window.visualViewport?.height || window.innerHeight;

    if (viewportHeight <= 760) {
      panel.style.setProperty('--login-card-center-offset', '0px');
      return;
    }

    const brandStyles = window.getComputedStyle(brand);
    const marginBottom = Number.parseFloat(brandStyles.marginBottom) || 0;
    const precedingHeight = brand.getBoundingClientRect().height + marginBottom;
    const offset = Math.max(0, precedingHeight / 2);

    panel.style.setProperty('--login-card-center-offset', `${Math.round(offset)}px`);
  }

  updateLoginCardCenter();
  window.addEventListener('load', updateLoginCardCenter, { once: true });
  window.addEventListener('resize', updateLoginCardCenter, { passive: true });
  window.visualViewport?.addEventListener('resize', updateLoginCardCenter, { passive: true });
  document.fonts?.ready?.then(updateLoginCardCenter);

  if ('ResizeObserver' in window) {
    new ResizeObserver(updateLoginCardCenter).observe(brand);
  }
})();
