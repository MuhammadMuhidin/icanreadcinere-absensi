const CACHE_NAME = 'icr-v1';
const STATIC_ASSETS = [
  '/static/css/app.css',
  '/static/css/refinement.css',
  '/static/css/micro-fixes.css',
  '/static/css/premium.css',
  '/static/css/popup-center.css',
  '/static/css/route-skeleton.css',
  '/static/css/inbox.css',
  '/static/css/account-details.css',
  '/static/css/home-card-interactions.css',
  '/static/css/development.css',
  '/static/css/login.css',
  '/static/css/login-center.css',
  '/static/css/login-logo-original.css',
  '/static/css/paid_leave.css',
  '/static/css/upload.css',
  '/static/js/app.js',
  '/static/js/dialog.js',
  '/static/js/dialog-polish.js',
  '/static/js/api-form.js',
  '/static/js/home-details.js',
  '/static/js/account-security-ui.js',
  '/static/js/inbox-badge.js',
  '/static/Logo.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;

  // API calls: network only, never cache
  if (url.pathname.startsWith('/api/') || url.pathname === '/change_photo' || url.pathname === '/leave') {
    return;
  }

  // R2 profile images: stale-while-revalidate with 1h TTL
  if (url.hostname.includes('r2.') || url.hostname.includes('cloudflare') || url.pathname.includes('/profiles/')) {
    event.respondWith(staleWhileRevalidate(request, 3600000));
    return;
  }

  // Static assets: cache first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // HTML pages: stale-while-revalidate
  event.respondWith(staleWhileRevalidate(request, 300000));
});

function cacheFirst(request) {
  return caches.match(request).then((cached) => {
    if (cached) return cached;
    return fetch(request).then((response) => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    });
  });
}

function staleWhileRevalidate(request, ttl) {
  return caches.match(request).then((cached) => {
    const isExpired = cached && cached.headers.get('sw-cached-at')
      && Date.now() - parseInt(cached.headers.get('sw-cached-at')) > ttl;

    const fetchPromise = fetch(request).then((response) => {
      if (response.ok) {
        const clone = response.clone();
        const headers = new Headers(clone.headers);
        headers.set('sw-cached-at', Date.now().toString());
        const toCache = new Response(clone.body, {
          status: clone.status,
          statusText: clone.statusText,
          headers
        });
        caches.open(CACHE_NAME).then((c) => c.put(request, toCache));
      }
      return response;
    }).catch(() => cached);

    // Return cached immediately if not expired, refresh in background
    if (cached && !isExpired) {
      // Refresh in background
      fetchPromise.catch(() => {});
      return cached;
    }

    return fetchPromise;
  });
}
