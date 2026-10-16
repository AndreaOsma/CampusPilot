import { useMemo, useState } from "react";
import { api, type DraftStep } from "../api";
import { InlineRich, RichText, TheoryFigure } from "../lib/rich";
import { linkTo, type Navigate } from "../router";
import { useStore } from "../store";
import { PlanReview } from "../components/Syllabus";
import { DegreeReview } from "../components/DegreePlan";
import { Card, ErrorBox, Field, FormStatus, Loading, PageHeader, useLoad, useSubmit } from "../ui";
import { t } from "../i18n";

const KIND: Record<DraftStep["kind"], string> = {
  info: t("📘 Teoría"),
  choice: t("Opción múltiple"),
  truefalse: "Verdadero / falso",
  numeric: t("Numérico"),
  complex: t("Complejo"),
  order: t("Ordenar"),
  param: t("Números nuevos cada vez"),
  match: t("Emparejar"),
};

/** Resumen legible de la solución de un paso del borrador, para revisarla de un vistazo. */
function solutionOf(step: DraftStep): string {
  const d = step.data as Record<string, any>;
  switch (step.kind) {
    case "choice":
      return (d.correct ?? []).map((i: number) => d.options?.[i]).join(" · ");
    case "truefalse":
      return d.answer ? t("Verdadero") : t("Falso");
    case "numeric":
      return `${d.answer}${d.unit ? ` ${d.unit}` : ""} (±${d.tolerance ?? 0})`;
    case "complex":
      return `${d.re} + ${d.im}i (±${d.tolerance ?? 0})`;
    case "order":
      return (d.items ?? []).join(" → ");
    case "param":
      return d.answer?.kind === "complex" ? `re = ${d.answer.re}, im = ${d.answer.im}` : `= ${d.answer?.value}`;
    case "match":
      return (d.pairs ?? []).map((p: [string, string]) => `${p[0]} ↔ ${p[1]}`).join(" · ");
    default:
      return "";
  }
}

