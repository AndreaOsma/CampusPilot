import { useState } from "react";
import { api, type CalendarFeed } from "../api";
import { useStore } from "../store";
import { Card, ConfirmDelete, Field, FormStatus, useLoad, useSubmit } from "../ui";
import { t } from "../i18n";

const MODE: Record<CalendarFeed["mode"], string> = {
  events: t("Como eventos de la agenda"),
  activities: t("Como entregas (cuentan en el expediente)"),
};

/** Ajustes: enlaces iCal del campus virtual (Moodle, Canvas, Blackboard…) que llenan la agenda. */
export function CalendarFeedsCard() {
  const { subjects } = useStore();
  const feeds = useLoad(() => api.calendarFeeds.list());
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<CalendarFeed["mode"]>("events");
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const { state, run } = useSubmit();
  const enrolled = subjects.filter((s) => s.status === "enrolled" || s.status === "pending");

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await run(() => api.calendarFeeds.create({ url, mode, subject_id: subjectId, name: "", enabled: true }), t("Calendario conectado"));
    if (res) {
      setUrl("");
      void feeds.reload();
    }
  };
  const syncNow = (id: number) => run(() => api.calendarFeeds.sync(id), t("Sincronizado")).then(() => feeds.reload());

  return (
    <Card title={t("Calendario de la universidad")}>
      <p className="muted small">
        {t("Pega el enlace iCal de tu campus virtual (en Moodle: Calendario → Exportar calendario → copiar URL; en Canvas: Calendario → Fuente del calendario) y las entregas y exámenes entran solos en la agenda, actualizándose cada 3 horas. La asignatura se reconoce por su código o su nombre.")}
      </p>
      {(feeds.data ?? []).length > 0 && (
        <ul className="row-list">
          {(feeds.data ?? []).map((f) => (
            <li key={f.id} className="row-list__item">
              <div>
                <strong>{f.name}</strong> <span className="muted small">{f.url_hint}</span>
                <div className={`small ${f.last_error ? "text-crit" : "muted"}`}>
                  {MODE[f.mode]} · {t("{0} entradas", { 0: f.items })}
                  {f.last_error && ` · ${f.last_error}`}
                </div>
              </div>
              <span className="row-actions">
                <button type="button" className="btn btn--ghost btn--sm" onClick={() => void syncNow(f.id)} disabled={state.status === "loading"}>
                  {t("↻ Sincronizar")}
                </button>
                <ConfirmDelete label="✕" onConfirm={() => void api.calendarFeeds.remove(f.id).then(feeds.reload)} />
              </span>
            </li>
          ))}
        </ul>
      )}
      <form className="form" onSubmit={add}>
        <div className="form-grid">
          <Field label={t("Enlace iCal")} wide>
            {(id) => <input id={id} type="url" required placeholder="https://… o webcal://…" maxLength={1000} value={url} onChange={(e) => setUrl(e.target.value)} />}
          </Field>
          <Field label={t("Entran")}>
            {(id) => (
              <select id={id} value={mode} onChange={(e) => setMode(e.target.value as CalendarFeed["mode"])}>
                {Object.entries(MODE).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={t("Si no se reconoce la asignatura")}>
            {(id) => (
              <select id={id} value={subjectId ?? ""} onChange={(e) => setSubjectId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">{mode === "activities" ? t("No importarla") : t("Sin asignatura")}</option>
                {enrolled.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={!url.trim() || state.status === "loading"}>
            {t("Conectar calendario")}
          </button>
          <FormStatus state={state} />
        </div>
      </form>
    </Card>
  );
}
