import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Card as CardT } from "../api";
import { fmtDate, fmtMinutes, todayIso } from "../lib/format";
import { MathText } from "../lib/math";
import { useStore } from "../store";
import { Card, ConfirmDelete, Empty, ErrorBox, Field, FormStatus, Loading, PageHeader, ProgressBar, useLoad, useSubmit, useUiMode } from "../ui";
import { t } from "../i18n";

type Timer = { subjectId: number | null; goalMin: number; startedAt: number | null; accumulatedMs: number };
const TIMER_KEY = "campus-focus";

function loadTimer(): Timer {
  try {
    const raw = localStorage.getItem(TIMER_KEY);
    if (raw) return JSON.parse(raw) as Timer;
  } catch {
    /* sin almacenamiento: el temporizador vive solo en memoria */
  }
  return { subjectId: null, goalMin: 25, startedAt: null, accumulatedMs: 0 };
}

function FocusTimer({ onSaved }: { onSaved: () => void }) {
  const { subjects } = useStore();
  const enrolled = subjects.filter((s) => s.status === "enrolled");
  const [timer, setTimer] = useState<Timer>(loadTimer);
  const [now, setNow] = useState(Date.now());
  const { state, run } = useSubmit();
  const notified = useRef(false);

  useEffect(() => {
    try {
      localStorage.setItem(TIMER_KEY, JSON.stringify(timer));
    } catch {
      /* ignorar */
    }
  }, [timer]);

  useEffect(() => {
    if (!timer.startedAt) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [timer.startedAt]);

  // Basado en marcas de tiempo, no en ticks: sigue bien aunque la pestaña se duerma.
  const elapsedMs = timer.accumulatedMs + (timer.startedAt ? now - timer.startedAt : 0);
  const remainingMs = Math.max(0, timer.goalMin * 60_000 - elapsedMs);
  const running = timer.startedAt !== null;
  const mm = String(Math.floor(remainingMs / 60_000)).padStart(2, "0");
  const ss = String(Math.floor((remainingMs % 60_000) / 1000)).padStart(2, "0");

  useEffect(() => {
    if (running && remainingMs === 0 && !notified.current) {
      notified.current = true;
      document.title = t("⏰ Focus terminado · Campus Pilot");
    }
    if (remainingMs > 0) notified.current = false;
  }, [running, remainingMs]);

  const start = () => setTimer((t) => ({ ...t, startedAt: Date.now() }));
  const pause = () => setTimer((t) => ({ ...t, startedAt: null, accumulatedMs: elapsedMs }));
  const reset = () => {
    document.title = t("Campus Pilot");
    setTimer((t) => ({ ...t, startedAt: null, accumulatedMs: 0 }));
  };
  const save = async () => {
    const minutes = Math.round(elapsedMs / 60_000);
    if (minutes < 1) return;
    const ok = await run(
      () => api.sessions.create({ subject_id: timer.subjectId, date: todayIso(), minutes, kind: "focus", note: "" }),
      t("Guardados {0}", { 0: fmtMinutes(minutes) })
    );
    if (ok) {
      reset();
      onSaved();
    }
  };

  return (
    <Card title={t("Focus")}>
      <div className="focus">
        <div className="focus__ring" data-empty={elapsedMs === 0 ? "" : undefined} style={{ ["--p" as string]: String(Math.min(1, elapsedMs / (timer.goalMin * 60_000))) }}>
          <svg viewBox="0 0 120 120" aria-hidden>
            <circle className="focus__track" cx="60" cy="60" r="52" />
            <circle className="focus__progress" cx="60" cy="60" r="52" pathLength="100" />
          </svg>
          <div className="focus__clock" role="timer" aria-live="off" aria-label={t("Quedan {0} minutos y {1} segundos", { 0: mm, 1: ss })}>
            {mm}:{ss}
          </div>
        </div>
        <div className="segmented focus__presets" role="group" aria-label={t("Duración del bloque")}>
          {[25, 45, 50, 90].map((m) => (
            <button key={m} type="button" disabled={running} className={timer.goalMin === m ? "is-active" : ""} aria-pressed={timer.goalMin === m}
              onClick={() => setTimer({ ...timer, goalMin: m })}>
              {m} {t("min")}
            </button>
          ))}
        </div>
        <Field label={t("Asignatura")}>
          {(id) => (
            <select id={id} value={timer.subjectId ?? ""} onChange={(e) => setTimer({ ...timer, subjectId: e.target.value ? Number(e.target.value) : null })}>
              <option value="">{t("— General")}</option>
              {enrolled.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <div className="form-actions">
          {running ? (
            <button type="button" className="btn btn--primary" onClick={pause}>
              {t("⏸ Pausa")}
            </button>
          ) : (
            <button type="button" className="btn btn--primary" onClick={start}>
              ▶ {elapsedMs > 0 ? t("Seguir") : t("Empezar")}
            </button>
          )}
          <button type="button" className="btn btn--ghost" disabled={elapsedMs < 60_000} onClick={() => void save()}>
            {t("Guardar")} {elapsedMs >= 60_000 ? fmtMinutes(Math.round(elapsedMs / 60_000)) : ""}
          </button>
          <button type="button" className="btn btn--ghost" disabled={elapsedMs === 0} onClick={reset}>
            {t("Reiniciar")}
          </button>
          <FormStatus state={state} />
        </div>
      </div>
    </Card>
  );
}

function ManualSession({ onSaved }: { onSaved: () => void }) {
  const { subjects } = useStore();
  const [form, setForm] = useState({ subject_id: null as number | null, date: todayIso(), minutes: 60, note: "" });
  const { state, run } = useSubmit();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await run(() => api.sessions.create({ ...form, kind: "manual" }))) onSaved();
  };
  return (
    <form className="form" onSubmit={submit}>
      <div className="form-grid">
        <Field label={t("Asignatura")}>
          {(id) => (
            <select id={id} value={form.subject_id ?? ""} onChange={(e) => setForm({ ...form, subject_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">{t("— General")}</option>
              {subjects
                .filter((s) => s.status === "enrolled")
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          )}
        </Field>
        <Field label={t("Día")}>
          {(id) => <input id={id} type="date" required value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />}
        </Field>
        <Field label={t("Minutos")}>
          {(id) => <input id={id} type="number" min={1} max={1440} required value={form.minutes} onChange={(e) => setForm({ ...form, minutes: Number(e.target.value) })} />}
        </Field>
        <Field label={t("Qué hiciste")} wide>
          {(id) => <input id={id} maxLength={300} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />}
        </Field>
      </div>
      <div className="form-actions">
        <button type="submit" className="btn btn--ghost" disabled={state.status === "loading"}>
          {t("+ Sesión")}
        </button>
        <FormStatus state={state} />
      </div>
    </form>
  );
}

function Review({ onChange }: { onChange: () => void }) {
  const { subjectName } = useStore();
  const due = useLoad(() => api.dueCards());
  const [index, setIndex] = useState(0);
  const [done, setDone] = useState(0);
  const cards = due.data ?? [];
  const card: CardT | undefined = cards[index];

  const answer = async (knew: boolean) => {
    if (!card) return;
    await api.reviewCard(card.id, knew);
    setDone((d) => d + 1);
    setIndex((i) => i + 1);
    onChange();
  };

  if (due.loading) return <Loading />;
  if (due.error) return <ErrorBox message={due.error} onRetry={due.reload} />;
  if (!card)
    return (
      <Empty icon="🧠" title={done ? t("¡Hecho! {0} pregunta{1} repasada{2}", { 0: done, 1: done > 1 ? "s" : "", 2: done > 1 ? "s" : "" }) : t("Nada que repasar hoy")}>
        {done > 0 && (
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => (setIndex(0), setDone(0), void due.reload())}>
            {t("Buscar más")}
          </button>
        )}
      </Empty>
    );

  return (
    <div className="review">
      <p className="muted small">
        {index + 1} {t("de")} {cards.length} · {card.deck || t("Sin mazo")}
        {card.subject_id && ` · ${subjectName(card.subject_id)}`} {t("· caja")} {card.box}
      </p>
      <p className="review__question">
        <MathText text={card.question} />
      </p>
      <p className="muted small">{t("Respóndela en voz alta o en papel, sin mirar. Luego evalúate con sinceridad:")}</p>
      <div className="form-actions">
        <button type="button" className="btn btn--primary" onClick={() => void answer(true)}>
          {t("✓ La sabía")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={() => void answer(false)}>
          {t("✗ No / a medias")}
        </button>
      </div>
    </div>
  );
}

function ImportCards({ onImported }: { onImported: () => void }) {
  const { subjects } = useStore();
  const [form, setForm] = useState({ subject_id: null as number | null, deck: "", source: "", markdown: "" });
  const { state, run } = useSubmit();
  const onFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 200_000) return;
    setForm((f) => ({ ...f, markdown: "", source: f.source || file.name }));
    const text = await file.text();
    setForm((f) => ({ ...f, markdown: text }));
  };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await run(() => api.importCards(form), t("Importadas"));
    if (res) {
      setForm({ ...form, markdown: "", deck: "" });
      onImported();
    }
  };
  return (
    <form className="form" onSubmit={submit}>
      <p className="muted small detail-only">
        {t("Cada elemento de lista (")}<code>1.</code>, <code>-</code>{t(") es una pregunta; el primer")} <code>{t("# título")}</code> {t("da nombre al mazo. Las fórmulas")}{" "}
        <code>$…$</code> {t("se ven bien. Solo preguntas: las respuestas las das tú.")}
      </p>
      <div className="form-grid">
        <Field label={t("Archivo .md")}>
          {(id) => <input id={id} type="file" accept=".md,text/markdown,text/plain" onChange={(e) => void onFile(e.target.files?.[0])} />}
        </Field>
        <Field label={t("Asignatura")}>
          {(id) => (
            <select id={id} value={form.subject_id ?? ""} onChange={(e) => setForm({ ...form, subject_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">—</option>
              {subjects
                .filter((s) => s.status === "enrolled")
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          )}
        </Field>
        <Field label={t("Mazo")} hint={t("Vacío = el título del archivo")}>
          {(id) => <input id={id} maxLength={160} value={form.deck} onChange={(e) => setForm({ ...form, deck: e.target.value })} />}
        </Field>
        <Field label={t("O pega el texto")} wide>
          {(id) => <textarea id={id} rows={5} required maxLength={200_000} value={form.markdown} onChange={(e) => setForm({ ...form, markdown: e.target.value })} />}
        </Field>
      </div>
      <div className="form-actions">
        <button type="submit" className="btn btn--ghost" disabled={state.status === "loading" || !form.markdown.trim()}>
          {t("Importar preguntas")}
        </button>
        <FormStatus state={state} />
      </div>
    </form>
  );
}

function Decks({ version }: { version: number }) {
  const cards = useLoad(() => api.cards.list(), [version]);
  const decks = useMemo(() => {
    const map = new Map<string, CardT[]>();
    for (const c of cards.data ?? []) map.set(c.deck || t("Sin mazo"), [...(map.get(c.deck || t("Sin mazo")) ?? []), c]);
    return [...map.entries()];
  }, [cards.data]);
  if (!decks.length) return null;
  return (
    <div className="stack">
      {decks.map(([deck, list]) => (
        <details key={deck} className="details">
          <summary>
            {deck} <span className="muted small">· {list.length} {t("preguntas ·")} {list.filter((c) => c.box >= 4).length} {t("bien asentadas")}</span>
          </summary>
          <ul className="plain-list">
            {list.map((c) => (
              <li key={c.id} className="deck-card">
                <span>
                  <MathText text={c.question} />
                </span>
                <span className="muted small">
                  {t("caja")} {c.box} · {fmtDate(c.due_on)}
                </span>
                <ConfirmDelete label="✕" onConfirm={() => void api.cards.remove(c.id).then(cards.reload)} />
              </li>
            ))}
          </ul>
        </details>
      ))}
    </div>
  );
}

export function Study() {
  const mode = useUiMode();
  const stats = useLoad(() => api.studyStats());
  const hasCards = useLoad(() => api.cards.list({ limit: 1 }));
  const [version, setVersion] = useState(0);
  const bump = () => {
    setVersion((v) => v + 1);
    void stats.reload();
  };

  return (
    <div className="page">
      <PageHeader title={t("Estudio")} />
      <div className="grid-2">
        <FocusTimer onSaved={bump} />
        <Card title={t("Repaso de hoy")}>
          <Review key={version} onChange={() => undefined} />
        </Card>
      </div>

      <Card title={t("Horas de las últimas 4 semanas")}>
        {stats.loading ? (
          <Loading />
        ) : stats.error ? (
          <ErrorBox message={stats.error} onRetry={stats.reload} />
        ) : !stats.data?.by_subject.length ? (
          <Empty icon="⏱️" title={t("Aún no hay sesiones")}>
            {t("Usa el focus o apunta sesiones a mano; si pones horas/semana previstas en cada asignatura verás si vas al día.")}
          </Empty>
        ) : (
          <ul className="hours-list">
            {stats.data.by_subject.map((r) => (
              <li key={r.subject_id ?? "none"}>
                <div className="hours-list__head">
                  <span>{r.subject_name}</span>
                  <span className="muted small">
                    {fmtMinutes(r.minutes)}
                    {r.expected_minutes ? t(" de {0} previstas", { 0: fmtMinutes(r.expected_minutes) }) : ""}
                  </span>
                </div>
                {r.expected_minutes ? <ProgressBar value={r.minutes} max={r.expected_minutes} label={t("Horas de {0}", { 0: r.subject_name })} /> : null}
              </li>
            ))}
          </ul>
        )}
        <details className="details" open={mode === "detailed"}>
          <summary>{t("Apuntar una sesión a mano")}</summary>
          <ManualSession onSaved={bump} />
        </details>
      </Card>

      <Card title={t("Preguntas de repaso")}>
        <Decks version={version} />
        <details className="details" open={!hasCards.data?.length}>
          <summary>{t("Importar preguntas")}</summary>
          <ImportCards onImported={bump} />
        </details>
      </Card>
    </div>
  );
}
