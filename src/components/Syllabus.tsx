import { useEffect, useState } from "react";
import { api, type GenerationJob, type ObjectiveKind, type SyllabusView } from "../api";
import { fmtDate } from "../lib/format";
import { linkTo, type Navigate } from "../router";
import { Card, ConfirmDelete, ErrorBox, Field, FormStatus, Loading, PageHeader, useLoad, useSubmit } from "../ui";
import { t } from "../i18n";

const KIND_LABEL: Record<ObjectiveKind, string> = {
  general: t("Objetivos generales"),
  conocimiento: t("Conocimientos"),
  habilidad: t("Habilidades"),
  competencia: t("Competencias"),
};
const KIND_ORDER: ObjectiveKind[] = ["general", "conocimiento", "habilidad", "competencia"];

/** Espera a que termine un trabajo de IA (plan docente) y avisa con el resultado. */
export function useJobWatch(onDone: (job: GenerationJob) => void) {
  const [jobId, setJobId] = useState<number | null>(null);
  const [job, setJob] = useState<GenerationJob | null>(null);
  useEffect(() => {
    if (jobId === null) return;
    let stop = false;
    const tick = async () => {
      const j = await api.learn.job(jobId).catch(() => null);
      if (stop || !j) return;
      setJob(j);
      if (j.status === "done" || j.status === "error") {
        setJobId(null);
        onDone(j);
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 4000);
    return () => {
      stop = true;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);
  return { job, watch: setJobId, watching: jobId !== null };
}

function PlanUpload({ subjectId, navigate, label }: { subjectId: number; navigate: Navigate; label: string }) {
  const [file, setFile] = useState<File | null>(null);
  const { state, run } = useSubmit();
  const { job, watch, watching } = useJobWatch((j) => {
    if (j.status === "done") navigate({ name: "draft", id: j.id });
  });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const res = await run(() => api.syllabus.import(subjectId, file), t("Leyendo el plan docente: tarda un par de minutos"));
    if (res) watch(res.id);
  };
  return (
    <form className="form" onSubmit={submit}>
      <div className="form-grid">
        <Field label={label} wide>
          {(id) => <input id={id} type="file" accept=".pdf,.md,.txt,.html,.htm,application/pdf,text/markdown,text/plain,text/html" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
        </Field>
      </div>
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={!file || watching || state.status === "loading"}>
          {watching ? t("Leyendo…") : t("✨ Leer plan docente")}
        </button>
        <FormStatus state={state} />
        {job?.status === "error" && <p className="small text-crit">{job.error}</p>}
      </div>
    </form>
  );
}

function MasteryBar({ value, label }: { value: number | null; label: string }) {
  const pct = value === null ? null : Math.round(value * 100);
  return (
    <span className="mastery__bar" role="img" aria-label={label}>
      <span className="mastery__fill" style={{ width: `${pct ?? 0}%` }} />
    </span>
  );
}

/** Ficha de la asignatura: el plan docente (objetivos, temario, recursos) o el formulario para subirlo. */
export function SyllabusCard({ subjectId, navigate }: { subjectId: number; navigate: Navigate }) {
  const q = useLoad(() => api.syllabus.get(subjectId), [subjectId]);
  const s = q.data;
  if (q.loading) return null;
  if (q.error) return <ErrorBox message={q.error} onRetry={q.reload} />;
  if (!s?.has_plan)
    return (
      <Card title={t("Plan docente")}>
        <p className="muted small">
          {t("Sube el plan docente de la asignatura (el PDF que publica la universidad) y la app saca sus objetivos de aprendizaje, el temario por módulos, los recursos, la evaluación y las fechas. Lo revisas antes de aplicarlo, y Aprender alinea la teoría y los ejercicios con esos objetivos.")}
        </p>
        <PlanUpload subjectId={subjectId} navigate={navigate} label={t("Plan docente (PDF, Markdown o HTML)")} />
      </Card>
    );
  return (
    <Card title={t("Plan docente")} actions={<span className="muted small">📄 {s.source}{s.imported_on ? ` · ${fmtDate(s.imported_on)}` : ""}</span>}>
      {s.summary && <p>{s.summary}</p>}
      <SyllabusBody s={s} navigate={navigate} />
      {s.resources.length > 0 && (
        <details>
          <summary>{t("Recursos ({0})", { 0: s.resources.length })}</summary>
          <ul className="plain-list small">
            {s.resources.map((r, i) => (
              <li key={i}>
                {r.title}
                {r.kind && <span className="muted"> · {r.kind}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
      <details>
        <summary>{t("Volver a leer o quitar el plan docente")}</summary>
        <PlanUpload subjectId={subjectId} navigate={navigate} label={t("Plan docente nuevo")} />
        <ConfirmDelete label={t("Quitar plan docente")} onConfirm={() => void api.syllabus.remove(subjectId).then(q.reload)} />
      </details>
    </Card>
  );
}

/** Temario con el progreso por módulo y los objetivos con su dominio (ficha y Aprender). */
function SyllabusBody({ s, navigate, compact = false }: { s: SyllabusView; navigate: Navigate; compact?: boolean }) {
  const byKind = KIND_ORDER.map((k) => [k, s.objectives.filter((o) => o.kind === k)] as const).filter(([, list]) => list.length);
  const practised = s.objectives.filter((o) => o.steps > 0);
  return (
    <div className="stack">
      {s.modules.length > 0 && (
        <section>
          <h3 className="small">{t("Temario")}</h3>
          <ol className="syllabus-modules">
            {s.modules.map((m) => (
              <li key={m.ref}>
                <strong>{m.title}</strong>
                <span className="muted small">
                  {" · "}
                  {m.lessons ? t("{0}/{1} lecciones", { 0: m.lessons_done, 1: m.lessons }) : t("sin lecciones aún")}
                  {m.objectives.length > 0 && ` · ${m.objectives.join(", ")}`}
                </span>
                {!compact && m.topics.length > 0 && <div className="muted small">{m.topics.join(" · ")}</div>}
              </li>
            ))}
          </ol>
        </section>
      )}
      {compact ? (
        practised.length > 0 && (
          <section>
            <h3 className="small">{t("Objetivos de aprendizaje")}</h3>
            <ObjectiveRows list={practised} courseId={s.course_id} navigate={navigate} />
            {practised.length < s.objectives.length && (
              <p className="muted small">{t("{0} objetivos aún sin ejercicios.", { 0: s.objectives.length - practised.length })}</p>
            )}
          </section>
        )
      ) : (
        byKind.map(([kind, list]) => (
          <details key={kind} open={kind === "conocimiento" || kind === "habilidad"}>
            <summary>
              {KIND_LABEL[kind]} ({list.length})
            </summary>
            <ObjectiveRows list={list} courseId={s.course_id} navigate={navigate} />
          </details>
        ))
      )}
    </div>
  );
}

function ObjectiveRows({ list, courseId, navigate }: { list: SyllabusView["objectives"]; courseId: number | null; navigate: Navigate }) {
  return (
    <ul className="mastery">
      {list.map((o) => {
        const pct = o.mastery === null ? null : Math.round(o.mastery * 100);
        const level = pct === null ? "none" : pct >= 80 ? "ok" : pct >= 50 ? "mid" : "low";
        return (
          <li key={o.code} className={`mastery__row mastery__row--${level} objective-row`}>
            <span className="mastery__name">
              <strong>{o.code}</strong> {o.text}
            </span>
            {o.steps > 0 ? (
              <>
                <MasteryBar value={o.mastery} label={pct === null ? t("{0}: sin practicar", { 0: o.code }) : t("{0}: {1} % de aciertos", { 0: o.code, 1: pct })} />
                <span className="mastery__pct small">{pct === null ? "—" : `${pct} %`}</span>
                {courseId && (
                  <a className="btn btn--ghost btn--xs" href={`/aprender/practica/${courseId}/objetivo/${encodeURIComponent(o.code)}`}
                    onClick={linkTo(navigate, { name: "practice", courseId, concept: "", objective: o.code })}>
                    {t("Practicar")}
                  </a>
                )}
              </>
            ) : (
              <span className="muted small">{t("sin ejercicios")}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Aprender: temario y objetivos de la asignatura elegida, con su progreso. */
export function SyllabusProgress({ subjectId, navigate }: { subjectId: number; navigate: Navigate }) {
  const q = useLoad(() => api.syllabus.get(subjectId), [subjectId]);
  if (!q.data?.has_plan) return null;
  return (
    <Card title={t("Plan docente")}>
      <SyllabusBody s={q.data} navigate={navigate} compact />
    </Card>
  );
}

/** Revisión del borrador de un plan docente antes de aplicarlo a la asignatura. */
export function PlanReview({ job, navigate }: { job: GenerationJob; navigate: Navigate }) {
  const plan = job.draft?.plan;
  const state0 = job.subject_state;
  const [useEval, setUseEval] = useState(!state0?.has_groups);
  // Lo que ya está en la agenda empieza desmarcado: así no se duplica.
  const [chosen, setChosen] = useState<Set<number>>(() => new Set((plan?.activities ?? []).map((_, i) => i).filter((i) => !state0?.existing[i])));
  const { state, run } = useSubmit();
  if (!plan) return <Loading />;
  const toggle = (i: number) =>
    setChosen((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  const apply = async () => {
    const res = await run(() => api.learn.importJob(job.id, { subject_id: job.subject_id, exclude: [], use_eval: useEval, activities: [...chosen] }), t("Plan docente aplicado"));
    if (res && job.subject_id) navigate({ name: "subject", id: job.subject_id });
  };
  return (
    <div className="page">
      <PageHeader
        title={job.title}
        subtitle={`${job.filenames.join(", ")} · ${t("{0} objetivos, {1} módulos, {2} fechas", { 0: plan.objectives.length, 1: plan.modules.length, 2: plan.activities.length })}`}
        actions={
          <a className="btn btn--ghost" href="/aprender" onClick={linkTo(navigate, { name: "learn" })}>
            {t("← Aprender")}
          </a>
        }
      />
      <p className="banner banner--warn small">{t("Lo ha extraído una IA del plan docente: compáralo con el original antes de aplicarlo.")}</p>

      <Card title={t("Objetivos de aprendizaje")}>
        {plan.summary && <p>{plan.summary}</p>}
        {KIND_ORDER.map((k) => {
          const list = plan.objectives.filter((o) => o.kind === k);
          return list.length ? (
            <section key={k}>
              <h3 className="small">{KIND_LABEL[k]}</h3>
              <ul className="plain-list small">
                {list.map((o) => (
                  <li key={o.code}>
                    <strong>{o.code}</strong> {o.text}
                  </li>
                ))}
              </ul>
            </section>
          ) : null;
        })}
      </Card>

      <Card title={t("Temario")}>
        <ol className="syllabus-modules">
          {plan.modules.map((m) => (
            <li key={m.ref}>
              <strong>{m.title}</strong>
              {m.objectives.length > 0 && <span className="muted small"> · {m.objectives.join(", ")}</span>}
              <div className="muted small">{m.topics.join(" · ")}</div>
            </li>
          ))}
        </ol>
      </Card>

      {plan.groups.length > 0 && (
        <Card title={t("Evaluación")}>
          <ul className="plain-list small">
            {plan.groups.map((g) => (
              <li key={g.name}>
                <strong>{g.name}</strong> {g.weight} %{g.min_grade !== null && ` · ${t("mínimo {0}", { 0: g.min_grade })}`}
              </li>
            ))}
          </ul>
          <label className="check">
            <input type="checkbox" checked={useEval} onChange={(e) => setUseEval(e.target.checked)} />{" "}
            {state0?.has_groups ? t("Sustituir la evaluación que ya tiene la asignatura por esta") : t("Usar esta evaluación")}
          </label>
        </Card>
      )}

      {plan.activities.length > 0 && (
        <Card title={t("Fechas para la agenda")}>
          <ul className="draft-steps">
            {plan.activities.map((a, i) => (
              <li key={i} className={`draft-step${chosen.has(i) ? "" : " is-off"}`}>
                <label className="check draft-step__toggle">
                  <input type="checkbox" checked={chosen.has(i)} onChange={() => toggle(i)} aria-label={t("Añadir: {0}", { 0: a.name })} />
                </label>
                <div className="draft-step__body">
                  <strong>{a.name}</strong>
                  <div className="muted small">
                    {a.window_start && `${fmtDate(a.window_start)} → `}
                    {a.due_date ? fmtDate(a.due_date) : t("sin fecha")}
                    {a.group && ` · ${a.group}`}
                    {state0?.existing[i] && ` · ${t("ya está en tu agenda")}`}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title={t("Aplicar a la asignatura")}>
        <p className="muted small">
          {t("Se guardan los objetivos, el temario y los recursos; la evaluación y las fechas, solo lo marcado. La política de IA solo se rellena si estaba sin indicar: nunca se relaja.")}
        </p>
        <div className="form-actions">
          <button type="button" className="btn btn--primary" disabled={state.status === "loading"} onClick={() => void apply()}>
            {t("Aplicar plan docente")}
          </button>
          <FormStatus state={state} />
        </div>
      </Card>
    </div>
  );
}