export function DraftReview({ navigate, jobId }: { navigate: Navigate; jobId: number }) {
  const job = useLoad(() => api.learn.job(jobId), [jobId]);
  const { subjects } = useStore();
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const { state, run } = useSubmit();

  const units = job.data?.draft?.units ?? [];
  const total = useMemo(() => units.reduce((a, u) => a + u.lessons.reduce((b, l) => b + l.steps.length, 0), 0), [units]);
  // Lo marcado para revisar empieza excluido: tienes que aceptarlo a propósito.
  const initialised = useMemo(() => {
    const flagged = new Set<string>();
    units.forEach((u) => u.lessons.forEach((l) => l.steps.forEach((s) => s.flag && flagged.add(`${u.ref}/${l.ref}/${s.ref}`))));
    return flagged;
  }, [units]);
  const [touched, setTouched] = useState(false);
  const isExcluded = (key: string) => (touched ? excluded : initialised).has(key);
  const toggle = (key: string) => {
    const base = new Set(touched ? excluded : initialised);
    if (base.has(key)) base.delete(key);
    else base.add(key);
    setExcluded(base);
    setTouched(true);
  };

  if (job.loading) return <Loading />;
  if (job.error) return <ErrorBox message={job.error} onRetry={job.reload} />;
  const j = job.data!;
  if (j.mode === "plan") return <PlanReview job={j} navigate={navigate} />;
  if (j.mode === "career") return <DegreeReview job={j} navigate={navigate} />;
  const exclude = [...(touched ? excluded : initialised)];
  const chosen = total - exclude.length;
  const theory = j.mode === "theory";

  const doImport = async () => {
    const res = await run(
      () => api.learn.importJob(j.id, { subject_id: j.subject_id ?? subjectId, exclude }),
      t("Importado")
    );
    if (res) navigate({ name: "learn" });
  };

  return (
    <div className="page">
      <PageHeader
        title={t("Borrador · {0}", { 0: j.title })}
        subtitle={`${j.filenames.join(", ")} · ${t(theory ? "{0} tarjetas de teoría" : "{0} pasos", { 0: total })}${j.review ? t(" · {0} para revisar", { 0: j.review }) : ""}${j.dropped ? t(" · {0} descartados por no cumplir las reglas", { 0: j.dropped }) : ""}`}
        actions={
          <a className="btn btn--ghost" href="/aprender" onClick={linkTo(navigate, { name: "learn" })}>
            {t("← Aprender")}
          </a>
        }
      />
      <p className="banner banner--warn small">
        {t("Revisa cada ejercicio: lo ha generado una IA a partir de tu material. Los marcados ⚠ no superaron la comprobación automática de la respuesta y empiezan desmarcados. Comprueba que la fuente citada existe en tu material.")}
      </p>
      {theory && <p className="muted small">{t("Cada lección recibe estas tarjetas delante de sus preguntas. Si ya tenía teoría puesta así, se sustituye; sus ejercicios no se tocan.")}</p>}

      {units.map((u) => (
        <Card key={u.ref} title={u.title}>
          {u.lessons.map((l) => (
            <section key={l.ref} className="draft-lesson">
              <h3>{l.title}</h3>
              <ul className="draft-steps">
                {l.steps.map((s) => {
                  const key = `${u.ref}/${l.ref}/${s.ref}`;
                  const off = isExcluded(key);
                  return (
                    <li key={key} className={`draft-step${off ? " is-off" : ""}${s.flag ? " is-flagged" : ""}`}>
                      <label className="check draft-step__toggle">
                        <input type="checkbox" checked={!off} onChange={() => toggle(key)} aria-label={t("Incluir: {0}", { 0: s.prompt.slice(0, 60) })} />
                      </label>
                      <div className="draft-step__body">
                        <div className="muted small">
                          {KIND[s.kind]} · 📖 {s.source}
                          {s.concepts.length > 0 && ` · ${s.concepts.join(", ")}`}
                        </div>
                        <RichText text={s.prompt} className="draft-step__prompt" />
                        {s.kind === "choice" && (
                          <ol className="draft-step__options" type="A">
                            {((s.data.options as string[]) ?? []).map((o, i) => (
                              <li key={i} className={((s.data.correct as number[]) ?? []).includes(i) ? "is-correct" : ""}>
                                <InlineRich text={o} />
                              </li>
                            ))}
                          </ol>
                        )}
                        {s.kind !== "info" && (
                          <p className="small">
                            <strong>{t("Solución:")}</strong> <InlineRich text={solutionOf(s)} />
                          </p>
                        )}
                        {s.explanation && <RichText text={s.explanation} className="small muted" />}
                        {s.kind === "info" && (s.data as { figure?: { svg: string; alt: string; caption?: string } }).figure && (
                          <TheoryFigure figure={(s.data as { figure: { svg: string; alt: string; caption?: string } }).figure} />
                        )}
                        {s.hints.length > 0 && <p className="small muted">💡 {s.hints.join(" · ")}</p>}
                        {s.flag && <p className="small text-crit">⚠ {s.flag}</p>}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </Card>
      ))}

      <Card title={t("Añadir al curso")}>
        {theory ? (
          <p className="muted">{t("Se ponen delante de las preguntas de cada lección de")} <strong>{subjects.find((x) => x.id === j.subject_id)?.name ?? t("su asignatura")}</strong>.</p>
        ) : j.subject_id ? (
          <p className="muted">{t("Se añaden al curso de")} <strong>{subjects.find((x) => x.id === j.subject_id)?.name ?? t("su asignatura")}</strong>.</p>
        ) : (
          <div className="form-grid">
            <Field label={t("Asignatura")}>
              {(id) => (
                <select id={id} value={subjectId ?? ""} onChange={(e) => setSubjectId(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">{t("Elige…")}</option>
                  {subjects.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.name}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
        )}
        <div className="form-actions">
          <button type="button" className="btn btn--primary" disabled={!chosen || !(j.subject_id ?? subjectId) || state.status === "loading"} onClick={() => void doImport()}>
            {theory ? t("Añadir {0} tarjetas de teoría", { 0: chosen }) : <>{t("Añadir")} {chosen} {t("ejercicio")}{chosen === 1 ? "" : "s"} {t("al curso")}</>}
          </button>
          <FormStatus state={state} />
        </div>
      </Card>
    </div>
  );
}
