// Hand-written service worker (no Workbox/next-pwa -- that's a webpack
// plugin and this project builds with Turbopack, which doesn't run webpack
// plugins at all). Scope is deliberately small: cache the app shell so the
// PWA is installable and the icon/manifest load offline, but never cache
// API responses -- this is a financial app, so a stale "amount owed" served
// from cache while offline would be actively misleading.
const CACHE_NAME = "sme-gpt-shell-v1";
const SHELL_ASSETS = [
  "/manifest.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Never intercept API/backend calls or Next.js data requests -- only the
  // static app shell is cached.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/_next/data/")) {
    return;
  }

  if (!SHELL_ASSETS.includes(url.pathname)) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      });
    })
  );
});
