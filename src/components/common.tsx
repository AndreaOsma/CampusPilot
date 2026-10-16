import type { AgendaItem, AiPolicy, Evaluation } from "../api";
import { AI_POLICY, fmtDate, fmtGrade, monthShort, parseDate, relDays, subjectStyle, todayIso, urgency, weekdayShort } from "../lib/format";
import { linkTo, type Navigate } from "../router";
import { t } from "../i18n";

const AI_ICON: Record<AiPolicy, string> = { unknown: "❔", allowed: "✅", limited: "⚠️", forbidden: "🚫" };

/** Distintivo de política de IA. En "prohibida" es deliberadamente llamativo. */
export function AiBadge({ policy, compact = false }: { policy: AiPolicy; compact?: boolean }) {
  return (
    <span className={`tag ai-badge ai-badge--${policy}`} title={AI_POLICY[policy]}>
      <span aria-hidden>{AI_ICON[policy]}</span>
      {compact ? <span className="sr-only">{AI_POLICY[policy]}</span> : <span>{AI_POLICY[policy]}</span>}
    </span>
  );
}

/** Píldora corta para listas: "sin IA". */
export function NoAiPill() {
  return (
    <span className="pill pill--noai" title={t("IA prohibida en esta actividad evaluable")}>
      {t("sin IA")}
    </span>
  );
}

/** Insignia de fecha: día de la semana + número (o rango si es una ventana). */
export function DateBadge({ date, end }: { date: string; end?: string | null }) {
  const d = parseDate(date);
  if (end && end !== date) {
    const e = parseDate(end);
    return (
      <span className="date-badge date-badge--range" aria-hidden>
        <span className="date-badge__wd">{monthShort(date)}</span>
        <span className="date-badge__d">
          {d.getDate()}–{e.getDate()}
        </span>
      </span>
    );
  }
  return (
    <span className="date-badge" aria-hidden>
      <span className="date-badge__wd">{weekdayShort(date)}</span>
      <span className="date-badge__d">{d.getDate()}</span>
    </span>
  );
}

const TYPE_LABEL: Record<AgendaItem["type"], string> = { activity: "", window: t("Ventana"), event: t("Evento"), procedure: t("Trámite"), grant: t("Beca") };

export function AgendaRow({
  item,
  navigate,
  onOpen,
  onDone,
}: {
  item: AgendaItem;
  navigate?: Navigate;
  onOpen?: () => void;
  onDone?: () => void;
}) {
  const today = todayIso();
  const isWindow = item.type === "window";
  const open = isWindow && item.date <= today;
  const refDate = isWindow && open && item.end_date ? item.end_date : item.date;
  const level = item.done ? "normal" : urgency(refDate, today);
  const rel = item.done ? t("✓ hecho") : open ? t("cierra {0}", { 0: relDays(item.end_date ?? item.date, today) }) : relDays(item.date, today);
  const label = `${TYPE_LABEL[item.type] ? `${TYPE_LABEL[item.type]}: ` : ""}${item.title}`;

  return (
    <li className={`agenda-row agenda-row--${item.type}${item.done ? " is-done" : ""}${open ? " is-open" : ""}`} style={subjectStyle(item.subject_id)}>
      <DateBadge date={item.date} end={isWindow ? item.end_date : null} />
      <div className="agenda-row__main">
        <div className="agenda-row__title">
          {onOpen ? (
            <button type="button" className="link-btn" onClick={onOpen} aria-label={label}>
              {item.title}
            </button>
          ) : (
            <span>{item.title}</span>
          )}
          {item.ai_forbidden && item.evaluable && <NoAiPill />}
        </div>
        <div className="agenda-row__meta small">
          {TYPE_LABEL[item.type] && <span className="agenda-row__type">{TYPE_LABEL[item.type]}</span>}
          {item.subject_name &&
            (navigate && item.subject_id ? (
              <a className="subj-chip" href={`/asignaturas/${item.subject_id}`} onClick={linkTo(navigate, { name: "subject", id: item.subject_id })}>
                {item.subject_name}
              </a>
            ) : (
              <span className="subj-chip">{item.subject_name}</span>
            ))}
          {item.time && <span className="muted">{item.time}</span>}
          {isWindow && item.end_date && <span className="muted">{fmtDate(item.date)} – {fmtDate(item.end_date)}</span>}
        </div>
      </div>
      <div className="agenda-row__side">
        <span className={`pill pill--${level}`}>{rel}</span>
        {onDone && !item.done && (
          <button type="button" className="btn btn--ghost btn--xs" onClick={onDone}>
            {t("Hecha")}
          </button>
        )}
      </div>
    </li>
  );
}

/** Nota actual / final y "cuánto necesito" en una línea. */
export function EvalLine({ ev }: { ev: Evaluation }) {
  if (ev.official_grade !== null)
    return (
      <span>
        {t("Nota oficial:")} <strong>{fmtGrade(ev.official_grade)}</strong>
      </span>
    );
  if (ev.final !== null)
    return (
      <span className={ev.passed ? "text-ok" : "text-crit"}>
        {t("Final:")} <strong>{fmtGrade(ev.final)}</strong> {ev.passed ? t("· aprobada") : t("· no superada")}
      </span>
    );
  return (
    <span>
      {ev.current !== null ? (
        <>
          {t("Vas con")} <strong>{fmtGrade(ev.current)}</strong>
        </>
      ) : (
        t("Sin notas aún")
      )}
      {ev.pending > 0 &&
        (ev.achievable ? (
          ev.needed !== null && (
            <>
              {" "}
              {t("· necesitas")} <strong>{fmtGrade(ev.needed)}</strong> {t("en lo pendiente")}
            </>
          )
        ) : (
          <span className="text-crit"> {t("· ya no se llega al objetivo")}</span>
        ))}
    </span>
  );
}
