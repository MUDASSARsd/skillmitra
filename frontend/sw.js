// SkillMitra PWA Service Worker for Offline Resilience
const CACHE_NAME = 'skillmitra-v4';
const STATIC_ASSETS = [
  '/app',
  '/ui/styles.css?v=46',
  '/ui/app.js?v=46',
  '/ui/manifest.json',
  '/ui/icon-192.png',
  '/ui/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('Pre-cache error (non-fatal):', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) return caches.delete(key);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Only cache GET requests for static UI assets; dynamic API calls go directly to the server
  if (event.request.method === 'GET' && (url.pathname === '/app' || url.pathname.startsWith('/ui/'))) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
  }
});
