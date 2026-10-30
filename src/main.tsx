import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { StoreProvider } from "./store";
import { reloadIfSessionExpired } from "./lib/sessionGuard";
import "./vendor/design-system/tokens.css";
import "./vendor/design-system/base.css";
import "./styles/base.css";
// Modo dev de ágora (🛠️): elegir un elemento y pedir el cambio a la fábrica. Solo se activa dentro de ágora.
import "./vendor/dev-overlay/overlay";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <StoreProvider>
      <App />
    </StoreProvider>
  </React.StrictMode>
);

// Un trozo de JS que no carga al navegar suele ser la sesión de Authelia caducada (redirige al
// login): en ese caso, a iniciar sesión en vez de quedarse en blanco.
window.addEventListener("vite:preloadError", () => {
  void reloadIfSessionExpired();
});

// PWA: solo en producción (en dev, el SW cachearía el servidor de Vite).
// En la app nativa (Capacitor) no: la web ya va dentro de la app y el SW guardaría versiones viejas.
const isNativeApp = Boolean((window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } }).Capacitor?.isNativePlatform?.());
if ("serviceWorker" in navigator && import.meta.env.PROD && !isNativeApp) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then(() => navigator.serviceWorker.ready)
      .then((reg) => reg.active?.postMessage({ type: "refresh-shell" }))
      .catch(() => undefined);
  });
}
