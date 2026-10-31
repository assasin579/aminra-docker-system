// AMINRA Service Worker — offline caching for audit field use
const CACHE_NAME = "aminra-v10";
const OFFLINE_URL = "/offline.html";
// URLs the SW must NEVER serve from cache (always go to network).
// Auth/admin identity paths are account-switch critical: cached responses/pages
// can resurrect a prior browser profile after logout/login as another account.
const NEVER_CACHE_PATTERNS = [
  /\/auth(?:\/|$)/,
  /\/admin(?:\/|$)/,
  /\/dashboard(?:\/|$)/,
  /\/business\/login(?:\/|$)/,
  /\/provider\/login(?:\/|$)/,
  /\/api\/auth(?:\/|$)/,
  /\/api\/api\/auth(?:\/|$)/,
  /\/api\/admin(?:\/|$)/,
  /\/api\/api\/admin(?:\/|$)/,
  /\/api\/me(?:\/|$)/,
  /\/api\/users\/me(?:\/|$)/,
  /\/api\/templates\//,
  /\/api\/admin\/templates\/.*\/template-file\/view/,
  /\/api\/admin\/templates\/.*\/files\/.*\/view/,
];

// Cache critical assets on install
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([OFFLINE_URL]);
    }),
  );
  self.skipWaiting();
});

// Clean old caches on activate
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key)),
      );
    }),
  );
  self.clients.claim();
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

// Network-first strategy for API calls, cache-first for pages
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests (POST/PUT for checklist updates go to IndexedDB queue)
  if (request.method !== "GET") return;

  // Skip cross-origin requests entirely. Keycloak SSO + Sentry tunnel
  // + any 3rd-party fetch must NOT route through our offline cache —
  // when fetch fails, we'd serve our OFFLINE_URL HTML which breaks
  // JSON-expecting clients (oidc-client-ts metadata fetch).
  if (url.origin !== self.location.origin) return;

  // Auth/admin pages must never be served from the offline page cache.
  // Stale cached Next.js routes or chunks can resurrect old auth guards and
  // look like an "immediate logout" after the Keycloak callback.
  const skipCache = NEVER_CACHE_PATTERNS.some((re) => re.test(url.pathname));
  if (skipCache) {
    event.respondWith(fetch(request));
    return;
  }

  // Authorization headers do not partition Cache Storage. Keep all API and
  // private navigation/RSC responses network-only, including offline failures.
  const staticAsset = url.pathname.startsWith("/_next/static/") ||
    /^\/aminra-[a-z0-9-]+\.png$/.test(url.pathname) ||
    url.pathname === OFFLINE_URL;
  if (!staticAsset || request.headers.has("Authorization")) {
    event.respondWith(fetch(request));
    return;
  }
  event.respondWith(fetch(request).then((response) => {
    if (response.ok) {
      const clone = response.clone();
      event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(request, clone)));
    }
    return response;
  }).catch(() => caches.match(request).then(cached => cached || Response.error())));

});

// Web push: show notification when server pushes via VAPID
self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (e) {
    payload = { title: event.data ? event.data.text() : "AMINRA" };
  }
  const title = payload.title || "AMINRA";
  const options = {
    body: payload.message || "",
    icon: "/aminra-mark.png",
    badge: "/aminra-mark.png",
    data: {
      link: payload.link || "/",
      notification_id: payload.notification_id || null,
    },
    tag: payload.tag || payload.notification_id || undefined,
    requireInteraction: false,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Click on notification → open or focus the linked URL
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const link = (event.notification.data && event.notification.data.link) || "/";
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((wins) => {
        for (const w of wins) {
          if ("focus" in w) {
            w.navigate(link).catch(() => {});
            return w.focus();
          }
        }
        return self.clients.openWindow(link);
      }),
  );
});

// Listen for sync events (for queued offline checklist updates)
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-audit-data") {
    event.waitUntil(syncAuditData());
  }
});

async function syncAuditData() {
  // Read queued updates from IndexedDB and POST them
  try {
    const db = await openDB();
    const tx = db.transaction("sync-queue", "readonly");
    const store = tx.objectStore("sync-queue");
    const items = await getAllFromStore(store);

    for (const item of items) {
      try {
        await fetch(item.url, {
          method: item.method,
          headers: item.headers,
          body: item.body,
        });
        // Remove from queue on success
        const delTx = db.transaction("sync-queue", "readwrite");
        delTx.objectStore("sync-queue").delete(item.id);
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
    const req = indexedDB.open("aminra-offline", 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("sync-queue")) {
        db.createObjectStore("sync-queue", {
          keyPath: "id",
          autoIncrement: true,
        });
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
