import { useEffect, useMemo, useState } from "react";
import { api, type Career as CareerT, type CareerIn, type Subject, type SubjectKind, type SubjectStatus, type TermIn } from "../api";
import { AiBadge } from "../components/common";
import { emptySubject, SubjectForm } from "../components/SubjectForm";
import { SemesterPlanner } from "../components/SemesterPlanner";
import { CareerRulesFields } from "../components/CareerRulesFields";
import { fmtDate, fmtGrade, SUBJECT_STATUS, subjectStyle, todayIso } from "../lib/format";
import { DEFAULT_CONFIG, offeredShort, rulesOf, subjectKindLabel } from "../lib/rules";
import { linkTo, type Navigate } from "../router";
import { useStore } from "../store";
import { Card, Empty, Field, FormStatus, Loading, Modal, PageHeader, ProgressBar, useLoad, useSubmit, useUiMode, writeStored } from "../ui";
import { t } from "../i18n";

const STATUS_FILTERS: Array<{ id: "all" | SubjectStatus | "todo"; label: string }> = [
  { id: "all", label: t("Todas") },
  { id: "enrolled", label: t("Matriculadas") },
  { id: "todo", label: t("Por cursar") },
  { id: "passed", label: t("Aprobadas") },
  { id: "convalidated", label: t("Convalidadas") },
];

function CareerForm({ initial, careerId, onSaved }: { initial: CareerIn; careerId?: number; onSaved: (c: CareerT) => void }) {
  const [form, setForm] = useState<CareerIn>(initial);
  const { state, run } = useSubmit();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const saved = await run(() => (careerId ? api.careers.update(careerId, form) : api.careers.create(form)));
    if (saved) onSaved(saved);
  };
  return (
    <form className="form" onSubmit={submit}>
      <div className="form-grid">
        <Field label={t("Titulación")} wide>
          {(id) => <input id={id} required maxLength={200} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
        </Field>
        <Field label={t("Universidad / centro")} wide>
          {(id) => <input id={id} maxLength={200} value={form.institution} onChange={(e) => setForm({ ...form, institution: e.target.value })} />}
        </Field>
        <Field label={t("{0} totales", { 0: form.config.credit_label })}>
          {(id) => (
            <input id={id} type="number" min={1} max={1000} required value={form.ects_goal} onChange={(e) => setForm({ ...form, ects_goal: Number(e.target.value) })} />
          )}
        </Field>
        <Field label={t("Archivada")} hint={t("Estudios que ya no sigues")}>
          {(id) => <input id={id} type="checkbox" checked={form.archived} onChange={(e) => setForm({ ...form, archived: e.target.checked })} />}
        </Field>
      </div>
      <CareerRulesFields value={form.config} onChange={(config) => setForm({ ...form, config })} />
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={state.status === "loading"}>
          {t("Guardar")}
        </button>
        <FormStatus state={state} />
      </div>
    </form>
  );
}

function TermForm({ careerId, onSaved }: { careerId: number; onSaved: () => void }) {
  const [form, setForm] = useState<TermIn>({ career_id: careerId, label: "", start_date: todayIso(), end_date: null });
  const { state, run } = useSubmit();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await run(() => api.terms.create(form))) onSaved();
  };
  return (
    <form className="form" onSubmit={submit}>
      <div className="form-grid">
        <Field label={t("Nombre")} hint={t("p. ej. 2026S1, 1.er cuatrimestre…")}>
          {(id) => <input id={id} required maxLength={40} value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />}
        </Field>
        <Field label={t("Empieza")}>
          {(id) => <input id={id} type="date" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />}
        </Field>
        <Field label={t("Acaba")}>
          {(id) => <input id={id} type="date" value={form.end_date ?? ""} onChange={(e) => setForm({ ...form, end_date: e.target.value || null })} />}
        </Field>
      </div>
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={state.status === "loading"}>
          {t("Añadir semestre")}
        </button>
        <FormStatus state={state} />
      </div>
    </form>
  );
}

