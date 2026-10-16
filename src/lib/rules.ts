/**
 * Reglas de cada universidad: escala de notas, aprobado, créditos, calendario y nombres.
 * Vienen de `career.config` (las trae el módulo de estudios o las pones tú); sin ellas, lo de
 * siempre en España: 0–10, aprobado 5, ECTS y dos semestres desde septiembre.
 */
import type { ActivityKind, Career, CareerConfig, GradeLetter, Offered, SubjectKind, TermSystem } from "../api";
import { ACTIVITY_KIND, SUBJECT_KIND } from "./format";
import { locale, t } from "../i18n";

export const DEFAULT_CONFIG: CareerConfig = {
  grade_max: 10,
  pass_mark: 5,
  decimals: 2,
  credit_label: "ECTS",
  term_system: "semesters",
  year_start_month: 9,
  labels: { subject_kinds: {}, activity_kinds: {}, ec: "", pf: "" },
  letters: [],
};

/** Letra de una nota según la escala de la carrera (null si no usa letras). */
export function letterOf(grade: number | null | undefined, rules: CareerConfig): string | null {
  if (grade === null || grade === undefined || !rules.letters?.length) return null;
  return rules.letters.find((l) => grade >= l.min)?.label ?? rules.letters[rules.letters.length - 1].label;
}

/** Escalas con letras habituales, ajustadas a la nota máxima de la carrera (en fracciones). */
export function letterPresets(max: number): { id: string; label: string; letters: GradeLetter[] }[] {
  const at = (f: number) => Math.round(f * max * 100) / 100;
  const mk = (rows: [string, number, number][]) => rows.map(([label, min, value]) => ({ label, min: at(min), value: at(value) }));
  return [
    { id: "ec", label: t("A, B, C+, C-, D (informe de evaluación continua)"), letters: mk([["A", 0.9, 0.95], ["B", 0.7, 0.8], ["C+", 0.5, 0.6], ["C-", 0.3, 0.4], ["D", 0, 0.15]]) },
    { id: "af", label: t("A, B, C, D, F"), letters: mk([["A", 0.9, 0.95], ["B", 0.8, 0.85], ["C", 0.7, 0.75], ["D", 0.6, 0.65], ["F", 0, 0.3]]) },
    { id: "es", label: t("Sobresaliente, Notable, Aprobado, Suspenso"), letters: mk([[t("SB"), 0.9, 0.95], [t("NT"), 0.7, 0.8], [t("AP"), 0.5, 0.6], [t("SS"), 0, 0.25]]) },
  ];
}

export function rulesOf(career: Pick<Career, "config"> | null | undefined): CareerConfig {
  const c = career?.config;
  if (!c) return DEFAULT_CONFIG;
  return { ...DEFAULT_CONFIG, ...c, labels: { ...DEFAULT_CONFIG.labels, ...(c.labels ?? {}) } };
}

export const TERM_SYSTEM: Record<TermSystem, string> = {
  semesters: t("Semestres (2 al año)"),
  trimesters: t("Trimestres (3 al año)"),
  quarters: t("Cuatro periodos al año"),
  annual: t("Curso anual"),
};

/** Letra del periodo, cuántos hay y en qué mes (desde el inicio de curso) empieza cada uno. */
const PERIODS: Record<TermSystem, { code: string; starts: number[]; name: [string, string] }> = {
  // Semestres: el 2.º empieza en el 6.º mes (sep→feb), como en casi todas las universidades.
  semesters: { code: "S", starts: [0, 5], name: ["semestre", "sem."] },
  trimesters: { code: "T", starts: [0, 4, 7], name: ["trimestre", "trim."] },
  quarters: { code: "Q", starts: [0, 3, 6, 9], name: ["periodo", "per."] },
  annual: { code: "A", starts: [0], name: ["curso", "curso"] },
};

function systemOfCode(code: string): TermSystem {
  return (Object.keys(PERIODS) as TermSystem[]).find((k) => PERIODS[k].code === code) ?? "semesters";
}

/** Periodo personal: "2026S1" = curso que empieza en 2026, periodo 1. "2026A" = curso anual. */
export type PlanTerm = string;

function parse(t: PlanTerm): { y: number; code: string; i: number } {
  const y = Number(t.slice(0, 4));
  const code = t.slice(4, 5);
  const i = code === "A" ? 1 : Number(t.slice(5)) || 1;
  return { y, code, i };
}

function make(y: number, code: string, i: number): PlanTerm {
  return code === "A" ? `${y}A` : `${y}${code}${i}`;
}

