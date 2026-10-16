import { useEffect, useMemo, useState } from "react";
import { api, type Activity, type ActivityIn, type ActivityKind, type CareerConfig, type EvalGroup, type Evaluation } from "../api";
import { AiBadge, DateBadge } from "../components/common";
import { SubjectForm } from "../components/SubjectForm";
import { SyllabusCard } from "../components/Syllabus";
import { ACTIVITY_KIND, fmtGrade, numOrNull, relDays, SUBJECT_STATUS, subjectStyle, todayIso, urgency } from "../lib/format";
import { activityKindLabel, ecLabel, letterOf, pfLabel, rulesOf, subjectKindLabel } from "../lib/rules";
import { linkTo, type Navigate } from "../router";
import { useStore } from "../store";
import { Card, ConfirmDelete, Empty, ErrorBox, Field, FormStatus, Loading, Modal, PageHeader, useLoad, useSubmit, useUiMode } from "../ui";
import { t } from "../i18n";

function emptyActivity(subjectId: number, groupId: number | null, scale = 10): ActivityIn {
  return {
    subject_id: subjectId,
    group_id: groupId,
    name: "",
    kind: "pec",
    weight: 1,
    grade: null,
    max_grade: scale,
    due_date: null,
    due_time: null,
    window_start: null,
    window_end: null,
    evaluable: true,
    done: false,
    kept_from_previous: false,
    estimated_hours: null,
    notes: "",
  };
}

