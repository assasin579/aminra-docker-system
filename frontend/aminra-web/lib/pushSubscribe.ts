/**
 * Web Push subscription helpers.
 *
 * Flow:
 *   1. Fetch VAPID public key from /api/api/notifications/push-public-key
 *   2. Ask user for Notification permission
 *   3. Subscribe via service worker registration
 *   4. POST endpoint+keys to /api/api/notifications/push-subscriptions
 *
 * The browser may rotate the endpoint URL — re-running subscribe is safe
 * (server upserts on `endpoint`).
 */

function urlBase64ToUint8Array(b64: string): Uint8Array {
  const padding = "=".repeat((4 - (b64.length % 4)) % 4);
  const base64 = (b64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function arrayBufferToBase64Url(buf: ArrayBuffer | null): string {
  if (!buf) return "";
  const bytes = new Uint8Array(buf);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function isPushSupported(): Promise<boolean> {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export async function getCurrentSubscription(): Promise<PushSubscription | null> {
  if (!(await isPushSupported())) return null;
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

export async function subscribePush(
  token: string,
): Promise<{ ok: true } | { ok: false; reason: string }> {
  if (!(await isPushSupported())) return { ok: false, reason: "unsupported" };

  const perm = await Notification.requestPermission();
  if (perm !== "granted") return { ok: false, reason: "permission-denied" };

  const keyRes = await fetch("/api/api/notifications/push-public-key");
  if (!keyRes.ok) return { ok: false, reason: "no-vapid-key" };
  const { key } = await keyRes.json();
  if (!key) return { ok: false, reason: "vapid-not-configured" };

  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    const keyBytes = urlBase64ToUint8Array(key);
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes.buffer.slice(
        keyBytes.byteOffset,
        keyBytes.byteOffset + keyBytes.byteLength,
      ) as ArrayBuffer,
    });
  }

  const json = sub.toJSON();
  const res = await fetch("/api/api/notifications/push-subscriptions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      endpoint: json.endpoint!,
      p256dh: json.keys?.p256dh ?? arrayBufferToBase64Url(sub.getKey("p256dh")),
      auth: json.keys?.auth ?? arrayBufferToBase64Url(sub.getKey("auth")),
      user_agent: navigator.userAgent,
    }),
  });
  if (!res.ok) return { ok: false, reason: `http-${res.status}` };
  return { ok: true };
}

export async function unsubscribePush(token: string): Promise<boolean> {
  const sub = await getCurrentSubscription();
  if (!sub) return true;
  const endpoint = sub.endpoint;
  await sub.unsubscribe();
  await fetch(
    `/api/api/notifications/push-subscriptions?endpoint=${encodeURIComponent(endpoint)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  return true;
}
