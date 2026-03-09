/* Minimal service worker for PWA shell.
   Cache static assets; keep pages network-first. */
const CACHE_NAME = 'ahelp-shell-v7';
const STATIC_ASSETS = [
  '/static/app.css',
  '/static/icon.svg',
  '/static/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k === CACHE_NAME ? Promise.resolve() : caches.delete(k))))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET') return;

  // Only handle same-origin
  if (url.origin !== self.location.origin) return;

  // Cache-first for static
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(()=>{});
        return res;
      }))
    );
    return;
  }

  // Network-first for pages/APIs
  event.respondWith(
    fetch(req).catch(() => caches.match('/post'))
  );
});