export function termOf(iso: string, system: TermSystem = "semesters", startMonth = 9): PlanTerm {
  const [y, m] = iso.split("-").map(Number);
  const year = m >= startMonth ? y : y - 1;
  const offset = (m - startMonth + 12) % 12;
  const p = PERIODS[system];
  let i = 1;
  p.starts.forEach((s, idx) => {
    if (offset >= s) i = idx + 1;
  });
  return make(year, p.code, i);
}

export function nextTerm(t: PlanTerm, n = 1): PlanTerm {
  let { y, i } = parse(t);
  const { code } = parse(t);
  const count = PERIODS[systemOfCode(code)].starts.length;
  for (let k = 0; k < Math.abs(n); k++) {
    if (n > 0) [y, i] = i < count ? [y, i + 1] : [y + 1, 1];
    else [y, i] = i > 1 ? [y, i - 1] : [y - 1, count];
  }
  return make(y, code, i);
}

/** 1.er/2.º… o 1st/2nd… según el idioma. */
function ordinal(i: number): string {
  if (locale() === "en") return `${i}${i === 1 ? "st" : i === 2 ? "nd" : i === 3 ? "rd" : "th"}`;
  return i === 1 ? "1.er" : i === 3 ? "3.er" : `${i}.º`;
}

function periodName(code: string, short: boolean): string {
  const [long, abbr] = PERIODS[systemOfCode(code)].name;
  return t(short ? abbr : long);
}

export function termLabel(term: PlanTerm, short = false): string {
  const { y, code, i } = parse(term);
  const years = `${y}/${String(y + 1).slice(2)}`;
  if (code === "A") return years;
  return `${years} · ${ordinal(i)} ${periodName(code, short)}`;
}

/** Periodos para un selector: desde el curso pasado hasta dentro de unos 5 años (y el elegido si cae fuera). */
export function planTermOptions(
  current: PlanTerm | null = null,
  today = new Date().toISOString().slice(0, 10),
  system: TermSystem = "semesters",
  startMonth = 9
): PlanTerm[] {
  const count = PERIODS[system].starts.length;
  const start = nextTerm(termOf(today, system, startMonth), -count);
  const out = Array.from({ length: count * 6 }, (_, k) => nextTerm(start, k));
  if (current && !out.includes(current)) out.push(current);
  return out.sort();
}

/** Cuándo se imparte la asignatura, según el calendario de la carrera. */
export function offeredOptions(system: TermSystem): Record<string, string> {
  const p = PERIODS[system];
  const out: Record<string, string> = { both: system === "annual" ? t("Todo el curso") : t("En cualquier periodo") };
  if (system === "annual") return out;
  p.starts.forEach((_, idx) => {
    out[`${p.code.toLowerCase()}${idx + 1}`] = t("Solo en el {0} {1}", { 0: ordinal(idx + 1), 1: periodName(p.code, false) });
  });
  return out;
}

export function offeredShort(offered: Offered | null): string {
  if (!offered || offered === "both") return "";
  return t("solo {0} {1}", { 0: ordinal(Number(offered.slice(1))), 1: periodName(offered[0].toUpperCase(), true) });
}

/** «Solo se imparte en el 2.º semestre». */
export function offeredWarning(offered: Offered | null): string {
  if (!offered || offered === "both") return "";
  return t("Solo se imparte en el {0} {1}", { 0: ordinal(Number(offered.slice(1))), 1: periodName(offered[0].toUpperCase(), false) });
}

/** ¿Choca el periodo elegido con cuándo se imparte? Solo si son del mismo tipo de periodo. */
export function termClash(offered: Offered | null, t: PlanTerm | null): boolean {
  if (!t || !offered || offered === "both") return false;
  const { code, i } = parse(t);
  if (offered[0].toUpperCase() !== code) return false;
  return Number(offered.slice(1)) !== i;
}

export function subjectKindLabel(cfg: CareerConfig, kind: SubjectKind): string {
  return cfg.labels.subject_kinds?.[kind] || SUBJECT_KIND[kind];
}

export function activityKindLabel(cfg: CareerConfig, kind: ActivityKind): string {
  return cfg.labels.activity_kinds?.[kind] || ACTIVITY_KIND[kind];
}

export function ecLabel(cfg: CareerConfig, long = false): string {
  return cfg.labels.ec || (long ? t("Evaluación continua") : "EC");
}

export function pfLabel(cfg: CareerConfig, long = false): string {
  return cfg.labels.pf || (long ? t("Prueba final") : "PF");
}
