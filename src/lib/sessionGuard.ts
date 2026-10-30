/**
 * Con Authelia delante, una sesión caducada no llega como 401: el servidor redirige al login, que
 * está en otro dominio. Para `fetch` (la API, los trozos de JS que se cargan al navegar) eso es un
 * error de red, y la app se quedaba en blanco en vez de llevarte a iniciar sesión.
 *
 * `/health` pasa por Authelia pero no por el service worker: si al pedirla sin seguir redirecciones
 * vuelve una redirección, la sesión ha caducado y se recarga la página entera, que sí pasa por el
 * login. Una vez por minuto como mucho, para no entrar en bucle si algo raro devuelve redirecciones.
 */
const KEY = "campus-session-reload";

export async function sessionExpired(): Promise<boolean> {
  try {
    const res = await fetch("/health", { redirect: "manual", cache: "no-store", credentials: "same-origin" });
    return res.type === "opaqueredirect" || (res.status >= 300 && res.status < 400);
  } catch {
    return false; // sin red de verdad: lo que haya en caché sigue sirviendo
  }
}

export async function reloadIfSessionExpired(): Promise<boolean> {
  if (!(await sessionExpired())) return false;
  let last = 0;
  try {
    last = Number(sessionStorage.getItem(KEY) || 0);
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    /* sin sessionStorage: se recarga igual */
  }
  if (Date.now() - last < 60_000) return false;
  window.location.reload();
  return true;
}
