import { useState } from "react";
import { api, type Material, type TutorAnswer } from "../api";
import { RichText } from "../lib/rich";
import { Card, ConfirmDelete, Field, FormStatus, useLoad, useSubmit } from "../ui";
import { t } from "../i18n";

const KINDS: Record<string, string> = { manual: t("Manual o módulo"), apuntes: t("Mis apuntes"), video: t("Vídeo resumen (transcripción)"), otro: t("Otro material") };

/** Aprender: los materiales guardados de la asignatura (para generar, el tutor y abrir la teoría por la página). */
export function LibraryCard({ subjectId, forbidden }: { subjectId: number; forbidden: boolean }) {
  const list = useLoad(() => api.materials.list(subjectId), [subjectId]);
  const plan = useLoad(() => api.syllabus.get(subjectId), [subjectId]);
  const modules = plan.data?.modules ?? [];
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState("manual");
  const [moduleRef, setModuleRef] = useState("");
  const { state, run } = useSubmit();
  const moduleName = new Map(modules.map((m) => [m.ref, m.title]));

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    if (await run(() => api.materials.upload(subjectId, file, kind, moduleRef), t("Guardado en la biblioteca"))) {
      setFile(null);
      void list.reload();
    }
  };
  return (
    <Card title={t("Biblioteca")}>
      <p className="muted small detail-only">
        {t("Tus materiales de esta asignatura: el generador y el tutor los usan sin volver a subirlos, y la teoría abre el PDF por la página que cita.")}
      </p>
      {(list.data ?? []).length > 0 && (
        <ul className="row-list">
          {(list.data ?? []).map((m: Material) => (
            <li key={m.id} className="row-list__item">
              <div>
                <strong>{m.filename}</strong>
                <div className="muted small">
                  {KINDS[m.kind] ?? m.kind}
                  {m.module_ref && ` · ${moduleName.get(m.module_ref) ?? m.module_ref}`}
                  {m.pages ? ` · ${t("{0} págs.", { 0: m.pages })}` : ""}
                </div>
              </div>
              <span className="row-actions">
                {m.has_file && (
                  <a className="btn btn--ghost btn--sm" href={api.materials.fileUrl(m.id)} target="_blank" rel="noreferrer">
                    {t("Abrir")}
                  </a>
                )}
                <ConfirmDelete label="✕" onConfirm={() => void api.materials.remove(m.id).then(list.reload)} />
              </span>
            </li>
          ))}
        </ul>
      )}
      <form className="form" onSubmit={upload}>
        <div className="form-grid">
          <Field label={t("Material")} wide>
            {(id) => <input id={id} type="file" accept=".pdf,.md,.txt,.markdown,application/pdf,text/markdown,text/plain" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
          </Field>
          <Field label={t("Qué es")}>
            {(id) => (
              <select id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                {Object.entries(KINDS).map(([k, v]) => (
                  <option key={k} value={k} disabled={forbidden && k === "otro"}>
                    {v}
                  </option>
                ))}
              </select>
            )}
          </Field>
          {modules.length > 0 && (
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
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn--ghost" disabled={!file || state.status === "loading"}>
            {t("⬆ Guardar en la biblioteca")}
          </button>
          <FormStatus state={state} />
        </div>
      </form>
    </Card>
  );
}

type Turn = { role: "user" | "tutor"; text: string; answer?: TutorAnswer };

/** Aprender: pregunta tus dudas de teoría; responde solo con tu material y dice de dónde sale. */
export function TutorCard({ subjectId }: { subjectId: number }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const { state, run } = useSubmit();
  const ask = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (q.length < 2) return;
    const history = turns.map(({ role, text }) => ({ role, text }));
    const res = await run(() => api.tutor({ subject_id: subjectId, question: q, history }), t("Respondido"));
    if (res) {
      setTurns([...turns, { role: "user", text: q }, { role: "tutor", text: res.answer, answer: res }]);
      setQuestion("");
    }
  };
  return (
    <Card title={t("Pregunta tus dudas")} actions={turns.length > 0 ? <button type="button" className="btn btn--ghost btn--sm" onClick={() => setTurns([])}>{t("Nueva conversación")}</button> : undefined}>
      <p className="muted small">{t("Responde solo con los materiales de tu biblioteca y te dice de dónde sale. No trabaja actividades evaluables: esas, al foro del aula.")}</p>
      {turns.length > 0 && (
        <ol className="tutor" aria-live="polite">
          {turns.map((turn, i) => (
            <li key={i} className={`tutor__turn tutor__turn--${turn.role}`}>
              {turn.role === "user" ? (
                <p>{turn.text}</p>
              ) : (
                <>
                  <RichText text={turn.text} />
                  {turn.answer && !turn.answer.in_material && <p className="small text-warn">{t("No está en tu material: compruébalo con el profesorado.")}</p>}
                  {turn.answer && turn.answer.citations.length > 0 && (
                    <p className="small muted">
                      📖{" "}
                      {turn.answer.citations.map((c, j) => (
                        <span key={j}>
                          {j > 0 && " · "}
                          {c.material_id && c.has_file ? (
                            <a href={api.materials.fileUrl(c.material_id, c.page)} target="_blank" rel="noreferrer">
                              {c.material}
                              {c.page ? `, p. ${c.page}` : ""}
                            </a>
                          ) : (
                            `${c.material}${c.page ? `, p. ${c.page}` : ""}`
                          )}
                          {c.section && ` (${c.section})`}
                        </span>
                      ))}
                    </p>
                  )}
                </>
              )}
            </li>
          ))}
        </ol>
      )}
      <form className="form" onSubmit={ask}>
        <Field label={t("Tu pregunta")} wide>
          {(id) => <textarea id={id} rows={3} maxLength={2000} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={t("Por ejemplo: ¿por qué se hace este paso en el ejemplo resuelto 3?")} />}
        </Field>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={question.trim().length < 2 || state.status === "loading"}>
            {state.status === "loading" ? t("Pensando…") : t("Preguntar")}
          </button>
          <FormStatus state={state} />
        </div>
      </form>
    </Card>
  );
}
