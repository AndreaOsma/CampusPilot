import { useMemo, useState } from "react";
import { api, type AgendaItem, type CalEvent, type CalEventIn, type EventKind, type Habit } from "../api";
import { AgendaRow } from "../components/common";
import { addDays, EVENT_KIND, fmtDate, todayIso, weekStart, WEEKDAYS, WEEKDAYS_LONG } from "../lib/format";
import type { Navigate } from "../router";
import { useStore } from "../store";
import { Card, ConfirmDelete, Empty, ErrorBox, Field, FormStatus, Loading, Modal, PageHeader, useLoad, useSubmit, useUiMode } from "../ui";
import { t } from "../i18n";

const WEEKS_SHOWN = 8;

function EventForm({ initial, eventId, onSaved }: { initial: CalEventIn; eventId?: number; onSaved: () => void }) {
  const { subjects } = useStore();
  const [form, setForm] = useState<CalEventIn>(initial);
  const { state, run } = useSubmit();
  const set = <K extends keyof CalEventIn>(k: K, v: CalEventIn[K]) => setForm((f) => ({ ...f, [k]: v }));
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await run(() => (eventId ? api.events.update(eventId, form) : api.events.create(form)))) onSaved();
  };
  return (
    <form className="form" onSubmit={submit}>
      <div className="form-grid">
        <Field label={t("Título")} wide>
          {(id) => <input id={id} required maxLength={200} value={form.title} onChange={(e) => set("title", e.target.value)} />}
        </Field>
        <Field label={t("Tipo")}>
          {(id) => (
            <select id={id} value={form.kind} onChange={(e) => set("kind", e.target.value as EventKind)}>
              {Object.entries(EVENT_KIND).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("Asignatura")}>
          {(id) => (
            <select id={id} value={form.subject_id ?? ""} onChange={(e) => set("subject_id", e.target.value ? Number(e.target.value) : null)}>
              <option value="">—</option>
              {subjects
                .filter((s) => s.status === "enrolled" || s.id === form.subject_id)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          )}
        </Field>
        <Field label={t("Día")}>
          {(id) => <input id={id} type="date" required value={form.date} onChange={(e) => set("date", e.target.value)} />}
        </Field>
        <Field label={t("Hasta (opcional)")}>
          {(id) => <input id={id} type="date" value={form.end_date ?? ""} onChange={(e) => set("end_date", e.target.value || null)} />}
        </Field>
        <Field label={t("Desde las")}>
          {(id) => <input id={id} type="time" value={form.start_time ?? ""} onChange={(e) => set("start_time", e.target.value || null)} />}
        </Field>
        <Field label={t("Hasta las")}>
          {(id) => <input id={id} type="time" value={form.end_time ?? ""} onChange={(e) => set("end_time", e.target.value || null)} />}
        </Field>
        <Field label={t("Enlace")} wide>
          {(id) => <input id={id} type="url" maxLength={500} placeholder={t("https://…")} value={form.url} onChange={(e) => set("url", e.target.value)} />}
        </Field>
        <Field label={t("Notas")} wide>
          {(id) => <textarea id={id} rows={2} maxLength={5000} value={form.notes} onChange={(e) => set("notes", e.target.value)} />}
        </Field>
      </div>
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={state.status === "loading"}>
          {t("Guardar")}
        </button>
        <FormStatus state={state} />
      </div>
    </form>
  );
}

function HabitsCard() {
  const { subjects } = useStore();
  const week = weekStart(todayIso());
  const habits = useLoad(() => api.habits.list());
  const checks = useLoad(() => api.habitsWeek(week), [week]);
  const [draft, setDraft] = useState<{ title: string; weekdays: number[] }>({ title: "", weekdays: [] });
  const { state, run } = useSubmit();

  const toggle = async (h: Habit, day: string) => {
    await api.toggleHabit(h.id, day);
    void checks.reload();
  };
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(() => api.habits.create({ title: draft.title, weekdays: draft.weekdays, subject_id: null, active: true }));
    if (ok) {
      setDraft({ title: "", weekdays: [] });
      void habits.reload();
    }
  };

  return (
    <Card title={t("Hábitos")}>
      {habits.error && <ErrorBox message={habits.error} onRetry={habits.reload} />}
      {(habits.data ?? []).length === 0 ? (
        <p className="muted small">{t("Rutinas que se repiten cada semana (la guía semanal del domingo, revisar el tablón…).")}</p>
      ) : (
        <div className="table-wrap">
          <table className="table habit-table">
            <thead>
              <tr>
                <th>{t("Hábito")}</th>
                {WEEKDAYS.map((d, i) => (
                  <th key={i} className="num" title={WEEKDAYS_LONG[i]}>
                    {d}
                  </th>
                ))}
                <th />
              </tr>
            </thead>
            <tbody>
              {(habits.data ?? []).map((h) => (
                <tr key={h.id} className={h.active ? "" : "muted"}>
                  <td>
                    {h.title}
                    {h.subject_id && <div className="muted small">{subjects.find((s) => s.id === h.subject_id)?.name}</div>}
                  </td>
                  {WEEKDAYS.map((d, i) => {
                    const day = addDays(week, i);
                    const due = h.weekdays.includes(i);
                    const done = (checks.data?.checks[h.id] ?? []).includes(day);
                    return (
                      <td key={d} className="num">
                        {due ? (
                          <input
                            type="checkbox"
                            checked={done}
                            aria-label={`${h.title}, ${WEEKDAYS_LONG[i]}`}
                            onChange={() => void toggle(h, day)}
                          />
                        ) : (
                          <span className="muted" aria-hidden>
                            ·
                          </span>
                        )}
                      </td>
                    );
                  })}
                  <td>
                    <ConfirmDelete label="✕" onConfirm={() => void api.habits.remove(h.id).then(habits.reload)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form className="inline-form" onSubmit={add}>
        <input aria-label={t("Nuevo hábito")} placeholder={t("Nuevo hábito")} required maxLength={200} value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
        <div className="weekday-picker" role="group" aria-label={t("Días")}>
          {WEEKDAYS.map((d, i) => (
            <button
              key={i}
              type="button"
              className={draft.weekdays.includes(i) ? "is-active" : ""}
              aria-pressed={draft.weekdays.includes(i)}
              aria-label={WEEKDAYS_LONG[i]}
              onClick={() =>
                setDraft({ ...draft, weekdays: draft.weekdays.includes(i) ? draft.weekdays.filter((x) => x !== i) : [...draft.weekdays, i] })
              }
            >
              {d}
            </button>
          ))}
        </div>
        <button type="submit" className="btn btn--ghost btn--sm" disabled={!draft.weekdays.length}>
          {t("+ Hábito")}
        </button>
      </form>
      <FormStatus state={state} />
    </Card>
  );
}

export function Semester({ navigate }: { navigate: Navigate }) {
  const { currentTerm } = useStore();
  const mode = useUiMode();
  const [start, setStart] = useState(() => weekStart(todayIso()));
  const [wholeTerm, setWholeTerm] = useState(false);
  const range = useMemo(() => {
    if (wholeTerm && currentTerm) return { start: weekStart(currentTerm.start_date), end: currentTerm.end_date ?? addDays(currentTerm.start_date, 150) };
    return { start, end: addDays(start, WEEKS_SHOWN * 7 - 1) };
  }, [start, wholeTerm, currentTerm]);
  const agenda = useLoad(() => api.agenda(range.start, range.end), [range.start, range.end]);
  const ical = useLoad(() => api.icalStatus());
  const [modal, setModal] = useState<null | "new" | { event: CalEvent }>(null);

  const weeks = useMemo(() => {
    const out: { week: string; items: AgendaItem[] }[] = [];
    if (!agenda.data) return out;
    for (let w = range.start; w <= range.end; w = addDays(w, 7)) {
      const end = addDays(w, 6);
      out.push({
        week: w,
        items: agenda.data.items.filter((i) =>
          i.type === "window" ? i.date <= end && (i.end_date ?? i.date) >= w && (i.date >= w || w === range.start) : i.date >= w && i.date <= end
        ),
      });
    }
    return out;
  }, [agenda.data, range]);
  const heavy = new Map((agenda.data?.heavy_weeks ?? []).map((h) => [h.week, h.subjects]));
  const thisWeek = weekStart(todayIso());

  const openItem = async (it: AgendaItem) => {
    if (it.type === "event") setModal({ event: await api.events.get(it.id) });
    else if ((it.type === "activity" || it.type === "window") && it.subject_id) navigate({ name: "subject", id: it.subject_id });
  };

  return (
    <div className="page">
      <PageHeader
        title={t("Semestre")}
        subtitle={currentTerm ? `${currentTerm.label} · ${fmtDate(currentTerm.start_date)} – ${fmtDate(currentTerm.end_date)}` : undefined}
        actions={
          <button type="button" className="btn btn--primary" onClick={() => setModal("new")}>
            {t("+ Evento")}
          </button>
        }
      />

      <div className="toolbar">
        <button type="button" className="btn btn--ghost btn--sm" disabled={wholeTerm} onClick={() => setStart(addDays(start, -28))}>
          {t("← 4 semanas")}
        </button>
        <button type="button" className="btn btn--ghost btn--sm" disabled={wholeTerm} onClick={() => setStart(thisWeek)}>
          {t("Hoy")}
        </button>
        <button type="button" className="btn btn--ghost btn--sm" disabled={wholeTerm} onClick={() => setStart(addDays(start, 28))}>
          {t("4 semanas →")}
        </button>
        {currentTerm && (
          <label className="check">
            <input type="checkbox" checked={wholeTerm} onChange={(e) => setWholeTerm(e.target.checked)} /> {t("Todo el semestre")}
          </label>
        )}
      </div>

      {agenda.loading ? (
        <Loading />
      ) : agenda.error ? (
        <ErrorBox message={agenda.error} onRetry={agenda.reload} />
      ) : (
        <div className="weeks">
          {weeks.map(({ week, items }) => {
            const isHeavy = heavy.get(week);
            if (!items.length && mode === "minimal" && week !== thisWeek) return null;
            return (
              <section key={week} className={`week${week === thisWeek ? " is-current" : ""}${isHeavy ? " is-heavy" : ""}`}>
                <h2 className="week__title">
                  {isHeavy && (
                    <span className="week__heavy" title={t("Semana cargada: {0}", { 0: isHeavy.join(", ") })}>
                      ▲
                    </span>
                  )}
                  {t("Semana del")} {fmtDate(week)}
                  {week === thisWeek && <span className="tag">{t("esta semana")}</span>}
                </h2>
                {items.length === 0 ? (
                  <p className="muted small">{t("Sin entregas ni eventos.")}</p>
                ) : (
                  <ul className="agenda-list">
                    {items.map((it) => (
                      <AgendaRow key={it.uid} item={it} onOpen={() => void openItem(it)} />
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
          {weeks.every((w) => !w.items.length) && <Empty icon="🗓️" title={t("Nada en estas semanas")} />}
        </div>
      )}

      <HabitsCard />

      <Card title={t("Calendario en tu app")} className="detail-only">
        <p className="small">
          <a className="btn btn--ghost btn--sm" href={api.calendarUrl} download="campus-pilot.ics">
            {t("⬇ Descargar .ics")}
          </a>{" "}
          {ical.data?.configured && ical.data.path ? (
            <>
              {t("o suscríbete (se actualiza solo):")}{" "}
              <code className="mono break">{`${window.location.origin}${ical.data.path}`}</code>
            </>
          ) : (
            <span className="muted">{t("Para suscribirte sin pasar por el inicio de sesión, el servidor necesita CAMPUS_ICAL_TOKEN.")}</span>
          )}
        </p>
      </Card>

      <Modal open={modal === "new"} title={t("Nuevo evento")} onClose={() => setModal(null)}>
        <EventForm
          initial={{ subject_id: null, title: "", kind: "other", date: todayIso(), end_date: null, start_time: null, end_time: null, url: "", notes: "", done: false }}
          onSaved={() => {
            setModal(null);
            void agenda.reload();
          }}
        />
      </Modal>
      <Modal open={typeof modal === "object" && modal !== null} title={t("Evento")} onClose={() => setModal(null)}>
        {typeof modal === "object" && modal !== null && (
          <>
            <EventForm
              initial={modal.event}
              eventId={modal.event.id}
              onSaved={() => {
                setModal(null);
                void agenda.reload();
              }}
            />
            <ConfirmDelete
              label={t("Borrar evento")}
              onConfirm={() =>
                void api.events.remove(modal.event.id).then(() => {
                  setModal(null);
                  void agenda.reload();
                })
              }
            />
          </>
        )}
      </Modal>
    </div>
  );
}
