import { useState } from "react";
import { api, type InboxKind, type InboxMessage } from "../api";
import { DateBadge } from "../components/common";
import { fmtDate } from "../lib/format";
import { useStore } from "../store";
import { Card, Empty, ErrorBox, Field, FormStatus, Loading, PageHeader, useLoad, useSubmit, useUiMode } from "../ui";
import { t } from "../i18n";
import { Calendar, Check, Icon, Mailbox, Plus, TriangleAlert } from "../vendor/icons";

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
        {pending > 0 && <span className="tag"><Icon svg={Calendar} /> {pending} {t("fecha")}{pending > 1 ? "s" : ""} {t("por revisar")}</span>}{" "}
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
                <span className="muted">{p.state === "accepted" ? <><Icon svg={Check} /> {t("En la agenda")}</> : t("Descartada")}</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {open && (
        <>
          <p className="muted inbox-card__from">{t("De:")} {msg.sender}</p>
          <div className="inbox-card__body">{msg.body || t("(sin texto)")}</div>
          {msg.classify_status === "error" && <p className="form-status form-status--error"><Icon svg={TriangleAlert} /> {msg.classify_error}</p>}
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

/** Añadir un correo pegando su texto (para quien no reenvía los correos a la app). */
function PasteCard({ onAdded, open, setOpen }: { onAdded: (m: InboxMessage) => void; open: boolean; setOpen: (v: boolean) => void }) {
  const [form, setForm] = useState({ subject: "", sender: "", text: "" });
  const { state, run } = useSubmit();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await run(() => api.inbox.paste(form), t("Correo añadido: la IA lo está leyendo"));
    if (res) {
      setForm({ subject: "", sender: "", text: "" });
      onAdded(res);
    }
  };
  if (!open) return null;
  return (
    <Card title={t("Añadir un correo")}>
      <p className="muted small">
        {t("Abre el correo de tu universidad, copia su texto y pégalo aquí. En el móvil, en Gmail: mantén pulsado el texto del correo → «Seleccionar todo» → «Copiar». La app lo lee, te dice de qué asignatura es y te propone las fechas que traiga.")}
      </p>
      <form className="form" onSubmit={submit}>
        <div className="form-grid">
          <Field label={t("Asunto")}>{(id) => <input id={id} value={form.subject} maxLength={500} onChange={(e) => setForm({ ...form, subject: e.target.value })} />}</Field>
          <Field label={t("De (opcional)")}>{(id) => <input id={id} type="email" autoComplete="off" value={form.sender} maxLength={320} onChange={(e) => setForm({ ...form, sender: e.target.value })} />}</Field>
          <Field label={t("Texto del correo")} wide>
            {(id) => <textarea id={id} rows={8} required value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />}
          </Field>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={!form.text.trim() || state.status === "loading"}>
            {state.status === "loading" ? t("Añadiendo…") : t("Añadir a la bandeja")}
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => setOpen(false)}>{t("Cerrar")}</button>
          <FormStatus state={state} />
        </div>
      </form>
    </Card>
  );
}

export function InboxPage() {
  const { careers } = useStore();
  const institution = (careers.find((c) => !c.archived) ?? careers[0])?.institution?.trim() ?? "";
  const [view, setView] = useState<"open" | "archived">("open");
  const list = useLoad(() => api.inbox.list(view), [view]);
  const stats = useLoad(() => api.inbox.stats());
  const [pasting, setPasting] = useState(false);

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
      <div className="form-actions">
        <button type="button" className="btn btn--primary" aria-expanded={pasting} onClick={() => setPasting(!pasting)}>
          <Icon svg={Plus} /> {t("Añadir correo")}
        </button>
      </div>
      {stats.data && !stats.data.ingest_configured && !pasting && (
        <p className="muted small">
          {t("Pega aquí los correos de tu universidad con «Añadir correo». (Si quien instala la app configura el reenvío automático, también llegan solos.)")}
        </p>
      )}
      <PasteCard
        open={pasting}
        setOpen={setPasting}
        onAdded={(m) => {
          setPasting(false);
          if (view === "open") list.setData([m, ...(list.data ?? []).filter((x) => x.id !== m.id)]);
          void stats.reload();
        }}
      />
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
        <Empty icon={Mailbox} title={view === "open" ? t("No hay correos pendientes") : t("No hay correos archivados")}>
          {view === "open" ? t("Pulsa «Añadir correo» y pega uno de tu universidad: aparecerá aquí con sus fechas propuestas.") : null}
        </Empty>
      )}
      {list.data?.map((msg) => (
        <MessageCard key={msg.id} msg={msg} onChange={(next) => replace(msg.id, next)} />
      ))}
    </div>
  );
}
