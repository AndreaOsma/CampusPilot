import { useMemo, useState } from "react";
import { api, type Career, type Subject } from "../api";
import { todayIso } from "../lib/format";
import { nextTerm, offeredShort, offeredWarning, planTermOptions, rulesOf, termClash, termLabel, termOf } from "../lib/rules";
import { useStore } from "../store";
import { t } from "../i18n";

const NONE = "";
const HIGH_LOAD = 30;

function isDone(s: Subject) {
  return s.status === "passed" || s.status === "convalidated";
}

/**
 * Tu plan de semestres: tú decides qué cursas y cuándo. El semestre recomendado por la uni
 * solo aparece como referencia; lo que se guarda es `planned_term` de cada asignatura.
 */
export function SemesterPlanner({ career, detailed }: { career: Career; detailed: boolean }) {
  const { subjects, reload } = useStore();
  const rules = rulesOf(career);
  const credits = rules.credit_label;
  const [extra, setExtra] = useState(0);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [over, setOver] = useState<string | null>(null);

  const pending = useMemo(
    () =>
      subjects
        .filter((s) => s.career_id === career.id && !isDone(s))
        .filter((s) => !(career.track && s.kind === "mencion" && s.track !== career.track))
        .sort((a, b) => (a.plan_semester ?? 99) - (b.plan_semester ?? 99) || a.name.localeCompare(b.name)),
    [subjects, career],
  );

  const columns = useMemo(() => {
    const now = termOf(todayIso(), rules.term_system, rules.year_start_month);
    const used = pending.map((s) => s.planned_term).filter((t): t is string => !!t);
    const last = [...used, nextTerm(now, rules.term_system === "annual" ? 2 : 3)].sort().reverse()[0];
    const first = [now, ...used].sort()[0];
    const out: string[] = [];
    for (let t = first; t <= last; t = nextTerm(t)) out.push(t);
    for (let i = 0; i < extra; i++) out.push(nextTerm(out[out.length - 1]));
    return out;
  }, [pending, extra, rules]);

  const move = async (s: Subject, term: string) => {
    const planned_term = term || null;
    if (planned_term === s.planned_term) return;
    setBusy(s.id);
    setError(null);
    try {
      const { id: _id, pack_ref: _ref, ...rest } = s;
      await api.subjects.update(s.id, { ...rest, planned_term });
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("No se pudo mover la asignatura"));
    } finally {
      setBusy(null);
    }
  };

  const onDrop = (term: string) => {
    const s = pending.find((x) => x.id === dragging);
    setDragging(null);
    setOver(null);
    if (s) void move(s, term);
  };

  const options = planTermOptions(null, todayIso(), rules.term_system, rules.year_start_month);
  const lanes: { term: string; rows: Subject[] }[] = [
    ...columns.map((term) => ({ term, rows: pending.filter((s) => s.planned_term === term) })),
    { term: NONE, rows: pending.filter((s) => !s.planned_term || !columns.includes(s.planned_term)) },
  ];
  const plannedEcts = pending.filter((s) => s.planned_term).reduce((a, s) => a + s.ects, 0);
  const totalEcts = pending.reduce((a, s) => a + s.ects, 0);

  if (pending.length === 0) return <p className="muted">{t("No te queda nada por planificar. 🎉")}</p>;

  return (
    <div className="planner">
      <p className="planner__summary small">
        <strong>{plannedEcts}</strong> {t("de")} {totalEcts} {credits} {t("pendientes ya tienen periodo.")}
        <span className="detail-only muted"> {t("Arrastra las asignaturas (o usa el selector) para colocarlas cuando tú quieras cursarlas.")}</span>
      </p>
      {error && (
        <p className="form-status form-status--error" role="alert">
          {error}
        </p>
      )}
      {[lanes.slice(0, -1), lanes.slice(-1)].map((group, gi) => (
        <div key={gi} className={gi === 0 ? "planner__board" : "planner__pool"}>
          {group.map(({ term, rows }) => {
            const ects = rows.reduce((a, s) => a + s.ects, 0);
            return (
              <section
                key={term || "none"}
                className={`planner__lane${term ? "" : " planner__lane--none"}${over === term ? " is-over" : ""}`}
                aria-label={term ? termLabel(term) : t("Sin planificar")}
                onDragOver={(e) => {
                  e.preventDefault();
                  setOver(term);
                }}
                onDragLeave={() => setOver((o) => (o === term ? null : o))}
                onDrop={(e) => {
                  e.preventDefault();
                  onDrop(term);
                }}
              >
                <header className="planner__head">
                  <h3>{term ? termLabel(term, true) : t("Sin planificar")}</h3>
                  <span className={`planner__ects${term && ects > HIGH_LOAD ? " is-high" : ""}`} title={term && ects > HIGH_LOAD ? t("Carga alta") : undefined}>
                    {ects} {credits}
                  </span>
                </header>
                {rows.length === 0 ? (
                  <p className="planner__empty muted small">{term ? t("Suelta aquí") : t("Todo colocado")}</p>
                ) : (
                  <ul className="planner__list">
                    {rows.map((s) => {
                      const clash = termClash(s.offered, s.planned_term);
                      return (
                        <li
                          key={s.id}
                          className={`planner__item${s.status === "enrolled" ? " is-enrolled" : ""}${clash ? " is-clash" : ""}${busy === s.id ? " is-busy" : ""}`}
                          draggable
                          onDragStart={(e) => {
                            e.dataTransfer.effectAllowed = "move";
                            setDragging(s.id);
                          }}
                          onDragEnd={() => setDragging(null)}
                        >
                          <span className="planner__name">{s.name}</span>
                          <span className="planner__meta muted small">
                            {s.ects} {credits}
                            {s.status === "enrolled" && t(" · cursando")}
                            {s.status === "failed" && t(" · a repetir")}
                            {offeredShort(s.offered) && ` · ${offeredShort(s.offered)}`}
                            {detailed && s.plan_semester && t(" · recomendado: {0}.º", { 0: s.plan_semester })}
                          </span>
                          {clash && (
                            <span className="planner__warn small" role="note">
                              ⚠️ {offeredWarning(s.offered)}
                            </span>
                          )}
                          <select
                            className="input-sm planner__select"
                            aria-label={t("Semestre para {0}", { 0: s.name })}
                            value={s.planned_term ?? NONE}
                            disabled={busy === s.id}
                            onChange={(e) => void move(s, e.target.value)}
                          >
                            <option value={NONE}>{t("Sin planificar")}</option>
                            {[...new Set([...columns, ...options])].sort().map((t) => (
                              <option key={t} value={t}>
                                {termLabel(t, true)}
                              </option>
                          ))}
                        </select>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          );
        })}
      </div>
      ))}
      <button type="button" className="btn btn--ghost btn--sm" onClick={() => setExtra((n) => n + 1)}>
        {t("+ Otro periodo")}
      </button>
    </div>
  );
}
