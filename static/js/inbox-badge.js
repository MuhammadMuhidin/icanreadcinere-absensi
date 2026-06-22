(() => {
  const badges = [...document.querySelectorAll('[data-inbox-count]')];
  if (!badges.length) return;

  // Skip on slow connections
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (connection?.saveData || /(^|-)2g$/.test(connection?.effectiveType || "")) return;

  const render = (count) => {
    badges.forEach((badge) => {
      badge.textContent = count > 99 ? '99+' : String(count);
      badge.hidden = count <= 0;
    });
  };

  fetch('/api/notifications/unread-count', {
    headers: { Accept: 'application/json' },
    cache: 'default'
  })
    .then((response) => response.ok ? response.json() : { count: 0 })
    .then((payload) => render(Number(payload.count) || 0))
    .catch(() => render(0));
})();
