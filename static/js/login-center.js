(() => {
  const page = document.querySelector('.login-page');
  const panel = document.querySelector('.login-panel');
  const brand = document.querySelector('.login-brand');
  if (!page || !panel || !brand) return;

  function px(value) {
    return Number.parseFloat(value) || 0;
  }

  function updateLoginCardCenter() {
    panel.style.setProperty('--login-card-center-offset', '0px');
    page.classList.remove('login-layout-scroll');

    const viewportHeight = window.visualViewport?.height || window.innerHeight;
    const pageStyles = window.getComputedStyle(page);
    const paddingTop = px(pageStyles.paddingTop);
    const paddingBottom = px(pageStyles.paddingBottom);
    const safeTop = paddingTop + 12;
    const requiredHeight = panel.scrollHeight + paddingTop + paddingBottom;

    if (viewportHeight <= 760 || requiredHeight > viewportHeight) {
      page.classList.add('login-layout-scroll');
      return;
    }

    const brandStyles = window.getComputedStyle(brand);
    const marginBottom = px(brandStyles.marginBottom);
    const precedingHeight = brand.getBoundingClientRect().height + marginBottom;
    const desiredOffset = precedingHeight / 2;

    const naturalTop = panel.getBoundingClientRect().top;
    const availableShift = Math.max(0, naturalTop - safeTop);
    const safeOffset = Math.min(desiredOffset, availableShift);

    panel.style.setProperty('--login-card-center-offset', `${Math.round(safeOffset)}px`);
  }

  updateLoginCardCenter();
  window.addEventListener('load', updateLoginCardCenter, { once: true });
  window.addEventListener('resize', updateLoginCardCenter, { passive: true });
  window.visualViewport?.addEventListener('resize', updateLoginCardCenter, { passive: true });
  window.visualViewport?.addEventListener('scroll', updateLoginCardCenter, { passive: true });
  document.fonts?.ready?.then(updateLoginCardCenter);

  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(updateLoginCardCenter);
    observer.observe(brand);
    observer.observe(panel);
  }
})();