function ActivityForm({ initial, activityId, groups, rules, onSaved }: { initial: ActivityIn; activityId?: number; groups: EvalGroup[]; rules: CareerConfig; onSaved: () => void }) {
  const [form, setForm] = useState<ActivityIn>(initial);
  const [hasWindow, setHasWindow] = useState(Boolean(initial.window_start));
  const { state, run } = useSubmit();
  const set = <K extends keyof ActivityIn>(k: K, v: ActivityIn[K]) => setForm((f) => ({ ...f, [k]: v }));
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = hasWindow ? form : { ...form, window_start: null, window_end: null };
    if (await run(() => (activityId ? api.activities.update(activityId, payload) : api.activities.create(payload)))) onSaved();
  };
  return (
    <form className="form" onSubmit={submit}>
      <div className="form-grid">
        <Field label={t("Nombre")} wide>
          {(id) => <input id={id} required maxLength={160} value={form.name} onChange={(e) => set("name", e.target.value)} />}
        </Field>
        <Field label={t("Tipo")}>
          {(id) => (
            <select id={id} value={form.kind} onChange={(e) => set("kind", e.target.value as ActivityKind)}>
              {Object.keys(ACTIVITY_KIND).map((k) => [k, activityKindLabel(rules, k as ActivityKind)]).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("Grupo")}>
          {(id) => (
            <select id={id} value={form.group_id ?? ""} onChange={(e) => set("group_id", e.target.value ? Number(e.target.value) : null)}>
              <option value="">{t("— (no cuenta para nota)")}</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("Peso dentro del grupo")} hint={t("Relativo: 1 y 1 = igual; 0 = no cuenta")}>
          {(id) => <input id={id} type="number" min={0} max={100} step={0.1} value={form.weight} onChange={(e) => set("weight", Number(e.target.value))} />}
        </Field>
        <Field label={t("Entrega")}>
          {(id) => <input id={id} type="date" value={form.due_date ?? ""} onChange={(e) => set("due_date", e.target.value || null)} />}
        </Field>
        <Field label={t("Hora")}>
          {(id) => <input id={id} type="time" value={form.due_time ?? ""} onChange={(e) => set("due_time", e.target.value || null)} />}
        </Field>
        <Field label={t("Tiene ventana")} hint={t("Se hace en un intervalo (vídeo, examen…)")}>
          {(id) => <input id={id} type="checkbox" checked={hasWindow} onChange={(e) => setHasWindow(e.target.checked)} />}
        </Field>
        {hasWindow && (
          <>
            <Field label={t("Abre")}>
              {(id) => <input id={id} type="date" required value={form.window_start ?? ""} onChange={(e) => set("window_start", e.target.value || null)} />}
            </Field>
            <Field label={t("Cierra")}>
              {(id) => <input id={id} type="date" required value={form.window_end ?? ""} onChange={(e) => set("window_end", e.target.value || null)} />}
            </Field>
          </>
        )}
        <Field label={t("Nota")}>
          {(id) => (
            <input id={id} type="number" min={0} max={form.max_grade} step={0.01} value={form.grade ?? ""} onChange={(e) => set("grade", numOrNull(e.target.value))} />
          )}
        </Field>
        <Field label={t("Sobre")}>
          {(id) => <input id={id} type="number" min={1} max={100} value={form.max_grade} onChange={(e) => set("max_grade", Number(e.target.value) || 10)} />}
        </Field>
        <Field label={t("Horas estimadas")}>
          {(id) => (
            <input id={id} type="number" min={0} max={500} step={0.5} value={form.estimated_hours ?? ""} onChange={(e) => set("estimated_hours", numOrNull(e.target.value))} />
          )}
        </Field>
        <Field label={t("Evaluable")}>
          {(id) => <input id={id} type="checkbox" checked={form.evaluable} onChange={(e) => set("evaluable", e.target.checked)} />}
        </Field>
        <Field label={t("Nota conservada")} hint={t("De una matrícula anterior (repetidores)")}>
          {(id) => <input id={id} type="checkbox" checked={form.kept_from_previous} onChange={(e) => set("kept_from_previous", e.target.checked)} />}
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

function GroupsEditor({ subjectId, groups, rules, onChange }: { subjectId: number; groups: EvalGroup[]; rules: CareerConfig; onChange: () => void }) {
  const [draft, setDraft] = useState({ name: "", weight: "", min: "" });
  const { state, run } = useSubmit();
  const total = groups.reduce((a, g) => a + g.weight, 0);

  const save = (g: EvalGroup, patch: Partial<EvalGroup>) => run(() => api.groups.update(g.id, { ...g, ...patch }).then(onChange));
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    await run(() =>
      api.groups
        .create({ subject_id: subjectId, name: draft.name, weight: Number(draft.weight) || 0, min_grade: numOrNull(draft.min), role: null, position: groups.length })
        .then(() => {
          setDraft({ name: "", weight: "", min: "" });
          onChange();
        })
    );
  };

  return (
    <div className="stack">
      <table className="table">
        <thead>
          <tr>
            <th>{t("Grupo")}</th>
            <th className="num">{t("Peso %")}</th>
            <th className="num">{t("Nota mínima")}</th>
            <th>{t("Papel")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.id}>
              <td>
                <input aria-label={t("Nombre del grupo")} defaultValue={g.name} maxLength={80} onBlur={(e) => e.target.value !== g.name && void save(g, { name: e.target.value })} />
              </td>
              <td className="num">
                <input className="input-sm" aria-label={t("Peso de {0}", { 0: g.name })} type="number" min={0} max={100} defaultValue={g.weight}
                  onBlur={(e) => Number(e.target.value) !== g.weight && void save(g, { weight: Number(e.target.value) })} />
              </td>
              <td className="num">
                <input className="input-sm" aria-label={t("Mínimo de {0}", { 0: g.name })} type="number" min={0} max={rules.grade_max} step={0.1} defaultValue={g.min_grade ?? ""}
                  onBlur={(e) => numOrNull(e.target.value) !== g.min_grade && void save(g, { min_grade: numOrNull(e.target.value) })} />
              </td>
              <td>
                <select className="input-sm" aria-label={t("Papel de {0}", { 0: g.name })} value={g.role ?? ""} onChange={(e) => void save(g, { role: (e.target.value || null) as EvalGroup["role"] })}>
                  <option value="">—</option>
                  <option value="ec">{ecLabel(rules)}</option>
                  <option value="pf">{pfLabel(rules)}</option>
                </select>
              </td>
              <td>
                <ConfirmDelete onConfirm={() => void run(() => api.groups.remove(g.id).then(onChange))} label="✕" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {total !== 100 && groups.length > 0 && <p className="text-warn small">{t("Los pesos suman")} {total} {t("%, no 100 %.")}</p>}
      <form className="inline-form" onSubmit={add}>
        <input aria-label={t("Nuevo grupo")} placeholder={t("Nombre: entregas, prácticas, examen…")} required maxLength={80} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        <input className="input-sm" aria-label={t("Peso %")} placeholder={t("Peso %")} type="number" min={0} max={100} required value={draft.weight} onChange={(e) => setDraft({ ...draft, weight: e.target.value })} />
        <input className="input-sm" aria-label={t("Nota mínima")} placeholder={t("Mín.")} type="number" min={0} max={rules.grade_max} step={0.1} value={draft.min} onChange={(e) => setDraft({ ...draft, min: e.target.value })} />
        <button type="submit" className="btn btn--ghost btn--sm">
          {t("+ Grupo")}
        </button>
      </form>
      <FormStatus state={state} />
    </div>
  );
}

export function SubjectDetail({ navigate, subjectId }: { navigate: Navigate; subjectId: number }) {
  const { subjects, careers, terms, reload: reloadStore } = useStore();
  const mode = useUiMode();
  const subject = subjects.find((s) => s.id === subjectId);
  const career = careers.find((c) => c.id === subject?.career_id);
  const rules = rulesOf(career);
  const groupsQ = useLoad(() => api.groups.list({ subject_id: subjectId }), [subjectId]);
  const actsQ = useLoad(() => api.activities.list({ subject_id: subjectId }), [subjectId]);
  const [target, setTarget] = useState<number | null>(null);
  const [hypo, setHypo] = useState<Record<number, number>>({});
  const [ev, setEv] = useState<Evaluation | null>(null);
  const [evError, setEvError] = useState<string | null>(null);
  const [modal, setModal] = useState<null | "edit" | "activity" | { activity: Activity }>(null);

  const refreshKey = useMemo(() => JSON.stringify([actsQ.data, groupsQ.data]), [actsQ.data, groupsQ.data]);

  useEffect(() => {
    let cancelled = false;
    const t = window.setTimeout(() => {
      api
        .simulate(subjectId, hypo, target)
        .then((r) => !cancelled && (setEv(r), setEvError(null)))
        .catch((e: Error) => !cancelled && setEvError(e.message));
    }, 200);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [subjectId, hypo, target, refreshKey]);

  if (!subject || !career) {
    return subjects.length ? <ErrorBox message="Asignatura no encontrada" /> : <Loading />;
  }

  const groups = groupsQ.data ?? [];
  const acts = [...(actsQ.data ?? [])].sort((a, b) =>
    (a.window_start ?? a.due_date ?? "9999").localeCompare(b.window_start ?? b.due_date ?? "9999")
  );
  const term = terms.find((t) => t.id === subject.term_id);
  const groupName = new Map(groups.map((g) => [g.id, g.name]));

  const reloadAll = () => {
    void actsQ.reload();
    void groupsQ.reload();
  };

  const patchActivity = async (a: Activity, patch: Partial<Activity>) => {
    const updated = await api.activities.update(a.id, { ...a, ...patch });
    actsQ.setData(acts.map((x) => (x.id === a.id ? updated : x)));
  };

  const today = todayIso();
  const pendingActs = acts.filter((a) => a.grade === null && a.evaluable && a.weight > 0 && a.group_id !== null);

  return (
    <div className="page subject-page" style={subjectStyle(subject.id)}>
      <PageHeader
        title={subject.name}
        subtitle={
          <>
            <a href="/expediente" onClick={linkTo(navigate, { name: "career" })}>
              {career.name}
            </a>
            {" · "}
            {subject.ects} {rules.credit_label} · {subjectKindLabel(rules, subject.kind)} · {SUBJECT_STATUS[subject.status]}
            {term && ` · ${term.label}`}
            {subject.attempt > 1 && t(" · {0}.ª matrícula", { 0: subject.attempt })}
          </>
        }
        actions={
          <button type="button" className="btn btn--ghost" onClick={() => setModal("edit")}>
            {t("Editar")}
          </button>
        }
      />

      {subject.ai_policy === "forbidden" ? (
        <div className="banner banner--crit" role="note">
          <AiBadge policy="forbidden" /> <strong>{t("en las actividades evaluables.")}</strong>
          {subject.ai_policy_note && <p className="small prewrap">{subject.ai_policy_note}</p>}
        </div>
      ) : (
        <p>
          <AiBadge policy={subject.ai_policy} />
          {subject.ai_policy_note && mode === "detailed" && <span className="muted small"> {subject.ai_policy_note}</span>}
        </p>
      )}

      {subject.links.length > 0 && (
        <p className="link-row">
          {subject.links.map((l) => (
            <a key={l.url} className="btn btn--ghost btn--sm" href={l.url} target={l.url.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
              {l.label}
            </a>
          ))}
        </p>
      )}

      <Card
        title={t("Nota")}
        actions={
          <div className="inline-label">
            <label htmlFor="target">{t("Objetivo")}</label>
            <input id="target" className="input-sm" type="number" min={0} max={rules.grade_max} step={rules.grade_max > 20 ? 1 : 0.5} value={target ?? rules.pass_mark}
              onChange={(e) => setTarget(e.target.value === "" ? null : Math.min(rules.grade_max, Number(e.target.value) || 0))} />
          </div>
        }
      >
        {evError && <ErrorBox message={evError} />}
        {ev && (
          <>
            <div className="grade-stats">
              <div className="grade-stat">
                <span className="grade-stat__label">{ev.official_grade !== null ? t("Nota oficial") : ev.final !== null ? t("Nota final") : t("Vas con")}</span>
                <span className={`grade-stat__value${ev.passed === false ? " text-crit" : ev.passed ? " text-ok" : ""}`}>
                  {fmtGrade(ev.official_grade ?? ev.final ?? ev.current)}
                  {letterOf(ev.official_grade ?? ev.final ?? ev.current, rules) && <span className="grade-letter"> {letterOf(ev.official_grade ?? ev.final ?? ev.current, rules)}</span>}
                </span>
              </div>
              {ev.pending > 0 && (
                <div className="grade-stat">
                  <span className="grade-stat__label">{t("Necesitas en lo pendiente")}</span>
                  <span className={`grade-stat__value${!ev.achievable ? " text-crit" : ""}`}>{ev.achievable ? fmtGrade(ev.needed) : "✗"}</span>
                  <span className="muted small">
                    {ev.achievable ? t("para un {0} · {1} pendiente{2}", { 0: fmtGrade(target), 1: ev.pending, 2: ev.pending > 1 ? "s" : "" }) : t("ya no se llega al objetivo")}
                  </span>
                </div>
              )}
            </div>
            {ev.reasons.map((r) => (
              <p key={r} className="text-crit small">
                {r}
              </p>
            ))}
            {ev.groups.length > 0 && (
              <ul className="group-bars">
                {ev.groups.map((g) => (
                  <li key={g.id} className={g.meets_min === false ? "is-failing" : ""}>
                    <div className="group-bars__head">
                      <span>
                        <strong>{g.name}</strong> <span className="muted small">{g.weight} %{g.min_grade !== null && t(" · mín. {0}", { 0: g.min_grade })}</span>
                      </span>
                      <span className="small">
                        {fmtGrade(g.grade)}
                        {letterOf(g.grade, rules) && ` · ${letterOf(g.grade, rules)}`}
                        {g.pending > 0 && <span className="muted"> · {g.pending} {t("pendiente")}{g.pending > 1 ? "s" : ""}</span>}
                      </span>
                    </div>
                    <div className="group-bars__track" role="img" aria-label={`${g.name}: ${fmtGrade(g.grade)} de ${rules.grade_max}${g.min_grade !== null ? t(", mínimo {0}", { 0: g.min_grade }) : ""}`}>
                      <div className="group-bars__fill" style={{ width: `${((g.grade ?? 0) / rules.grade_max) * 100}%` }} />
                      {g.min_grade !== null && <div className="group-bars__min" style={{ left: `${(g.min_grade / rules.grade_max) * 100}%` }} />}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {subject.eval_model === "ec_pf" && (
              <p className="muted small">
                {ecLabel(rules)} + {pfLabel(rules)}{t(": con la")} {ecLabel(rules)} {t("por debajo de")} {subject.eval_config.ec_pass} {t("la nota final es la de la")}{" "}
                {ecLabel(rules)}{t("; con la")} {pfLabel(rules)} {t("por debajo de")} {subject.eval_config.pf_min}{t(", la de la")} {pfLabel(rules)}{t("; si no te presentas a la")} {pfLabel(rules)} {t("con la")} {ecLabel(rules)} {t("aprobada,")} {subject.eval_config.no_show_grade}.
              </p>
            )}
          </>
        )}
        {pendingActs.length > 0 && (
          <details className="details" open={mode === "detailed"}>
            <summary>{t("¿Y si…? Simula notas en lo pendiente")}</summary>
            <div className="sim-grid">
              {pendingActs.map((a) => (
                <label key={a.id} className="sim-grid__item">
                  <span>{a.name}</span>
                  <input
                    type="number"
                    min={0}
                    max={rules.grade_max}
                    step={0.25}
                    value={hypo[a.id] ?? ""}
                    placeholder="—"
                    onChange={(e) => {
                      const v = numOrNull(e.target.value);
                      setHypo((h) => {
                        const next = { ...h };
                        if (v === null) delete next[a.id];
                        else next[a.id] = Math.max(0, Math.min(10, v));
                        return next;
                      });
                    }}
                  />
                </label>
              ))}
            </div>
            {Object.keys(hypo).length > 0 && (
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setHypo({})}>
                {t("Borrar simulación")}
              </button>
            )}
            <p className="muted small">{t("La simulación no guarda nada.")}</p>
          </details>
        )}
      </Card>

      <Card
        title={t("Actividades")}
        actions={
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => setModal("activity")}>
            {t("+ Actividad")}
          </button>
        }
      >
        {actsQ.loading ? (
          <Loading />
        ) : acts.length === 0 ? (
          <Empty icon="📝" title={t("Sin actividades")}>
            {t("Añade entregas, prácticas, cuestionarios o exámenes con su fecha y su grupo.")}
          </Empty>
        ) : (
          <ul className="activity-list">
            {acts.map((a) => (
              <li key={a.id} className={`activity${a.done ? " is-done" : ""}`}>
                {a.window_start || a.due_date ? (
                  <DateBadge date={(a.window_start ?? a.due_date)!} end={a.window_start ? a.window_end : null} />
                ) : (
                  <span className="date-badge date-badge--empty" aria-hidden>
                    —
                  </span>
                )}
                <label className="check" title={t("Hecha")}>
                  <input type="checkbox" checked={a.done} onChange={(e) => void patchActivity(a, { done: e.target.checked })} aria-label={t("{0} hecha", { 0: a.name })} />
                </label>
                <div className="activity__main">
                  <button type="button" className="link-btn activity__name" onClick={() => setModal({ activity: a })}>
                    {a.name}
                  </button>
                  <div className="muted small">
                    {ACTIVITY_KIND[a.kind]}
                    {a.group_id && ` · ${groupName.get(a.group_id) ?? ""}`}
                    {a.due_time && ` · ${a.due_time}`}
                    {!a.evaluable && t(" · no evaluable")}
                    {a.kept_from_previous && t(" · nota conservada")}
                    {mode === "detailed" && a.weight !== 1 && t(" · peso {0}", { 0: a.weight })}
                    {!a.done && (a.window_end ?? a.due_date) && (
                      <span className={`pill pill--${urgency((a.window_end ?? a.due_date)!, today)}`}>{relDays((a.window_end ?? a.due_date)!, today)}</span>
                    )}
                  </div>
                </div>
                <input
                  className="input-sm activity__grade"
                  type="number"
                  min={0}
                  max={a.max_grade}
                  step={0.01}
                  aria-label={t("Nota de {0}", { 0: a.name })}
                  placeholder={t("nota")}
                  defaultValue={a.grade ?? ""}
                  key={`${a.id}-${a.grade}`}
                  onBlur={(e) => {
                    const v = numOrNull(e.target.value);
                    if (v !== a.grade) void patchActivity(a, { grade: v });
                  }}
                />
                {rules.letters.length > 0 && a.max_grade === rules.grade_max && (
                  <select
                    className="input-sm activity__letter"
                    aria-label={t("Nota de {0} con letra", { 0: a.name })}
                    value={letterOf(a.grade, rules) ?? ""}
                    onChange={(e) => {
                      const l = rules.letters.find((x) => x.label === e.target.value);
                      void patchActivity(a, { grade: l ? l.value : null });
                    }}
                  >
                    <option value="">—</option>
                    {rules.letters.map((l) => (
                      <option key={l.label} value={l.label}>
                        {l.label}
                      </option>
                    ))}
                  </select>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {(mode === "detailed" || groups.length === 0) && (
        <Card title={t("Grupos de evaluación")}>
          <GroupsEditor subjectId={subject.id} groups={groups} rules={rules} onChange={reloadAll} />
        </Card>
      )}

      <SyllabusCard subjectId={subject.id} navigate={navigate} />

      {subject.notes && (
        <Card title={t("Notas")}>
          <p className="prewrap">{subject.notes}</p>
        </Card>
      )}

      <div className="danger-zone">
        <ConfirmDelete
          label={t("Borrar asignatura")}
          onConfirm={() =>
            void api.subjects.remove(subject.id).then(async () => {
              await reloadStore();
              navigate({ name: "career" });
            })
          }
        />
      </div>

      <Modal open={modal === "edit"} title={t("Editar asignatura")} onClose={() => setModal(null)}>
        <SubjectForm initial={subject} subjectId={subject.id} career={career} onSaved={() => setModal(null)} />
      </Modal>
      <Modal open={modal === "activity"} title={t("Nueva actividad")} onClose={() => setModal(null)}>
        <ActivityForm
          initial={emptyActivity(subject.id, groups[0]?.id ?? null, rules.grade_max)}
          groups={groups}
          rules={rules}
          onSaved={() => {
            setModal(null);
            void actsQ.reload();
          }}
        />
      </Modal>
      <Modal open={typeof modal === "object" && modal !== null} title={t("Actividad")} onClose={() => setModal(null)}>
        {typeof modal === "object" && modal !== null && (
          <>
            <ActivityForm
              initial={modal.activity}
              activityId={modal.activity.id}
              groups={groups}
              rules={rules}
              onSaved={() => {
                setModal(null);
                void actsQ.reload();
              }}
            />
            <ConfirmDelete
              label={t("Borrar actividad")}
              onConfirm={() =>
                void api.activities.remove(modal.activity.id).then(() => {
                  setModal(null);
                  void actsQ.reload();
                })
              }
            />
          </>
        )}
      </Modal>
    </div>
  );
}
