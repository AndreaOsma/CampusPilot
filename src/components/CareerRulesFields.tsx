import type { CareerConfig, TermSystem } from "../api";
import { DEFAULT_CONFIG, letterPresets, TERM_SYSTEM } from "../lib/rules";
import { Field } from "../ui";
import { t } from "../i18n";

const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const SCALES: { max: number; pass: number; label: string }[] = [
  { max: 10, pass: 5, label: t("0 a 10 (aprobado 5)") },
  { max: 20, pass: 10, label: t("0 a 20 (aprobado 10)") },
  { max: 100, pass: 50, label: t("0 a 100 (aprobado 50)") },
  { max: 4, pass: 2, label: t("0 a 4 (GPA)") },
];

const rescale = (letters: CareerConfig["letters"], from: number, to: number) =>
  letters.map((l) => ({ ...l, min: Math.round((l.min / from) * to * 100) / 100, value: Math.round((l.value / from) * to * 100) / 100 }));

/** Reglas de la universidad: escala de notas, créditos, calendario y nombres de la evaluación. */
export function CareerRulesFields({ value, onChange }: { value: CareerConfig; onChange: (c: CareerConfig) => void }) {
  const cfg = { ...DEFAULT_CONFIG, ...value, labels: { ...DEFAULT_CONFIG.labels, ...(value.labels ?? {}) } };
  const preset = SCALES.find((s) => s.max === cfg.grade_max);
  const set = (patch: Partial<CareerConfig>) => onChange({ ...cfg, ...patch });
  const presets = letterPresets(cfg.grade_max);
  const letterKey = (l: CareerConfig["letters"]) => l.map((x) => `${x.label}:${x.min}`).join("|");
  const letterPreset = cfg.letters.length ? presets.find((p) => letterKey(p.letters) === letterKey(cfg.letters))?.id ?? "custom" : "";
  return (
    <fieldset className="fieldset">
      <legend>{t("Reglas de tu universidad")}</legend>
      <div className="form-grid">
        <Field label={t("Escala de notas")}>
          {(id) => (
            <select
              id={id}
              value={preset ? String(preset.max) : "custom"}
              onChange={(e) => {
                const s = SCALES.find((x) => String(x.max) === e.target.value);
                if (s) set({ grade_max: s.max, pass_mark: s.pass, letters: rescale(cfg.letters, cfg.grade_max, s.max) });
              }}
            >
              {SCALES.map((s) => (
                <option key={s.max} value={s.max}>
                  {s.label}
                </option>
              ))}
              {!preset && <option value="custom">0 a {cfg.grade_max} {t("(personalizada)")}</option>}
            </select>
          )}
        </Field>
        <Field label={t("Se aprueba con")}>
          {(id) => (
            <input id={id} type="number" min={0} max={cfg.grade_max} step={0.01} value={cfg.pass_mark}
              onChange={(e) => set({ pass_mark: Number(e.target.value) })} />
          )}
        </Field>
        <Field label={t("Notas con letras")} hint={t("Se ven junto a la nota y puedes apuntarla con la letra")}>
          {(id) => (
            <select id={id} value={letterPreset} onChange={(e) => set({ letters: presets.find((p) => p.id === e.target.value)?.letters ?? [] })}>
              <option value="">{t("Solo números")}</option>
              {presets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
              {letterPreset === "custom" && <option value="custom">{cfg.letters.map((x) => x.label).join(", ")}</option>}
            </select>
          )}
        </Field>
        <Field label={t("Nombre de los créditos")} hint={t("ECTS, créditos, credits…")}>
          {(id) => <input id={id} required maxLength={20} value={cfg.credit_label} onChange={(e) => set({ credit_label: e.target.value })} />}
        </Field>
        <Field label={t("Calendario")}>
          {(id) => (
            <select id={id} value={cfg.term_system} onChange={(e) => set({ term_system: e.target.value as TermSystem })}>
              {Object.entries(TERM_SYSTEM).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("El curso empieza en")}>
          {(id) => (
            <select id={id} value={cfg.year_start_month} onChange={(e) => set({ year_start_month: Number(e.target.value) })}>
              {MONTHS.map((m, i) => (
                <option key={m} value={i + 1}>
                  {m}
                </option>
              ))}
            </select>
          )}
        </Field>
        <div className="detail-only field--wide form-grid">
        <Field label={t("Escala máxima personalizada")} hint={t("Si no es ninguna de las de arriba")}>
          {(id) => (
            <input id={id} type="number" min={1} max={100} step={1} value={cfg.grade_max}
              onChange={(e) => {
                const max = Math.max(1, Math.min(100, Number(e.target.value) || 10));
                set({ grade_max: max, pass_mark: Math.min(cfg.pass_mark, max), letters: rescale(cfg.letters, cfg.grade_max, max) });
              }} />
          )}
        </Field>
        <Field label={t("Cómo llamáis a la evaluación continua")} hint={t("Vacío = «EC»")}>
          {(id) => <input id={id} maxLength={40} value={cfg.labels.ec} onChange={(e) => set({ labels: { ...cfg.labels, ec: e.target.value } })} />}
        </Field>
        <Field label={t("…y a la prueba final")} hint={t("Vacío = «PF»")}>
          {(id) => <input id={id} maxLength={40} value={cfg.labels.pf} onChange={(e) => set({ labels: { ...cfg.labels, pf: e.target.value } })} />}
        </Field>
        </div>
      </div>
    </fieldset>
  );
}
