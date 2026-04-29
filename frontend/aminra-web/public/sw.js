// AMINRA Service Worker — offline caching for audit field use
const CACHE_NAME = 'aminra-v4';
const OFFLINE_URL = '/audits';
// URLs the SW must NEVER serve from cache (always go to network).
// Admin rotates template content; serving stale = wrong file delivered.
const NEVER_CACHE_PATTERNS = [
  /\/api\/templates\//,
  /\/api\/admin\/templates\/.*\/template-file\/view/,
  /\/api\/admin\/templates\/.*\/files\/.*\/view/,
];

// Cache critical assets on install
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        OFFLINE_URL,
        '/audits/templates',
      ]);
    })
  );
  self.skipWaiting();
});

// Clean old caches on activate
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Network-first strategy for API calls, cache-first for pages
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests (POST/PUT for checklist updates go to IndexedDB queue)
  if (request.method !== 'GET') return;

  // API calls: network-first, fallback to cache
  if (url.pathname.startsWith('/api/')) {
    // Some endpoints (template downloads) MUST never be served from cache —
    // admin rotates content, stale = wrong template delivered to business.
    const skipCache = NEVER_CACHE_PATTERNS.some((re) => re.test(url.pathname));
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (!skipCache && response.ok && request.url.includes('/api/api/audits/')) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => skipCache ? Response.error() : caches.match(request))
    );
    return;
  }

  // Pages: network-first, fallback to cache, then offline page
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => {
        return caches.match(request).then((cached) => {
          return cached || caches.match(OFFLINE_URL);
        });
      })
  );
});

// Web push: show notification when server pushes via VAPID
self.addEventListener('push', (event) => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch (e) { payload = { title: event.data ? event.data.text() : 'AMINRA' }; }
  const title = payload.title || 'AMINRA';
  const options = {
    body: payload.message || '',
    icon: '/aminra-mark.png',
    badge: '/aminra-mark.png',
    data: { link: payload.link || '/', notification_id: payload.notification_id || null },
    tag: payload.tag || payload.notification_id || undefined,
    requireInteraction: false,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Click on notification → open or focus the linked URL
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const link = (event.notification.data && event.notification.data.link) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ('focus' in w) {
          w.navigate(link).catch(() => {});
          return w.focus();
        }
      }
      return self.clients.openWindow(link);
    })
  );
});

// Listen for sync events (for queued offline checklist updates)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-audit-data') {
    event.waitUntil(syncAuditData());
  }
});

async function syncAuditData() {
  // Read queued updates from IndexedDB and POST them
  try {
    const db = await openDB();
    const tx = db.transaction('sync-queue', 'readonly');
    const store = tx.objectStore('sync-queue');
    const items = await getAllFromStore(store);

    for (const item of items) {
      try {
        await fetch(item.url, {
          method: item.method,
          headers: item.headers,
          body: item.body,
        });
        // Remove from queue on success
        const delTx = db.transaction('sync-queue', 'readwrite');
        delTx.objectStore('sync-queue').delete(item.id);
      } catch (e) {
        // Keep in queue for next sync
      }
    }
  } catch (e) {
    // IndexedDB not available
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('aminra-offline', 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('sync-queue')) {
        db.createObjectStore('sync-queue', { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function getAllFromStore(store) {
  return new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
