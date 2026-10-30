/** Capacitor (Android/iOS): la web empaquetada y el backend de Python dentro del móvil. */
import type { CapacitorConfig } from "@capacitor/cli";

const appId = process.env.CAP_APP_ID || "com.andreaosma.campuspilot";
const appName = process.env.CAP_APP_NAME || "Campus Pilot";
const remoteUrl = process.env.CAP_REMOTE_URL || "";
// La web va en https://localhost (esquema por defecto de Capacitor) y la API en
// http://127.0.0.1: es contenido mixto, bloqueado si no se permite.
const apiIsCleartext = (process.env.VITE_API_BASE_URL || "").startsWith("http://");
const backgroundColor = "#f1f0fb";

const config: CapacitorConfig = {
  appId,
  appName,
  webDir: "dist",
  backgroundColor,
  android: {
    allowMixedContent: remoteUrl.startsWith("http://") || apiIsCleartext,
    backgroundColor,
  },
  server: {
    ...(remoteUrl ? { url: remoteUrl, cleartext: remoteUrl.startsWith("http://") } : {}),
    // «Conectar con OpenRouter»: el login se hace dentro de la app y OpenRouter vuelve a
    // https://localhost/ajustes con el código. (El inicio de sesión con Google no funciona
    // dentro de una app; con correo o GitHub, sí.)
    allowNavigation: ["openrouter.ai", "*.openrouter.ai", "github.com", "*.github.com"],
  },
};

export default config;
