import { useState } from "react";
import { api, type InboxKind, type InboxMessage } from "../api";
import { DateBadge } from "../components/common";
import { fmtDate } from "../lib/format";
import { useStore } from "../store";
import { Card, Empty, ErrorBox, FormStatus, Loading, PageHeader, useLoad, useSubmit, useUiMode } from "../ui";
import { t } from "../i18n";

const KIND: Record<InboxKind, string> = {
  announcement: t("Anuncio"),
  grade: t("Nota"),
  video_check: t("Vídeo de autoría"),
  forum: t("Foro"),
  deadline: t("Entrega"),
  admin: t("Trámite"),
  other: t("Otro"),
};

const CLASSIFY: Record<InboxMessage["classify_status"], string> = {
  pending: t("Clasificando…"),
  running: t("Clasificando…"),
  done: "",
  error: t("No se pudo clasificar"),
  off: t("Sin clasificar"),
};

function MessageCard({ msg, onChange }: { msg: InboxMessage; onChange: (m: InboxMessage | null) => void }) {
  const { subjects } = useStore();
  const mode = useUiMode();
  const [open, setOpen] = useState(mode === "detailed");
  const { state, run } = useSubmit();
  const subject = subjects.find((s) => s.id === msg.subject_id);
  const pending = msg.proposals.filter((p) => p.state === "pending").length;

  const act = async (action: () => Promise<InboxMessage | void>, message: string) => {
    const res = await run(action, message);
    if (res !== undefined) onChange(res || null);
  };

  const toggleOpen = () => {
    setOpen(!open);
    if (!open && msg.status === "new") void act(() => api.inbox.update(msg.id, { status: "read" }), t("Leído"));
  };

  return (
    <Card
      className={msg.status === "new" ? "inbox-card inbox-card--new" : "inbox-card"}
      title={
        <button type="button" className="link-btn inbox-card__title" aria-expanded={open} onClick={toggleOpen}>
          {msg.status === "new" && <span className="sr-only">{t("Nuevo:")} </span>}
          {msg.title || t("(sin asunto)")}
        </button>
      }
      actions={<span className="muted">{fmtDate(msg.received_at.slice(0, 10))}</span>}
    >
      <p className="inbox-card__meta">
        <span className="tag">{KIND[msg.kind]}</span> {subject ? <span className="tag tag--ok">{subject.name}</span> : null}{" "}
        {pending > 0 && <span className="tag">📅 {pending} {t("fecha")}{pending > 1 ? "s" : ""} {t("por revisar")}</span>}{" "}
        {CLASSIFY[msg.classify_status] && <span className="muted">{CLASSIFY[msg.classify_status]}</span>}
      </p>
      {msg.summary ? <p>{msg.summary}</p> : !open && <p className="muted">{msg.body.slice(0, 180)}{msg.body.length > 180 ? "…" : ""}</p>}

      {msg.proposals.length > 0 && (
        <ul className="inbox-proposals" aria-label={t("Fechas detectadas")}>
          {msg.proposals.map((p, i) => (
            <li key={i} className={`inbox-proposal inbox-proposal--${p.state}`}>
              <DateBadge date={p.date} end={p.end_date} />
              <span className="inbox-proposal__title">
                {p.title}
                {p.time ? ` · ${p.time}` : ""}
              </span>
              {p.state === "pending" ? (
                <span className="inbox-proposal__actions">
                  <button type="button" className="btn btn--primary btn--xs" onClick={() => void act(() => api.inbox.resolve(msg.id, i, "accept"), t("Añadido a la agenda"))}>
                    {t("Añadir a la agenda")}
                  </button>
                  <button type="button" className="btn btn--ghost btn--xs" onClick={() => void act(() => api.inbox.resolve(msg.id, i, "dismiss"), t("Descartado"))}>
                    {t("Descartar")}
                  </button>
                </span>
              ) : (
                <span className="muted">{p.state === "accepted" ? t("✓ En la agenda") : t("Descartada")}</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {open && (
        <>
          <p className="muted inbox-card__from">{t("De:")} {msg.sender}</p>
          <div className="inbox-card__body">{msg.body || t("(sin texto)")}</div>
          {msg.classify_status === "error" && <p className="form-status form-status--error">⚠ {msg.classify_error}</p>}
          <div className="form-actions">
            <label className="inline-label">
              {t("Asignatura")}{" "}
              <select
                className="input-sm"
                value={msg.subject_id ?? ""}
                onChange={(e) =>
                  void act(
                    () => api.inbox.update(msg.id, e.target.value ? { subject_id: Number(e.target.value) } : { clear_subject: true }),
                    t("Guardado")
                  )
                }
              >
                <option value="">{t("— Ninguna —")}</option>
                {subjects
                  .filter((s) => s.status === "enrolled")
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
              </select>
            </label>
            {(msg.classify_status === "error" || msg.classify_status === "off" || msg.classify_status === "done") && (
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => void act(() => api.inbox.classify(msg.id), t("Clasificando"))}>
                {t("Volver a clasificar")}
              </button>
            )}
            {msg.status !== "archived" ? (
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => void act(() => api.inbox.update(msg.id, { status: "archived" }), t("Archivado"))}>
                {t("Archivar")}
              </button>
            ) : (
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => void act(() => api.inbox.update(msg.id, { status: "read" }), t("Recuperado"))}>
                {t("Sacar del archivo")}
              </button>
            )}
          </div>
        </>
      )}
      <FormStatus state={state} />
    </Card>
  );
}

export function InboxPage() {
  const { careers } = useStore();
  const institution = (careers.find((c) => !c.archived) ?? careers[0])?.institution?.trim() ?? "";
  const [view, setView] = useState<"open" | "archived">("open");
  const list = useLoad(() => api.inbox.list(view), [view]);
  const stats = useLoad(() => api.inbox.stats());

  const replace = (id: number, next: InboxMessage | null) => {
    if (!list.data) return;
    const items = next === null || (view === "open" && next.status === "archived") || (view === "archived" && next.status !== "archived")
      ? list.data.filter((m) => m.id !== id)
      : list.data.map((m) => (m.id === id ? next : m));
    list.setData(items);
    void stats.reload();
  };

  return (
    <div className="page">
      <PageHeader
        title={institution ? t("Bandeja · {0}", { 0: institution }) : t("Bandeja de la universidad")}
        subtitle={t("Los correos de la universidad que reenvías a la app. Las fechas que traen no entran en la agenda hasta que las aceptas.")}
      />
      {stats.data && !stats.data.ingest_configured && (
        <div className="banner banner--warn" role="status">
          {t("La entrada de correos no está configurada en el servidor (falta la URL o el token del Worker de la bandeja).")}
        </div>
      )}
      <div className="filters" role="group" aria-label={t("Qué correos ver")}>
        {(["open", "archived"] as const).map((v) => (
          <button key={v} type="button" className={`chip-btn${view === v ? " is-on" : ""}`} aria-pressed={view === v} onClick={() => setView(v)}>
            {v === "open" ? `Bandeja${stats.data?.new ? t(" ({0} nuevos)", { 0: stats.data.new }) : ""}` : t("Archivados")}
          </button>
        ))}
      </div>
      {list.loading && <Loading />}
      {list.error && <ErrorBox message={list.error} onRetry={list.reload} />}
      {list.data && list.data.length === 0 && (
        <Empty icon="📭" title={view === "open" ? t("No hay correos pendientes") : t("No hay correos archivados")}>
          {view === "open" ? t("Cuando llegue un correo reenviado de tu universidad aparecerá aquí.") : null}
        </Empty>
      )}
      {list.data?.map((msg) => (
        <MessageCard key={msg.id} msg={msg} onChange={(next) => replace(msg.id, next)} />
      ))}
    </div>
  );
}
