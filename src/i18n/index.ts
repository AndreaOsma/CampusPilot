/**
 * Traducciones: español (origen) e inglés.
 *
 * Las claves son el propio texto en español (como gettext): lo que aún no está traducido sale
 * en español en vez de romperse, y el código se sigue leyendo igual. `{name}` = variable.
 * El idioma vive en Ajustes (settings.language); `setLocale` lo fija antes de pintar.
 */
import en from "./en.json";

export type Locale = "es" | "en";
export const LOCALES: Record<Locale, string> = { es: "Español", en: "English" };

const CATALOGS: Record<Locale, Record<string, string>> = { es: {}, en: en as Record<string, string> };
const INTL: Record<Locale, string> = { es: "es-ES", en: "en-GB" };

let current: Locale = initial();

function initial(): Locale {
  try {
    const saved = localStorage.getItem("campus-locale");
    if (saved === "es" || saved === "en") return saved;
  } catch {
    /* sin almacenamiento */
  }
  // Sin preferencia guardada: el idioma del navegador (español si no se sabe, p. ej. en Node).
  const lang = typeof navigator !== "undefined" ? navigator.language?.toLowerCase() ?? "" : "";
  return !lang || lang.startsWith("es") ? "es" : "en";
}

export function setLocale(l: Locale) {
  current = l;
  try {
    localStorage.setItem("campus-locale", l);
  } catch {
    /* sin almacenamiento */
  }
  if (typeof document !== "undefined") document.documentElement.lang = l;
}

export function locale(): Locale {
  return current;
}

/** Etiqueta BCP 47 para Intl (fechas, números, moneda). */
export function intlTag(): string {
  return INTL[current];
}

export function t(es: string, vars?: Record<string, string | number>): string {
  let out = CATALOGS[current][es] ?? es;
  if (vars) for (const [k, v] of Object.entries(vars)) out = out.split(`{${k}}`).join(String(v));
  return out;
}

/** Mapa de etiquetas que se traduce al leerlo (sirve con Object.entries y con m[clave]). */
export function translated<K extends string>(map: Record<K, string>): Record<K, string> {
  return new Proxy(map, {
    get(target, prop, receiver) {
      const v = Reflect.get(target, prop, receiver);
      return typeof v === "string" ? t(v) : v;
    },
  });
}

/** Lista que se traduce al leerla (días de la semana…). */
export function translatedList(list: string[]): string[] {
  return new Proxy(list, {
    get(target, prop, receiver) {
      const v = Reflect.get(target, prop, receiver);
      return typeof prop === "string" && /^\d+$/.test(prop) && typeof v === "string" ? t(v) : v;
    },
  });
}

if (typeof document !== "undefined") document.documentElement.lang = current;
