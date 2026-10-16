import type React from "react";
import { intlTag, t, translated, translatedList } from "../i18n";
import type {
  ActivityKind,
  AiPolicy,
  EventKind,
  ExpenseCategory,
  GrantStatus,
  PathKind,
  PathStatus,
  ProcedureCategory,
  ProcedureStatus,
  SubjectKind,
  SubjectStatus,
} from "../api";

export const SUBJECT_KIND: Record<SubjectKind, string> = translated({
  basica: "Formación básica",
  obligatoria: "Obligatoria",
  optativa: "Optativa",
  mencion: "De mención",
  practicas: "Prácticas",
  tfg: "Trabajo final",
  otra: "Otra",
});
export const SUBJECT_STATUS: Record<SubjectStatus, string> = translated({
  pending: "Pendiente",
  enrolled: "Matriculada",
  passed: "Aprobada",
  failed: "Suspendida",
  convalidated: "Convalidada",
  dropped: "Abandonada",
});
export const AI_POLICY: Record<AiPolicy, string> = translated({
  unknown: "IA: sin comprobar",
  allowed: "IA permitida",
  limited: "IA limitada",
  forbidden: "IA prohibida",
});
export const ACTIVITY_KIND: Record<ActivityKind, string> = translated({
  pec: "Entrega",
  pr: "Práctica",
  quiz: "Cuestionario",
  video: "Vídeo",
  exam: "Examen",
  lab: "Laboratorio",
  project: "Proyecto",
  other: "Otra",
});
export const EVENT_KIND: Record<EventKind, string> = translated({
  session: "Sesión síncrona",
  class: "Clase",
  exam: "Examen",
  admin: "Gestión",
  personal: "Personal",
  other: "Otro",
});
export const EXPENSE_CATEGORY: Record<ExpenseCategory, string> = translated({
  tuition: "Matrícula",
  materials: "Material",
  books: "Libros",
  exam: "Exámenes",
  transport: "Transporte",
  software: "Software",
  other: "Otros",
});
export const GRANT_STATUS: Record<GrantStatus, string> = translated({
  idea: "Por mirar",
  preparing: "Preparando",
  applied: "Solicitada",
  granted: "Concedida",
  rejected: "Denegada",
  paid: "Cobrada",
});
export const PROCEDURE_CATEGORY: Record<ProcedureCategory, string> = translated({
  enrollment: "Matrícula",
  recognition: "Reconocimiento / convalidación",
  scholarship: "Becas",
  internship: "Prácticas",
  tfg: "TFG",
  admin: "Gestión",
  other: "Otro",
});
export const PROCEDURE_STATUS: Record<ProcedureStatus, string> = translated({
  todo: "Pendiente",
  doing: "En curso",
  waiting: "Esperando respuesta",
  done: "Hecho",
});
export const PATH_KIND: Record<PathKind, string> = translated({
  course: "Curso",
  certification: "Certificación",
  project: "Proyecto",
  internship: "Prácticas",
  job: "Trabajo",
  language: "Idioma",
  volunteering: "Voluntariado",
  award: "Premio",
  other: "Otro",
});
export const PATH_STATUS: Record<PathStatus, string> = translated({
  idea: "Idea",
  planned: "Previsto",
  in_progress: "En marcha",
  done: "Hecho",
  dropped: "Descartado",
});
export const WEEKDAYS = translatedList(["L", "M", "X", "J", "V", "S", "D"]);
export const WEEKDAYS_LONG = translatedList(["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]);

export function parseDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function isoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export const todayIso = () => isoDate(new Date());

export function addDays(iso: string, days: number): string {
  const d = parseDate(iso);
  d.setDate(d.getDate() + days);
  return isoDate(d);
}

export function weekStart(iso: string): string {
  const d = parseDate(iso);
  return addDays(iso, -((d.getDay() + 6) % 7));
}

export function daysBetween(fromIso: string, toIso: string): number {
  return Math.round((parseDate(toIso).getTime() - parseDate(fromIso).getTime()) / 86_400_000);
}

// Formateadores por idioma, creados una vez por locale.
const fmtCache = new Map<string, Intl.DateTimeFormat>();
function dtf(opts: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = intlTag() + JSON.stringify(opts);
  let f = fmtCache.get(key);
  if (!f) fmtCache.set(key, (f = new Intl.DateTimeFormat(intlTag(), opts)));
  return f;
}

export function fmtDate(iso: string | null | undefined, withYear = false): string {
  if (!iso) return "—";
  return dtf(withYear ? { day: "numeric", month: "short", year: "numeric" } : { day: "numeric", month: "short" }).format(parseDate(iso));
}

export function fmtWeekday(iso: string): string {
  return dtf({ weekday: "short", day: "numeric", month: "short" }).format(parseDate(iso));
}

export function relDays(iso: string, today = todayIso()): string {
  const n = daysBetween(today, iso);
  if (n === 0) return t("hoy");
  if (n === 1) return t("mañana");
  if (n === -1) return t("ayer");
  if (n < 0) return t("hace {n} días", { n: -n });
  return t("en {n} días", { n });
}

export function fmtGrade(g: number | null | undefined): string {
  if (g === null || g === undefined) return "—";
  return g.toLocaleString(intlTag(), { minimumFractionDigits: 1, maximumFractionDigits: 2 });
}

export function fmtMoney(n: number, currency = "EUR"): string {
  return n.toLocaleString(intlTag(), { style: "currency", currency });
}

export function fmtMinutes(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (!h) return `${m} min`;
  return m ? `${h} h ${m} min` : `${h} h`;
}

/** Enlace obsidian:// a una nota/carpeta de la bóveda (ruta relativa a la raíz). */
export function obsidianUrl(vault: string, file: string): string {
  return `obsidian://open?vault=${encodeURIComponent(vault)}&file=${encodeURIComponent(file)}`;
}

export function numOrNull(v: string): number | null {
  if (v.trim() === "") return null;
  const n = Number(v.replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

/** Tono estable por asignatura (ángulo áureo: ids consecutivos quedan bien separados). */
export function subjectHue(id: number | null | undefined): number {
  if (!id) return 250;
  return Math.round((id * 137.508) % 360);
}

export function subjectStyle(id: number | null | undefined): React.CSSProperties {
  return { ["--subj-h" as string]: String(subjectHue(id)) } as React.CSSProperties;
}

/** Urgencia de una fecha: crit (vencida, hoy o mañana), warn (≤ 3 días), normal. */
export function urgency(iso: string, today = todayIso()): "crit" | "warn" | "normal" {
  const n = daysBetween(today, iso);
  if (n <= 1) return "crit";
  if (n <= 3) return "warn";
  return "normal";
}

export const weekdayShort = (iso: string) => dtf({ weekday: "short" }).format(parseDate(iso)).replace(".", "");
export const monthShort = (iso: string) => dtf({ month: "short" }).format(parseDate(iso)).replace(".", "");
