import { api, type Dashboard as DashboardT } from "../api";
import { AgendaRow, AiBadge, EvalLine, NoAiPill } from "../components/common";
import { daysBetween, fmtDate, fmtGrade, fmtMinutes, fmtWeekday, subjectStyle, todayIso, weekStart } from "../lib/format";
import { linkTo, type Navigate, type Route } from "../router";
import { rulesOf } from "../lib/rules";
import { Onboarding } from "../components/Onboarding";
import "../vendor/learn-game/learn-game.css";
import { useStore } from "../store";
import { Card, Empty, ErrorBox, Loading, PageHeader, ProgressBar, useLoad, useUiMode } from "../ui";
import { t } from "../i18n";

export function Dashboard({ navigate }: { navigate: Navigate }) {
  const { settings, careers, loading: storeLoading } = useStore();
  const { data, error, loading, reload, setData } = useLoad(() => api.dashboard());
  const mode = useUiMode();

  if (storeLoading || loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  if (careers.length === 0) return <Onboarding navigate={navigate} />;

  const today = todayIso();
  const thisWeek = weekStart(today);
  const heavyNow = data.heavy_weeks.find((w) => w.week === thisWeek);
  const heavyNext = data.heavy_weeks.find((w) => w.week > thisWeek);
  const upcoming = mode === "minimal" ? data.upcoming.slice(0, 6) : data.upcoming;
  const semestre = settings?.modules.semestre !== false;
  const estudio = settings?.modules.estudio !== false;
  const aprender = settings?.modules.aprender !== false;

  const toggleHabit = async (id: number) => {
    const res = await api.toggleHabit(id);
    setData({ ...data, habits_today: data.habits_today.map((h) => (h.id === id ? { ...h, done: res.done } : h)) });
  };

  const markDone = async (activityId: number) => {
    const a = await api.activities.get(activityId);
    await api.activities.update(activityId, { ...a, done: true });
    void reload();
  };

  const next = data.upcoming.find((i) => i.type === "activity" && i.evaluable);
  const nextDays = next ? daysBetween(today, next.date) : null;
  const rest = upcoming.filter((i) => i.uid !== next?.uid);

  return (
    <div className="page">
      <PageHeader title={t("Hoy")} subtitle={fmtDate(today, true)} />

      {heavyNow && (
        <div className="banner banner--warn" role="status">
          <strong>{t("▲ Semana cargada")}</strong>{t(": entregas de")} {heavyNow.subjects.join(" y ")}.
        </div>
      )}

      {semestre && next && nextDays !== null && (
        <section className="hero-next" style={subjectStyle(next.subject_id)} aria-label={t("Lo siguiente")}>
          <div className="hero-next__count">
            <span className="hero-next__num">{nextDays <= 0 ? t("Hoy") : nextDays}</span>
            {nextDays > 0 && <span className="hero-next__unit">{nextDays === 1 ? t("día") : t("días")}</span>}
          </div>
          <div className="hero-next__body">
            <span className="hero-next__kicker">{t("Lo siguiente")}</span>
            <span className="hero-next__title">
              {next.title} {next.ai_forbidden && <NoAiPill />}
            </span>
            <span className="hero-next__meta">
              {next.subject_name && (
                <a className="subj-chip" href={`/asignaturas/${next.subject_id}`} onClick={linkTo(navigate, { name: "subject", id: next.subject_id! })}>
                  {next.subject_name}
                </a>
              )}{" "}
              {fmtWeekday(next.date)}
              {next.time && ` · ${next.time}`}
            </span>
          </div>
        </section>
      )}

      <TodayPlan plan={data.today_plan} navigate={navigate} />

      {aprender && (data.next_lessons.length > 0 || data.learn.streak > 0) && (
        <section className="learn-strip" aria-label={t("Aprender")}>
          <span className={`learn-strip__streak${data.learn.streak ? " is-on" : ""}`} title={t("Días de racha")}>
            🔥 {data.learn.streak}
          </span>
          <span className="learn-strip__goal" title={t("XP de hoy")}>
            <ProgressBar value={Math.min(data.learn.today_xp, data.learn.goal)} max={data.learn.goal} label={t("Meta diaria de XP")} />
            <span className="small muted">
              {data.learn.today_xp}/{data.learn.goal} {t("XP")}
            </span>
          </span>
          <span className="learn-strip__lessons">
            {data.next_lessons.slice(0, mode === "minimal" ? 2 : 4).map((l) => (
              <a key={l.lesson_id} className="chip-link" style={subjectStyle(l.subject_id)} href={`/aprender/leccion/${l.lesson_id}`}
                onClick={linkTo(navigate, { name: "lesson", id: l.lesson_id })}>
                ▶ {l.subject_name}
              </a>
            ))}
          </span>
        </section>
      )}

      {data.at_risk.length > 0 && (
        <Card title={t("En riesgo")} className="risk-card">
          <ul className="risk-list">
            {data.at_risk.map((r) => (
              <li key={r.id} className={`risk-list__item is-${r.level}`}>
                <a href={`/asignaturas/${r.id}`} onClick={linkTo(navigate, { name: "subject", id: r.id })}>
                  {r.level === "crit" ? "⛔" : "⚠️"} {r.name}
                </a>
                <span className="small muted">{r.reason}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="stat-row">
        {data.careers.map((c) => {
          const credits = rulesOf(careers.find((x) => x.id === c.career_id)).credit_label;
          return (
          <div className="stat" key={c.career_id}>
            <span className="stat__label">{credits} {t("superados")}</span>
            <span className="stat__value">
              {c.ects_done}
              <small className="muted"> / {c.ects_goal} {credits}</small>
            </span>
            <ProgressBar value={c.ects_done} max={c.ects_goal} label={t("{0} superados de {1}", { 0: credits, 1: c.name })} />
            <span className="muted small truncate" title={c.name}>
              {c.average !== null ? t("Media {0} · ", { 0: fmtGrade(c.average) }) : ""}
              {c.name}
            </span>
          </div>
          );
        })}
        {estudio && (
          <a className="stat stat--link" href="/estudio" onClick={linkTo(navigate, { name: "study" })}>
            <span className="stat__label">{t("Estudio esta semana")}</span>
            <span className="stat__value">{fmtMinutes(data.study_minutes_week)}</span>
            {data.cards_due > 0 && <span className="small">🧠 {data.cards_due} {t("preguntas para repasar")}</span>}
          </a>
        )}
        {data.inbox_pending && data.inbox_pending.new + data.inbox_pending.proposals > 0 && (
          <a className="stat stat--link" href="/bandeja" onClick={linkTo(navigate, { name: "inbox" })}>
            <span className="stat__label">{t("Bandeja")}</span>
            <span className="stat__value">{data.inbox_pending.new}</span>
            <span className="small">
              {data.inbox_pending.new === 1 ? t("correo nuevo") : t("correos nuevos")}
              {data.inbox_pending.proposals > 0 && t(" · {0} fechas por revisar", { 0: data.inbox_pending.proposals })}
            </span>
          </a>
        )}
        {data.next_exam && (
          <div className="stat detail-only" style={subjectStyle(data.next_exam.subject_id)}>
            <span className="stat__label">{t("Próximo examen")}</span>
            <span className="stat__value">{daysBetween(today, data.next_exam.date) <= 0 ? t("Hoy") : `${daysBetween(today, data.next_exam.date)} d`}</span>
            <span className="small truncate" title={data.next_exam.title}>
              {data.next_exam.title} · {fmtWeekday(data.next_exam.date)}
            </span>
          </div>
        )}
      </div>

      {semestre && <WeekLoad weeks={data.week_load} heavy={data.heavy_weeks.map((w) => w.week)} />}

      <div className="grid-2">
        {semestre && (
          <Card
            title={t("Próximo")}
            actions={
              <a className="btn btn--ghost btn--sm" href="/semestre" onClick={linkTo(navigate, { name: "semester" })}>
                {t("Ver semestre")}
              </a>
            }
          >
            {data.overdue.length > 0 && (
              <div className="banner banner--crit small">
                <strong>{t("⚠ Pasadas sin marcar como hechas")}</strong>
                <ul className="overdue-list">
                  {data.overdue.map((o) => (
                    <li key={o.id}>
                      <span>
                        {o.title} <span className="muted">· {fmtDate(o.date)}</span>
                      </span>
                      <button type="button" className="btn btn--ghost btn--xs" onClick={() => void markDone(o.id)}>
                        {t("Marcar hecha")}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.open_windows.length > 0 && (
              <ul className="agenda-list">
                {data.open_windows.map((w) => (
                  <AgendaRow key={w.uid} item={w} navigate={navigate} />
                ))}
              </ul>
            )}
            {rest.length === 0 && data.open_windows.length === 0 ? (
              <Empty icon="🌿" title={t("Nada en las próximas dos semanas")} />
            ) : (
              <ul className="agenda-list">
                {rest.map((it) => (
                  <AgendaRow key={it.uid} item={it} navigate={navigate} />
                ))}
              </ul>
            )}
            {heavyNext && mode === "detailed" && (
              <p className="muted small">
                {t("▲ La semana del")} {fmtDate(heavyNext.week)} {t("también viene cargada (")}{heavyNext.subjects.join(", ")}).
              </p>
            )}
          </Card>
        )}

        <div className="stack">
          {semestre && data.habits_today.length > 0 && (
            <Card title={t("Hábitos de hoy")}>
              <ul className="check-list">
                {data.habits_today.map((h) => (
                  <li key={h.id}>
                    <label className="check">
                      <input type="checkbox" checked={h.done} onChange={() => void toggleHabit(h.id)} />
                      <span>{h.title}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card title={t("Asignaturas en curso")}>
            {data.enrolled.length === 0 ? (
              <Empty icon="📚" title={t("No tienes asignaturas matriculadas")}>
                {t("Márcalas como «matriculada» en el expediente o aplica un semestre desde Módulos.")}
              </Empty>
            ) : (
              <ul className="subject-list">
                {data.enrolled.map((s) => (
                  <li key={s.id} className="subject-card" style={subjectStyle(s.id)}>
                    <a href={`/asignaturas/${s.id}`} onClick={linkTo(navigate, { name: "subject", id: s.id })} className="subject-list__name">
                      {s.name}
                    </a>
                    <AiBadge policy={s.ai_policy} compact={mode === "minimal"} />
                    <div className="small muted">
                      <EvalLine ev={s.evaluation} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

const PLAN_ICON: Record<DashboardT["today_plan"][number]["kind"], string> = { deliver: "📝", study: "📚", review: "🧠", lesson: "🎯" };

/** «Hoy toca»: de 1 a 3 cosas concretas, con enlace directo a donde se hacen. */
function TodayPlan({ plan, navigate }: { plan: DashboardT["today_plan"]; navigate: Navigate }) {
  if (!plan.length) return null;
  return (
    <section className="today-plan" aria-label={t("Hoy toca")}>
      <h2 className="today-plan__title">{t("Hoy toca")}</h2>
      <ol className="today-plan__list">
        {plan.map((p, i) => {
          const to: Route | null = p.lesson_id
            ? { name: "lesson", id: p.lesson_id }
            : p.kind === "review"
              ? { name: "study" }
              : p.subject_id
                ? { name: "subject", id: p.subject_id }
                : null;
          const href = p.lesson_id ? `/aprender/leccion/${p.lesson_id}` : p.kind === "review" ? "/estudio" : p.subject_id ? `/asignaturas/${p.subject_id}` : "#";
          return (
            <li key={i} className="today-plan__item" style={subjectStyle(p.subject_id ?? null)}>
              <span className="today-plan__icon" aria-hidden>
                {PLAN_ICON[p.kind]}
              </span>
              <span className="today-plan__body">
                {to ? (
                  <a className="today-plan__link" href={href} onClick={linkTo(navigate, to)}>
                    {p.title}
                  </a>
                ) : (
                  <strong>{p.title}</strong>
                )}
                <span className="small muted">{p.detail}</span>
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Horas previstas de las próximas semanas (solo en modo detallado). */
function WeekLoad({ weeks, heavy }: { weeks: DashboardT["week_load"]; heavy: string[] }) {
  const max = Math.max(10, ...weeks.map((w) => w.hours));
  if (!weeks.some((w) => w.hours > 0 || w.deliveries > 0)) return null;
  return (
    <Card title={t("Carga de las próximas semanas")} className="detail-only">
      <ul className="week-load">
        {weeks.map((w) => (
          <li key={w.week} className={`week-load__row${heavy.includes(w.week) ? " is-heavy" : ""}`}>
            <span className="week-load__label small">{fmtDate(w.week)}</span>
            <span className="week-load__bar" role="img" aria-label={t("Semana del {0}: {1} horas, {2} entregas", { 0: fmtDate(w.week), 1: w.hours, 2: w.deliveries })}>
              <span className="week-load__fill" style={{ width: `${(w.hours / max) * 100}%` }} />
            </span>
            <span className="week-load__num small">
              {w.hours} h{w.deliveries > 0 && ` · ${w.deliveries} 📝`}
            </span>
          </li>
        ))}
      </ul>
      <p className="muted small">{t("Horas semanales de tus asignaturas + las estimadas de lo que vence. ▲ = semana cargada.")}</p>
    </Card>
  );
}
