const CACHE_NAME = 'million-hakbah-cache-v1';
const OFFLINE_URL = '/offline';
const PRECACHE_URLS = [
  '/',
  '/login',
  OFFLINE_URL,
  '/static/style.css',
  '/static/manifest.json',
  '/staff/dashboard'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
      .catch(err => console.warn('SW install failed:', err))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') {
    return;
  }

  const requestURL = new URL(event.request.url);
  const isSameOrigin = requestURL.origin === location.origin;

  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, responseClone));
          return response;
        })
        .catch(async () => {
          const cachedResponse = await caches.match(event.request);
          return cachedResponse || caches.match(OFFLINE_URL);
        })
    );
    return;
  }

  if (!isSameOrigin) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request)
        .then(response => {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, responseClone));
          return response;
        })
        .catch(() => {
          if (event.request.destination === 'document') {
            return caches.match(OFFLINE_URL);
          }
          return new Response('', { status: 503, statusText: 'offline' });
        });
    })
  );
});
