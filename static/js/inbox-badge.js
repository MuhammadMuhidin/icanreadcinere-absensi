(() => {
  const badges = [...document.querySelectorAll('[data-inbox-count]')];
  if (!badges.length) return;

  const render = (count) => {
    badges.forEach((badge) => {
      badge.textContent = count > 99 ? '99+' : String(count);
      badge.hidden = count <= 0;
    });
  };

  fetch('/api/notifications/unread-count', {
    headers: { Accept: 'application/json' },
    cache: 'no-store'
  })
    .then((response) => response.ok ? response.json() : { count: 0 })
    .then((payload) => render(Number(payload.count) || 0))
    .catch(() => render(0));
})();
