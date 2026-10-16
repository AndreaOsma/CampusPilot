import { api, type WeekModule } from "../api";
import { fmtDate, relDays, todayIso } from "../lib/format";
import { linkTo, type Navigate } from "../router";
import { Card, useLoad } from "../ui";
import { t } from "../i18n";

function ModuleRow({ m, navigate, late }: { m: WeekModule; navigate: Navigate; late?: boolean }) {
  return (
    <li className={`week-item${late ? " week-item--late" : ""}`}>
      <span>
        <strong>{m.title}</strong>{" "}
        {late && <span className="pill pill--warn">{t("atrasado")}</span>}{" "}
        <span className="muted small">
          {m.lessons ? t("{0}/{1} lecciones", { 0: m.done, 1: m.lessons }) : m.has_material ? t("material listo: genera sus lecciones") : t("sube su material")}
        </span>
      </span>
      {m.next_lesson_id && (
        <a className="btn btn--primary btn--xs" href={`/aprender/leccion/${m.next_lesson_id}`} onClick={linkTo(navigate, { name: "lesson", id: m.next_lesson_id })}>
          {t("Seguir")}
        </a>
      )}
    </li>
  );
}

/** Aprender: qué toca esta semana según el plan docente, las entregas y cómo vas. */
export function WeekPlanCard({ subjectId, navigate }: { subjectId: number; navigate: Navigate }) {
  const q = useLoad(() => api.syllabus.studyPlan(subjectId), [subjectId]);
  const p = q.data;
  if (!p?.has_plan) return null;
  const today = todayIso();
  const nothing = !p.this_week.length && !p.behind.length && !p.deadlines.length && !p.weak_objectives.length && !p.due_reviews;
  const week = p.weeks[p.current_week];
  return (
    <Card title={t("Esta semana")} actions={week ? <span className="muted small">{t("Semana {0} de {1}", { 0: p.current_week + 1, 1: p.weeks.length })}</span> : undefined}>
      {nothing && <p className="muted">{t("Nada pendiente: vas al día.")}</p>}
      <ul className="week-list">
        {p.this_week.map((m) => (
          <ModuleRow key={m.ref} m={m} navigate={navigate} />
        ))}
        {p.behind.map((m) => (
          <ModuleRow key={`late-${m.ref}`} m={m} navigate={navigate} late />
        ))}
        {p.deadlines.map((d) => (
          <li key={d.activity_id} className="week-item">
            <span>
              📅 <strong>{d.name}</strong> <span className="muted small">· {relDays(d.date, today)} ({fmtDate(d.date)})</span>
            </span>
          </li>
        ))}
        {p.weak_objectives.map((o) =>
          p.course_id ? (
            <li key={o.code} className="week-item">
              <span>
                🎯 <strong>{o.code}</strong> <span className="small">{o.text}</span> <span className="muted small">· {Math.round(o.mastery * 100)} %</span>
              </span>
              <a className="btn btn--ghost btn--xs" href={`/aprender/practica/${p.course_id}/objetivo/${encodeURIComponent(o.code)}`}
                onClick={linkTo(navigate, { name: "practice", courseId: p.course_id, concept: "", objective: o.code })}>
                {t("Practicar")}
              </a>
            </li>
          ) : null,
        )}
        {p.due_reviews > 0 && (
          <li className="week-item">
            <span>🔁 {t("{0} ejercicios para repasar", { 0: p.due_reviews })}</span>
            <a className="btn btn--ghost btn--xs" href="/aprender/repaso" onClick={linkTo(navigate, { name: "review" })}>
              {t("Repasar")}
            </a>
          </li>
        )}
      </ul>
      {p.hours_goal ? (
        <p className="muted small">{t("Llevas {0} de {1} h previstas esta semana.", { 0: (p.minutes_this_week / 60).toFixed(1), 1: p.hours_goal })}</p>
      ) : null}
      <details className="detail-only">
        <summary>{t("Calendario de módulos")}</summary>
        <ol className="week-timeline">
          {p.weeks.map((w, i) => (
            <li key={w.start} className={i === p.current_week ? "is-current" : i < p.current_week ? "is-past" : ""}>
              <span className="muted small">{fmtDate(w.start)}</span> {w.modules.join(", ") || "—"}
            </li>
          ))}
        </ol>
      </details>
    </Card>
  );
}
