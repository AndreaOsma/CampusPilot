import { useState } from "react";
import { api, type AiPolicy, type Career, type Link, type Subject, type SubjectIn, type SubjectKind, type SubjectStatus } from "../api";
import { AI_POLICY, numOrNull, obsidianUrl, SUBJECT_KIND, SUBJECT_STATUS, todayIso } from "../lib/format";
import { ecLabel, offeredOptions, pfLabel, planTermOptions, rulesOf, subjectKindLabel, termLabel } from "../lib/rules";
import { useStore } from "../store";
import { Field, FormStatus, useSubmit } from "../ui";
import { t } from "../i18n";

export function emptySubject(career: Career): SubjectIn {
  const r = rulesOf(career);
  const k = r.grade_max / 10;
  return {
    career_id: career.id,
    term_id: null,
    code: "",
    name: "",
    ects: 6,
    kind: "obligatoria",
    plan_semester: null,
    offered: null,
    planned_term: null,
    track: null,
    status: "pending",
    final_grade: null,
    attempt: 1,
    price_per_credit: null,
    weekly_hours: null,
    ai_policy: "unknown",
    ai_policy_note: "",
    eval_model: "weighted",
    eval_config: { ec_pass: r.pass_mark, pf_min: Math.round(4 * k * 100) / 100, no_show_grade: Math.round(3 * k * 100) / 100 },
    notes: "",
    links: [],
  };
}

