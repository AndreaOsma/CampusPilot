import { useState } from "react";
import { api, type Material, type TutorAnswer } from "../api";
import { RichText } from "../lib/rich";
import { Card, ConfirmDelete, Field, FormStatus, useLoad, useSubmit } from "../ui";
import { t } from "../i18n";
import { BookOpen, Icon, Play, Upload } from "../vendor/icons";

const KINDS: Record<string, string> = { manual: t("Manual o módulo"), apuntes: t("Mis apuntes"), video: t("Vídeo resumen (transcripción)"), otro: t("Otro material") };
const VIDEO = /\.(mp4|m4v|webm|mov)$/i;
const NO_UNIT = "";

/** Aprender: los recursos de aprendizaje de la asignatura, por unidad (módulos y apuntes en PDF que
 *  se abren por la página, vídeos que se ven aquí). El generador y el tutor usan su texto; en un
 *  vídeo, su transcripción. */
export function LibraryCard({ subjectId, forbidden }: { subjectId: number; forbidden: boolean }) {
  const list = useLoad(() => api.materials.list(subjectId), [subjectId]);
  const plan = useLoad(() => api.syllabus.get(subjectId), [subjectId]);
  const modules = plan.data?.modules ?? [];
  const moduleName = new Map(modules.map((m) => [m.ref, m.title]));
  const items = list.data ?? [];
  // Unidades: las del plan docente y las que ya se hayan escrito a mano en algún recurso.
  const units = [...new Set([...modules.map((m) => m.ref), ...items.map((m) => m.module_ref).filter(Boolean)])];
  const unitLabel = (ref: string) => (ref ? moduleName.get(ref) ?? ref : t("Sin unidad"));
  const groups = [...units, NO_UNIT]
    .map((ref) => ({ ref, items: items.filter((m) => (m.module_ref || NO_UNIT) === ref) }))
    .filter((g) => g.items.length > 0);

  const [file, setFile] = useState<File | null>(null);
  const [transcript, setTranscript] = useState<File | null>(null);
  const [kind, setKind] = useState("manual");
  const [unit, setUnit] = useState("");
  const { state, run } = useSubmit();
  const isVideo = !!file && VIDEO.test(file.name);

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const done = await run(
      () => (isVideo ? api.materials.uploadVideo(subjectId, file, transcript, unit.trim()) : api.materials.upload(subjectId, file, kind, unit.trim())),
      t("Guardado en los recursos"),
    );
    if (done) {
      setFile(null);
      setTranscript(null);
      (e.target as HTMLFormElement).reset();
      void list.reload();
    }
  };
  const unitInput = (id: string, value: string, onChange: (v: string) => void) =>
    modules.length > 0 ? (
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{t("Sin unidad")}</option>
        {modules.map((m) => (
          <option key={m.ref} value={m.ref}>
            {m.title}
          </option>
        ))}
      </select>
    ) : (
      <input id={id} value={value} onChange={(e) => onChange(e.target.value)} list={`units-${subjectId}`} maxLength={64} placeholder={t("Por ejemplo: Unidad 2")} />
    );

  return (
    <Card title={t("Recursos de aprendizaje")}>
      <p className="muted small">
        {t("Los materiales de cada unidad: módulos y apuntes (se abren por la página que cita la teoría) y vídeos con su transcripción. El generador y el tutor los usan sin volver a subirlos.")}
      </p>
      <datalist id={`units-${subjectId}`}>
        {units.map((u) => (
          <option key={u} value={u} />
        ))}
      </datalist>
      {groups.length === 0 && !list.loading && <p className="muted">{t("Aún no hay recursos. Sube el módulo o el vídeo de la unidad que estés estudiando.")}</p>}
      {groups.map((g) => (
        <section key={g.ref || "sin"} className="resources-unit" aria-label={unitLabel(g.ref)}>
          <h3 className="resources-unit__title">{unitLabel(g.ref)}</h3>
          <ul className="row-list">
            {g.items.map((m: Material) => (
              <ResourceRow key={m.id} m={m} unitInput={unitInput} reload={() => void list.reload()} />
            ))}
          </ul>
        </section>
      ))}
      <form className="form" onSubmit={upload}>
        <div className="form-grid">
          <Field label={t("Recurso")} hint={t("PDF, Markdown, texto o vídeo (MP4, WebM, MOV)")} wide>
            {(id) => (
              <input id={id} type="file" accept=".pdf,.md,.txt,.markdown,.mp4,.m4v,.webm,.mov,application/pdf,text/markdown,text/plain,video/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            )}
          </Field>
          {isVideo ? (
            <Field label={t("Transcripción del vídeo")} hint={t("Opcional: es lo que lee la IA (PDF, .md o .txt)")}>
              {(id) => <input id={id} type="file" accept=".pdf,.md,.txt,.markdown,application/pdf,text/markdown,text/plain" onChange={(e) => setTranscript(e.target.files?.[0] ?? null)} />}
            </Field>
          ) : (
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
          )}
          <Field label={t("Unidad")}>{(id) => unitInput(id, unit, setUnit)}</Field>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={!file || state.status === "loading"}>
            {state.status === "loading" ? t("Subiendo…") : <><Icon svg={Upload} /> {t("Guardar recurso")}</>}
          </button>
          <FormStatus state={state} />
        </div>
      </form>
    </Card>
  );
}

function ResourceRow({ m, unitInput, reload }: {
  m: Material;
  unitInput: (id: string, value: string, onChange: (v: string) => void) => React.ReactNode;
  reload: () => void;
}) {
  const [moving, setMoving] = useState(false);
  const [unit, setUnit] = useState(m.module_ref);
  const video = m.has_file && m.file_mime.startsWith("video/");
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.materials.setModule(m.id, unit.trim());
    setMoving(false);
    reload();
  };
  return (
    <li className="row-list__item resource">
      <div className="resource__main">
        <strong>
          <span aria-hidden="true">{video ? "🎬 " : m.has_file ? "📄 " : "📝 "}</span>
          {m.filename}
        </strong>
        <div className="muted small">
          {KINDS[m.kind] ?? m.kind}
          {m.pages ? ` · ${t("{0} págs.", { 0: m.pages })}` : ""}
          {video && !m.chars ? ` · ${t("sin transcripción (la IA no lo puede usar)")}` : ""}
        </div>
        {video && (
          <details className="resource__video">
            <summary><Icon svg={Play} /> {t("Ver el vídeo")}</summary>
            <video controls preload="metadata" playsInline src={api.materials.fileUrl(m.id)} aria-label={m.filename} />
          </details>
        )}
        {moving && (
          <form className="resource__move" onSubmit={save}>
            <label htmlFor={`unit-${m.id}`}>{t("Unidad")}</label>
            {unitInput(`unit-${m.id}`, unit, setUnit)}
            <button type="submit" className="btn btn--ghost btn--sm">{t("Guardar")}</button>
          </form>
        )}
      </div>
      <span className="row-actions">
        {m.has_file && !video && (
          <a className="btn btn--ghost btn--sm" href={api.materials.fileUrl(m.id)} target="_blank" rel="noreferrer">
            {t("Abrir")}
          </a>
        )}
        <button type="button" className="btn btn--ghost btn--sm" aria-expanded={moving} onClick={() => setMoving(!moving)}>
          {t("Unidad…")}
        </button>
        <ConfirmDelete label={t("Quitar")} onConfirm={() => void api.materials.remove(m.id).then(reload)} />
      </span>
    </li>
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
                      <Icon svg={BookOpen} />{" "}
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
