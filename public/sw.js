/* Service worker de Campus Pilot: la app abre y enseña los últimos datos sin cobertura.
 *
 * - Navegación: red primero; sin red, el index.html cacheado (la SPA enruta sola).
 * - /assets/*: caché primero (nombres con hash, inmutables).
 * - GET /api/*: red primero con copia en caché como respaldo (lectura sin cobertura).
 *   Las escrituras nunca pasan por aquí.
 * - Nunca se cachea una redirección (p. ej. al login de Authelia con la sesión caducada).
 */
const VERSION = "campus-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon.svg"];
// Descargas que deben venir siempre frescas del servidor.
const NO_CACHE = ["/api/backup", "/api/calendar.ics", "/api/packs/", "/ical/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(VERSION)
      .then((cache) => Promise.all(SHELL.map((url) => fetch(url, { credentials: "same-origin" }).then((res) => cacheable(res) && cache.put(url, res)))))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function cacheable(res) {
  return res && res.ok && res.type === "basic" && !res.redirected;
}

async function networkFirst(request, fallbackUrl) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(request);
    if (cacheable(res)) cache.put(fallbackUrl || request, res.clone());
    return res;
  } catch (err) {
    const cached = (await cache.match(request)) || (fallbackUrl && (await cache.match(fallbackUrl)));
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(VERSION);
  const cached = await cache.match(request);
  if (cached) return cached;
  const res = await fetch(request);
  if (cacheable(res)) cache.put(request, res.clone());
  return res;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // teselas OSM, etc.
  if (NO_CACHE.some((p) => url.pathname.startsWith(p))) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, "/"));
  } else if (url.pathname.startsWith("/assets/")) {
    event.respondWith(cacheFirst(request));
  } else if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request));
  }
});