export function SubjectForm({
  initial,
  subjectId,
  career,
  onSaved,
}: {
  initial: SubjectIn;
  subjectId?: number;
  career: Career;
  onSaved: (s: Subject) => void;
}) {
  const { terms, settings, reload } = useStore();
  const [form, setForm] = useState<SubjectIn>(initial);
  const [notesPath, setNotesPath] = useState("");
  const { state, run } = useSubmit();
  const set = <K extends keyof SubjectIn>(key: K, value: SubjectIn[K]) => setForm((f) => ({ ...f, [key]: value }));
  const careerTerms = terms.filter((t) => t.career_id === career.id);
  const rules = rulesOf(career);
  const top = rules.grade_max;

  const setLink = (i: number, patch: Partial<Link>) => set("links", form.links.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...form, links: form.links.filter((l) => l.label.trim() && l.url.trim()) };
    const saved = await run(() => (subjectId ? api.subjects.update(subjectId, payload) : api.subjects.create(payload)));
    if (saved) {
      await reload();
      onSaved(saved);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="form-grid">
        <Field label={t("Nombre")} wide>
          {(id) => <input id={id} required maxLength={200} value={form.name} onChange={(e) => set("name", e.target.value)} />}
        </Field>
        <Field label={t("Código")}>
          {(id) => <input id={id} maxLength={32} value={form.code} onChange={(e) => set("code", e.target.value)} />}
        </Field>
        <Field label={rules.credit_label}>
          {(id) => (
            <input id={id} type="number" min={0.5} max={60} step={0.5} required value={form.ects} onChange={(e) => set("ects", Number(e.target.value))} />
          )}
        </Field>
        <Field label={t("Tipo")}>
          {(id) => (
            <select id={id} value={form.kind} onChange={(e) => set("kind", e.target.value as SubjectKind)}>
              {Object.keys(SUBJECT_KIND).map((k) => (
                <option key={k} value={k}>
                  {subjectKindLabel(rules, k as SubjectKind)}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("Estado")}>
          {(id) => (
            <select id={id} value={form.status} onChange={(e) => set("status", e.target.value as SubjectStatus)}>
              {Object.entries(SUBJECT_STATUS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("Periodo en que la cursas")}>
          {(id) => (
            <select id={id} value={form.term_id ?? ""} onChange={(e) => set("term_id", e.target.value ? Number(e.target.value) : null)}>
              <option value="">—</option>
              {careerTerms.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("Mi plan")} hint={t("Cuándo la piensas cursar tú")}>
          {(id) => (
            <select id={id} value={form.planned_term ?? ""} onChange={(e) => set("planned_term", e.target.value || null)}>
              <option value="">{t("Sin planificar")}</option>
              {planTermOptions(form.planned_term, todayIso(), rules.term_system, rules.year_start_month).map((t) => (
                <option key={t} value={t}>
                  {termLabel(t)}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("Periodo recomendado")} hint={t("El que marca el plan de estudios (1, 2, 3…)")}>
          {(id) => (
            <input id={id} type="number" min={1} max={20} value={form.plan_semester ?? ""} onChange={(e) => set("plan_semester", numOrNull(e.target.value))} />
          )}
        </Field>
        <Field label={t("Se imparte")}>
          {(id) => (
            <select id={id} value={form.offered ?? ""} onChange={(e) => set("offered", (e.target.value || null) as SubjectIn["offered"])}>
              <option value="">—</option>
              {Object.entries(offeredOptions(rules.term_system)).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          )}
        </Field>
        {career.tracks.length > 0 && (
          <Field label={t("Mención")}>
            {(id) => (
              <select id={id} value={form.track ?? ""} onChange={(e) => set("track", e.target.value || null)}>
                <option value="">{t("— (todas)")}</option>
                {career.tracks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
        <Field label={t("Nota oficial")} hint={t("La del acta o la convalidación; manda sobre la calculada")}>
          {(id) => (
            <input id={id} type="number" min={0} max={top} step={0.01} value={form.final_grade ?? ""} onChange={(e) => set("final_grade", numOrNull(e.target.value))} />
          )}
        </Field>
        <Field label={t("Matrícula nº")} hint={t("1 = primera vez")}>
          {(id) => <input id={id} type="number" min={1} max={10} value={form.attempt} onChange={(e) => set("attempt", Number(e.target.value) || 1)} />}
        </Field>
        <Field label={t("Horas/semana previstas")}>
          {(id) => (
            <input id={id} type="number" min={0} max={80} step={0.5} value={form.weekly_hours ?? ""} onChange={(e) => set("weekly_hours", numOrNull(e.target.value))} />
          )}
        </Field>
        <Field label={t("Precio por crédito")} hint={t("Vacío = el de Ajustes")}>
          {(id) => (
            <input id={id} type="number" min={0} step={0.01} value={form.price_per_credit ?? ""} onChange={(e) => set("price_per_credit", numOrNull(e.target.value))} />
          )}
        </Field>
      </div>

      <fieldset className="fieldset">
        <legend>{t("IA generativa en las actividades evaluables")}</legend>
        <div className="form-grid">
          <Field label={t("Política")}>
            {(id) => (
              <select id={id} value={form.ai_policy} onChange={(e) => set("ai_policy", e.target.value as AiPolicy)}>
                {Object.entries(AI_POLICY).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={t("Fuente / matices")} wide hint={t("Dónde lo dice (plan docente, enunciado…) y qué pasa si no se cumple")}>
            {(id) => <textarea id={id} rows={3} maxLength={2000} value={form.ai_policy_note} onChange={(e) => set("ai_policy_note", e.target.value)} />}
          </Field>
        </div>
      </fieldset>

      <fieldset className="fieldset">
        <legend>{t("Evaluación")}</legend>
        <div className="form-grid">
          <Field label={t("Modelo")}>
            {(id) => (
              <select id={id} value={form.eval_model} onChange={(e) => set("eval_model", e.target.value as SubjectIn["eval_model"])}>
                <option value="weighted">{t("Suma ponderada de grupos (con mínimos)")}</option>
                <option value="ec_pf">{ecLabel(rules, true)} + {pfLabel(rules, true).toLowerCase()}</option>
              </select>
            )}
          </Field>
          {form.eval_model === "ec_pf" && (
            <>
              <Field label={t("Aprobar la {0} con", { 0: ecLabel(rules) })}>
                {(id) => (
                  <input id={id} type="number" min={0} max={top} step={0.1} value={form.eval_config.ec_pass}
                    onChange={(e) => set("eval_config", { ...form.eval_config, ec_pass: Number(e.target.value) })} />
                )}
              </Field>
              <Field label={t("Mínimo en la {0}", { 0: pfLabel(rules) })}>
                {(id) => (
                  <input id={id} type="number" min={0} max={top} step={0.1} value={form.eval_config.pf_min}
                    onChange={(e) => set("eval_config", { ...form.eval_config, pf_min: Number(e.target.value) })} />
                )}
              </Field>
            </>
          )}
        </div>
        <p className="muted small">{t("Los grupos de evaluación, con su peso y mínimo, se editan en la ficha de la asignatura.")}</p>
      </fieldset>

      <fieldset className="fieldset">
        <legend>{t("Enlaces (aula, apuntes, foro…)")}</legend>
        {form.links.map((l, i) => (
          <div className="inline-form" key={i}>
            <input aria-label={t("Texto del enlace")} placeholder={t("Apuntes")} maxLength={80} value={l.label} onChange={(e) => setLink(i, { label: e.target.value })} />
            <input aria-label={t("URL")} placeholder={t("https://… u obsidian://…")} maxLength={500} value={l.url} onChange={(e) => setLink(i, { url: e.target.value })} />
            <button type="button" className="icon-btn" aria-label={t("Quitar enlace")} onClick={() => set("links", form.links.filter((_, j) => j !== i))}>
              ✕
            </button>
          </div>
        ))}
        <div className="inline-form">
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => set("links", [...form.links, { label: "", url: "" }])}>
            {t("+ Enlace")}
          </button>
          {settings?.obsidian_vault && (
            <>
              <input aria-label={t("Carpeta o nota en Obsidian")} placeholder={t("matematicas-i/2026s1/apuntes")} value={notesPath} onChange={(e) => setNotesPath(e.target.value)} />
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                disabled={!notesPath.trim()}
                onClick={() => {
                  set("links", [...form.links, { label: t("Apuntes (Obsidian)"), url: obsidianUrl(settings.obsidian_vault, notesPath.trim()) }]);
                  setNotesPath("");
                }}
              >
                {t("+ Obsidian")}
              </button>
            </>
          )}
        </div>
      </fieldset>

      <Field label={t("Notas")} wide>
        {(id) => <textarea id={id} rows={3} maxLength={10000} value={form.notes} onChange={(e) => set("notes", e.target.value)} />}
      </Field>

      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={state.status === "loading"}>
          {subjectId ? t("Guardar") : t("Añadir asignatura")}
        </button>
        <FormStatus state={state} />
      </div>
    </form>
  );
}