export function Career({ navigate }: { navigate: Navigate }) {
  const { careers, subjects, terms, reload, loading } = useStore();
  const mode = useUiMode();
  const active = careers.filter((c) => !c.archived);
  const [careerId, setCareerId] = useState<number | null>(() => {
    try {
      return Number(localStorage.getItem("campus-career")) || null;
    } catch {
      return null;
    }
  });
  const career = careers.find((c) => c.id === careerId) ?? active[0] ?? careers[0] ?? null;
  useEffect(() => {
    if (career) writeStored("campus-career", String(career.id));
  }, [career]);

  const [filter, setFilter] = useState<(typeof STATUS_FILTERS)[number]["id"]>("all");
  const [modal, setModal] = useState<null | "career-new" | "career-edit" | "subject" | "term">(null);
  const summary = useLoad(() => (career ? api.careerSummary(career.id) : Promise.resolve(null)), [career?.id, subjects]);
  const rules = rulesOf(career);
  const credits = rules.credit_label;
  const iosImport = useSubmit();

  const list = useMemo(() => {
    if (!career) return [];
    return subjects
      .filter((s) => s.career_id === career.id)
      .filter((s) => (career.track && s.kind === "mencion" ? s.track === career.track : true))
      .filter((s) => {
        if (filter === "all") return true;
        if (filter === "todo") return s.status === "pending" || s.status === "failed";
        return s.status === filter;
      });
  }, [subjects, career, filter]);

  const groups = useMemo(() => {
    // Orden: semestres del plan (1, 2, 3…), luego cada mención, optativas, TFG y el resto.
    const trackName = new Map((career?.tracks ?? []).map((t) => [t.id, t.name]));
    const map = new Map<string, { order: number; rows: Subject[] }>();
    for (const s of list) {
      let key: string;
      let order: number;
      if (s.plan_semester) {
        key = t("Periodo {0} del plan", { 0: s.plan_semester });
        order = s.plan_semester;
      } else if (s.kind === "mencion") {
        key = s.track ? trackName.get(s.track) ?? t("Mención") : t("Mención");
        order = 100;
      } else {
        key = subjectKindLabel(rules, s.kind);
        order = s.kind === "optativa" ? 200 : s.kind === "tfg" ? 300 : 400;
      }
      const g = map.get(key) ?? { order, rows: [] };
      g.rows.push(s);
      map.set(key, g);
    }
    return [...map.entries()].sort((a, b) => a[1].order - b[1].order || a[0].localeCompare(b[0])).map(([k, g]) => [k, g.rows] as const);
  }, [list, career]);

  if (loading) return <Loading />;

  if (!career) {
    return (
      <div className="page">
        <PageHeader title={t("Expediente")} />
        <Card title={t("Crea tu carrera")}>
          <p className="muted">
            {t("Si tu titulación tiene un módulo de estudios, instálalo desde")}{" "}
            <a href="/modulos" onClick={linkTo(navigate, { name: "modules" })}>
              {t("Módulos")}
            </a>{" "}
            {t("y te ahorras meter el plan de estudios a mano.")}
          </p>
          <CareerForm initial={{ name: "", institution: "", ects_goal: 240, track: null, requirements: {}, config: DEFAULT_CONFIG, archived: false }} onSaved={() => void reload()} />
        </Card>
      </div>
    );
  }

  const quickStatus = async (s: Subject, status: SubjectStatus) => {
    await api.subjects.update(s.id, { ...s, status });
    await reload();
  };

  const setTrack = async (track: string | null) => {
    await api.careers.update(career.id, { ...career, track });
    await reload();
  };

  const onIosFile = async (file: File | undefined) => {
    if (!file) return;
    const res = await iosImport.run(() => api.importIos(career.id, file), t("Importado"));
    if (res) await reload();
  };

  const sum = summary.data;
  const kinds = sum ? Object.keys({ ...sum.requirements, ...sum.by_kind }) : [];

  return (
    <div className="page">
      <PageHeader
        title={t("Expediente")}
        subtitle={career.institution || undefined}
        actions={
          <>
            {careers.length > 1 && (
              <select aria-label={t("Carrera")} value={career.id} onChange={(e) => setCareerId(Number(e.target.value))}>
                {careers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.archived ? t(" (archivada)") : ""}
                  </option>
                ))}
              </select>
            )}
            <button type="button" className="btn btn--primary" onClick={() => setModal("subject")}>
              {t("+ Asignatura")}
            </button>
          </>
        }
      />

      <Card
        title={career.name}
        actions={
          <>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setModal("career-edit")}>
              {t("Editar")}
            </button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setModal("career-new")}>
              {t("Otra carrera")}
            </button>
          </>
        }
      >
        {sum && (
          <>
            <div className="stat-row stat-row--3">
              <div className="stat">
                <span className="stat__label">{credits} {t("superados")}</span>
                <span className="stat__value">
                  {sum.ects_done}
                  <small className="muted"> / {sum.ects_goal}</small>
                </span>
                <ProgressBar value={sum.ects_done} max={sum.ects_goal} label={t("{0} superados", { 0: credits })} />
              </div>
              <div className="stat">
                <span className="stat__label">{t("Matriculados")}</span>
                <span className="stat__value">{sum.ects_enrolled}</span>
              </div>
              <div className="stat">
                <span className="stat__label">{t("Media ponderada")}</span>
                <span className="stat__value">{fmtGrade(sum.average)}</span>
              </div>
            </div>
            {mode === "detailed" && kinds.length > 0 && (
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("Tipo")}</th>
                    <th className="num">{t("Superados")}</th>
                    <th className="num">{t("Exigidos")}</th>
                    <th>{t("Progreso")}</th>
                  </tr>
                </thead>
                <tbody>
                  {kinds.map((k) => {
                    const done = sum.by_kind[k]?.done ?? 0;
                    const req = sum.requirements[k];
                    return (
                      <tr key={k}>
                        <td>{subjectKindLabel(rules, k as SubjectKind)}</td>
                        <td className="num">{done}</td>
                        <td className="num">{req ?? "—"}</td>
                        <td>{req ? <ProgressBar value={done} max={req} label={t("{0} de {1}", { 0: credits, 1: k })} /> : null}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </>
        )}
        {career.tracks.length > 0 && (
          <div className="inline-label">
            <label htmlFor="career-track">{t("Mención")}</label>
            <select id="career-track" value={career.track ?? ""} onChange={(e) => void setTrack(e.target.value || null)}>
              <option value="">{t("Sin decidir (ver todas)")}</option>
              {career.tracks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </Card>

      <Card title={t("Mi plan de semestres")}>
        <SemesterPlanner career={career} detailed={mode === "detailed"} />
      </Card>

      <Card
        title={t("Asignaturas")}
        actions={
          <div className="segmented segmented--sm segmented--scroll" role="group" aria-label={t("Filtrar por estado")}>
            {STATUS_FILTERS.map((f) => (
              <button key={f.id} type="button" className={filter === f.id ? "is-active" : ""} aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
                {f.label}
              </button>
            ))}
          </div>
        }
      >
        {groups.length === 0 ? (
          <Empty icon="📚" title={t("Nada con este filtro")} />
        ) : (
          groups.map(([label, rows]) => {
            const done = rows.filter((x) => x.status === "passed" || x.status === "convalidated").length;
            const active = rows.some((x) => x.status === "enrolled");
            return (
              <details key={label} className="subject-group" open={active || filter !== "all" || groups.length <= 3}>
                <summary className="subject-group__title">
                  <span>{label}</span>
                  <span className="muted small">
                    {done}/{rows.length} · {rows.reduce((a, x) => a + x.ects, 0)} {credits}
                  </span>
                </summary>
                <ul className="subject-rows">
                  {rows.map((x) => (
                    <li key={x.id} className={`subject-row subject-row--${x.status}`} style={subjectStyle(x.id)}>
                      <a className="subject-row__name" href={`/asignaturas/${x.id}`} onClick={linkTo(navigate, { name: "subject", id: x.id })}>
                        {x.name}
                      </a>
                      <span className="subject-row__meta muted small">
                        {x.ects} {credits}
                        {offeredShort(x.offered) && x.status !== "passed" && x.status !== "convalidated" && ` · ${offeredShort(x.offered)}`}
                        {mode === "detailed" && x.code && ` · ${x.code}`}
                        {x.final_grade !== null && (
                          <>
                            {" · "}
                            <strong className="text-ok">{fmtGrade(x.final_grade)}</strong>
                          </>
                        )}
                      </span>
                      <span className="subject-row__side">
                        {x.ai_policy === "forbidden" && <AiBadge policy={x.ai_policy} compact />}
                        {mode === "detailed" ? (
                          <select className="input-sm" aria-label={t("Estado de {0}", { 0: x.name })} value={x.status}
                            onChange={(e) => void quickStatus(x, e.target.value as SubjectStatus)}>
                            {Object.entries(SUBJECT_STATUS).map(([k, v]) => (
                              <option key={k} value={k}>
                                {v}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className={`status-pill status-pill--${x.status}`}>{SUBJECT_STATUS[x.status]}</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            );
          })
        )}
      </Card>

      <Card title={t("Semestres")} actions={<button type="button" className="btn btn--ghost btn--sm" onClick={() => setModal("term")}>{t("+ Semestre")}</button>}>
        {terms.filter((t) => t.career_id === career.id).length === 0 ? (
          <p className="muted">{t("Sin semestres todavía.")}</p>
        ) : (
          <ul className="plain-list">
            {terms
              .filter((term) => term.career_id === career.id)
              .map((term) => (
                <li key={term.id}>
                  <strong>{term.label}</strong>{" "}
                  <span className="muted small">
                    {fmtDate(term.start_date, true)} – {term.end_date ? fmtDate(term.end_date, true) : "?"} · {subjects.filter((s) => s.term_id === term.id).length} {t("asignaturas")}
                  </span>
                </li>
              ))}
          </ul>
        )}
      </Card>

      <Card title={t("Compartir e importar")}>
          <div className="form-grid detail-only">
            <Field label={t("Importar desde la app iOS antigua")} hint={t("El JSON que exportaba Campus Pilot para iPhone")}>
              {(id) => <input id={id} type="file" accept="application/json,.json" onChange={(e) => void onIosFile(e.target.files?.[0])} />}
            </Field>
          </div>
          <FormStatus state={iosImport.state} />
          <p>
            <a className="btn btn--ghost btn--sm" href={api.exportPackUrl(career.id)} download={`${career.name}.json`}>
              {t("⬇ Exportar como módulo de estudios")}
            </a>{" "}
            <span className="muted small">{t("Plan, reglas, grupos de evaluación y fechas, sin notas ni nada personal: para que otra persona de tu universidad lo instale.")}</span>
          </p>
        </Card>

      <Modal open={modal === "subject"} title={t("Nueva asignatura")} onClose={() => setModal(null)}>
        <SubjectForm initial={emptySubject(career)} career={career} onSaved={() => setModal(null)} />
      </Modal>
      <Modal open={modal === "term"} title={t("Nuevo semestre")} onClose={() => setModal(null)}>
        <TermForm
          careerId={career.id}
          onSaved={() => {
            setModal(null);
            void reload();
          }}
        />
      </Modal>
      <Modal open={modal === "career-edit"} title={t("Editar carrera")} onClose={() => setModal(null)}>
        <CareerForm
          initial={{
            name: career.name, institution: career.institution, ects_goal: career.ects_goal, track: career.track,
            requirements: career.requirements, config: rulesOf(career), archived: career.archived,
          }}
          careerId={career.id}
          onSaved={() => {
            setModal(null);
            void reload();
          }}
        />
      </Modal>
      <Modal open={modal === "career-new"} title={t("Nueva carrera")} onClose={() => setModal(null)}>
        <CareerForm
          initial={{ name: "", institution: "", ects_goal: 240, track: null, requirements: {}, config: DEFAULT_CONFIG, archived: false }}
          onSaved={(c) => {
            setModal(null);
            setCareerId(c.id);
            void reload();
          }}
        />
      </Modal>
    </div>
  );
}
