/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
/** Tipos del juego (los mismos que devuelve `GET .../game` en cada app). */
export type Quest = { id: string; title: string; progress: number; target: number; gems: number; done: boolean; claimed: boolean };
export type WeekDay = { date: string; xp: number; frozen: boolean; active?: boolean; future: boolean };
export type GameState = {
  gems: number;
  streak_freezes: number;
  streak: number;
  today_xp: number;
  goal: number;
  week: WeekDay[];
  quests: Quest[];
  prices: { freeze: number };
  max_freezes: number;
};

/** Traductor: cada app pasa el suyo (Campus Pilot, `t`); sin él, español con variables. */
export type Tx = (es: string, vars?: Record<string, string | number>) => string;
export const spanish: Tx = (es, vars) => (vars ? Object.entries(vars).reduce((s, [k, v]) => s.split(`{${k}}`).join(String(v)), es) : es);

export const WEEKDAYS_ES = ["L", "M", "X", "J", "V", "S", "D"];

export function dayIsOn(d: WeekDay): boolean {
  return d.xp > 0 || Boolean(d.active);
}

export function fmtClock(sec: number): string {
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

export const PRAISE = ["¡Genial!", "¡Muy bien!", "¡Perfecto!", "¡Eso es!", "¡Bien hecho!", "¡Exacto!"];

export type MascotMood = "happy" | "cheer" | "think" | "sad";
