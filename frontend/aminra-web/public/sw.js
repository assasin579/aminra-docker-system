// AMINRA Service Worker — offline caching for audit field use
const CACHE_NAME = 'aminra-v1';
const OFFLINE_URL = '/audits';

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
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache successful API responses for offline reading
          if (response.ok && request.url.includes('/api/api/audits/')) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
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
