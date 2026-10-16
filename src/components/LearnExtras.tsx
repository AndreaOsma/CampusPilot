import { useEffect, useState } from "react";
import { api, type GenerationJob } from "../api";
import { fmtDate } from "../lib/format";
import { linkTo, type Navigate } from "../router";
import { useStore } from "../store";
import { Card, ConfirmDelete, Field, FormStatus, useLoad, useSubmit, useUiMode } from "../ui";
import { t } from "../i18n";

export function Mastery({ courseId, navigate }: { courseId: number; navigate: Navigate }) {
  const concepts = useLoad(() => api.learn.concepts(courseId), [courseId]);
  const mode = useUiMode();
  const [all, setAll] = useState(false);
  // Lo más flojo primero; lo que aún no has practicado, al final.
  const sorted = [...(concepts.data ?? [])].sort((a, b) => (a.mastery ?? 2) - (b.mastery ?? 2) || a.concept.localeCompare(b.concept));
  const limit = all || mode === "detailed" ? sorted.length : 6;
  const list = sorted.slice(0, limit);
  if (!list.length) return null;
  return (
    <Card
      title={t("Dominio por concepto")}
      actions={
        <a className="btn btn--ghost btn--sm" href={`/aprender/practica/${courseId}`} onClick={linkTo(navigate, { name: "practice", courseId, concept: "" })}>
          {t("🎯 Practicar lo más flojo")}
        </a>
      }
    >
      <ul className="mastery">
        {list.map((c) => {
          const pct = c.mastery === null ? null : Math.round(c.mastery * 100);
          const level = pct === null ? "none" : pct >= 80 ? "ok" : pct >= 50 ? "mid" : "low";
          return (
            <li key={c.concept} className={`mastery__row mastery__row--${level}`}>
              <span className="mastery__name">{c.concept}</span>
              <span className="mastery__bar" role="img" aria-label={pct === null ? t("{0}: sin practicar", { 0: c.concept }) : t("{0}: {1} % de aciertos", { 0: c.concept, 1: pct })}>
                <span className="mastery__fill" style={{ width: `${pct ?? 0}%` }} />
              </span>
              <span className="mastery__pct small">{pct === null ? "—" : `${pct} %`}</span>
              <a className="btn btn--ghost btn--xs" href={`/aprender/practica/${courseId}/${encodeURIComponent(c.concept)}`}
                onClick={linkTo(navigate, { name: "practice", courseId, concept: c.concept })}>
                {t("Practicar")}
              </a>
              {c.confident_wrong > 0 && (
                <span className="mastery__warn small" title={t("Fallos con confianza alta")}>
                  ⚠ {c.confident_wrong}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      {sorted.length > list.length && (
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => setAll(true)}>
          {t("Ver los")} {sorted.length} {t("conceptos")}
        </button>
      )}
      <p className="muted small detail-only">{t("Aciertos sobre intentos de los ejercicios de cada concepto. ⚠ = fallos en los que tenías claro que acertabas.")}</p>
    </Card>
  );
}

const JOB_LABEL: Record<GenerationJob["status"], string> = { queued: t("En cola"), running: t("Generando…"), done: t("Listo para revisar"), error: t("Error") };

/** Genera lecciones para el curso de una asignatura (siempre una: no hay cursos sueltos). */
export function Generator({ navigate, subjectId }: { navigate: Navigate; subjectId: number | null }) {
  const { subjects } = useStore();
  const status = useLoad(() => api.learn.generatorStatus());
  const jobs = useLoad(() => api.learn.jobs());
  const [files, setFiles] = useState<File[]>([]);
  const [kind, setKind] = useState("manual");
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState<"lessons" | "theory">("lessons");
  const [moduleRef, setModuleRef] = useState("");
  const plan = useLoad(() => (subjectId ? api.syllabus.get(subjectId) : Promise.resolve(null)), [subjectId]);
  const modules = plan.data?.modules ?? [];
  const library = useLoad(() => (subjectId ? api.materials.list(subjectId) : Promise.resolve([])), [subjectId]);
  const [picked, setPicked] = useState<number[]>([]);
  useEffect(() => setPicked([]), [subjectId]);
  const { state, run } = useSubmit();
  const running = (jobs.data ?? []).some((j) => j.status === "queued" || j.status === "running");
  const reloadJobs = jobs.reload;

  useEffect(() => {
    if (!running) return;
    const t = window.setInterval(() => void reloadJobs(), 5000);
    return () => window.clearInterval(t);
  }, [running, reloadJobs]);

  const subject = subjects.find((x) => x.id === subjectId);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!files.length && !picked.length) || !subjectId) return;
    const res = await run(() => api.learn.generate(files, kind, title, subjectId, mode, mode === "lessons" ? moduleRef : "", picked), t("Generando: tarda unos minutos, puedes seguir con otra cosa"));
    if (res) {
      setFiles([]);
      setPicked([]);
      void jobs.reload();
      void library.reload();
    }
  };

  const st = status.data;
  return (
    <Card title={subject ? t("Generar lecciones de {0}", { 0: subject.name }) : t("Generar lecciones de tus materiales")}>
      {st && !st.enabled && (
        <p className="banner banner--warn small">
          {t("Sin IA configurada:")} {st.reason}.{" "}
          <a href="/ajustes#ia" onClick={linkTo(navigate, { name: "settings" })}>
            {t("Configúrala en Ajustes")}
          </a>
          .
        </p>
      )}
      <p className="muted small detail-only">
        {t("Sube un módulo del manual, tus apuntes o la transcripción de un vídeo resumen (PDF, .md o .txt). Saldrá un borrador de lecciones: primero la teoría, sacada del material, y luego los ejercicios, cada cosa con la referencia exacta del apartado de donde sale; lo revisas antes de importarlo. Nunca se usan enunciados de actividades evaluables (entregas, prácticas, retos, cuestionarios o exámenes).")}
      </p>
      {!subjectId && <p className="muted small">{t("Elige arriba la asignatura: las lecciones se añaden a su curso.")}</p>}
      {subject?.ai_policy === "forbidden" && (
        <p className="banner banner--warn small">{t("En esta asignatura la IA está prohibida en evaluables: solo se aceptan manual, apuntes o vídeo.")}</p>
      )}
      <form className="form" onSubmit={submit}>
        <div className="form-grid">
          {(library.data ?? []).length > 0 && (
            <fieldset className="field field--wide plain-fieldset">
              <legend className="small">{t("De tu biblioteca")}</legend>
              {(library.data ?? []).map((m) => (
                <label key={m.id} className="check">
                  <input type="checkbox" checked={picked.includes(m.id)}
                    onChange={(e) => setPicked(e.target.checked ? [...picked, m.id] : picked.filter((x) => x !== m.id))} />{" "}
                  {m.filename}
                </label>
              ))}
            </fieldset>
          )}
          <Field label={(library.data ?? []).length ? t("…o sube material nuevo (se guarda en la biblioteca)") : t("Material")} wide>
            {(id) => (
              <input id={id} type="file" multiple accept=".pdf,.md,.txt,.markdown,application/pdf,text/markdown,text/plain" disabled={!st?.enabled}
                onChange={(e) => setFiles([...(e.target.files ?? [])])} />
            )}
          </Field>
          <Field label={t("Qué sale")}>
            {(id) => (
              <select id={id} value={mode} onChange={(e) => setMode(e.target.value as "lessons" | "theory")}>
                <option value="lessons">{t("Lecciones nuevas, con su teoría")}</option>
                <option value="theory">{t("Teoría para las lecciones que ya tengo")}</option>
              </select>
            )}
          </Field>
          {mode === "lessons" && modules.length > 0 && (
            <Field label={t("Módulo del plan docente")}>
              {(id) => (
                <select id={id} value={moduleRef} onChange={(e) => setModuleRef(e.target.value)}>
                  <option value="">{t("Sin indicar")}</option>
                  {modules.map((m) => (
                    <option key={m.ref} value={m.ref}>
                      {m.title}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          )}
          <Field label={t("Qué es")}>
            {(id) => (
              <select id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                {Object.entries(st?.kinds ?? { manual: t("Manual o módulo") }).map(([k, v]) => (
                  <option key={k} value={k} disabled={subject?.ai_policy === "forbidden" && k === "otro"}>
                    {v}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={t("Título del borrador")}>
            {(id) => <input id={id} maxLength={200} placeholder={t("Módulo 2 · Matrices")} value={title} onChange={(e) => setTitle(e.target.value)} />}
          </Field>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={!st?.enabled || !subjectId || (!files.length && !picked.length) || running || state.status === "loading"}>
            {t("✨ Generar borrador")}
          </button>
          <FormStatus state={state} />
        </div>
      </form>
      {(jobs.data ?? []).length > 0 && (
        <ul className="row-list jobs">
          {(jobs.data ?? []).map((j) => (
            <li key={j.id} className="row-list__item">
              <div>
                <strong>{j.title || j.filenames.join(", ")}</strong>
                {j.subject_id && <span className="muted small"> · {subjects.find((x) => x.id === j.subject_id)?.name}</span>}
                <div className={`small ${j.status === "error" ? "text-crit" : "muted"}`}>
                  {JOB_LABEL[j.status]} · {fmtDate(j.created_at.slice(0, 10))}
                  {j.status === "done" && ` · ${j.mode === "plan" && j.plan_counts ? t("{0} objetivos, {1} módulos, {2} fechas", { 0: j.plan_counts.objectives, 1: j.plan_counts.modules, 2: j.plan_counts.activities }) : t(j.mode === "theory" ? "{0} tarjetas de teoría" : "{0} pasos", { 0: j.steps })}${j.review ? t(" · {0} para revisar", { 0: j.review }) : ""}${j.dropped ? t(" · {0} descartados", { 0: j.dropped }) : ""}`}
                  {j.status === "error" && ` · ${j.error}`}
                </div>
              </div>
              <span className="row-actions">
                {j.status === "done" && (
                  <a className="btn btn--primary btn--sm" href={`/aprender/borrador/${j.id}`} onClick={linkTo(navigate, { name: "draft", id: j.id })}>
                    {t("Revisar")}
                  </a>
                )}
                {j.status !== "running" && <ConfirmDelete label="✕" onConfirm={() => void api.learn.removeJob(j.id).then(jobs.reload)} />}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

