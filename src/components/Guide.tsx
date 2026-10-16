import { useEffect, useState } from "react";
import { api, type LessonFull } from "../api";
import { obsidianUrl } from "../lib/format";
import { RichText } from "../lib/rich";
import { useStore } from "../store";
import { FormStatus, Loading, Modal, useSubmit } from "../ui";
import { t } from "../i18n";

/** Guía de una lección: tu teoría (la escribes tú) y/o el enlace a tus apuntes. */
export function GuideModal({ lessonId, onClose }: { lessonId: number | null; onClose: () => void }) {
  const { settings } = useStore();
  const [lesson, setLesson] = useState<LessonFull | null>(null);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const { state, run } = useSubmit();

  useEffect(() => {
    setLesson(null);
    setEditing(false);
    if (lessonId === null) return;
    void api.learn.lesson(lessonId).then((l) => {
      setLesson(l);
      setText(l.theory);
      setUrl(l.theory_url);
      setEditing(!l.theory.trim() && !l.theory_url);
    });
  }, [lessonId]);

  const save = async () => {
    if (!lesson) return;
    const res = await run(() => api.learn.saveTheory(lesson.id, text, url), t("Guía guardada"));
    if (res) {
      setLesson({ ...lesson, theory: res.theory, theory_url: res.theory_url });
      setEditing(false);
    }
  };

  return (
    <Modal open={lessonId !== null} title={lesson ? t("Guía · {0}", { 0: lesson.title }) : t("Guía")} onClose={onClose}>
      {!lesson ? (
        <Loading />
      ) : editing ? (
        <div className="stack">
          <p className="muted small">{t("Tu resumen de la lección (listas, **negrita** y fórmulas entre $…$) y/o el enlace a tus apuntes.")}</p>
          <textarea rows={12} maxLength={50000} aria-label={t("Guía de la lección")} value={text} onChange={(e) => setText(e.target.value)} />
          <input aria-label={t("Enlace a tus apuntes")} placeholder={t("https://… u obsidian://…")} value={url} onChange={(e) => setUrl(e.target.value)} />
          {settings?.obsidian_vault && !url && (
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setUrl(obsidianUrl(settings.obsidian_vault, ""))}>
              {t("Empezar enlace a Obsidian")}
            </button>
          )}
          <div className="form-actions">
            <button type="button" className="btn btn--primary" disabled={state.status === "loading"} onClick={() => void save()}>
              {t("Guardar guía")}
            </button>
            <FormStatus state={state} />
          </div>
        </div>
      ) : (
        <div className="stack">
          {lesson.theory.trim() ? <RichText text={lesson.theory} className="lesson-card__body" /> : <p className="muted">{t("Aún no has escrito la guía de esta lección.")}</p>}
          {lesson.theory_url && (
            <a className="btn btn--ghost btn--sm" href={lesson.theory_url} target={lesson.theory_url.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
              {t("📓 Abrir mis apuntes")}
            </a>
          )}
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => setEditing(true)}>
            {t("✏️ Editar guía")}
          </button>
        </div>
      )}
    </Modal>
  );
}
