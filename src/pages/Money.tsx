import { useState } from "react";
import { api, type ExpenseIn, type Grant, type GrantIn, type Procedure, type ProcedureIn, type ProcedureStatus } from "../api";
import { AutoForm, type FieldDef } from "../components/AutoForm";
import { EXPENSE_CATEGORY, fmtDate, fmtGrade, fmtMoney, GRANT_STATUS, PROCEDURE_CATEGORY, PROCEDURE_STATUS, relDays, todayIso } from "../lib/format";
import { rulesOf } from "../lib/rules";
import { useStore } from "../store";
import { Card, ConfirmDelete, Empty, ErrorBox, Loading, Modal, PageHeader, useLoad, useUiMode } from "../ui";
import { t } from "../i18n";

const opts = (rec: Record<string, string>): Array<[string, string]> => Object.entries(rec);

const GRANT_FIELDS: FieldDef<GrantIn>[] = [
  { key: "name", label: "Beca / ayuda", type: "text", required: true, max: 200, wide: true },
  { key: "provider", label: t("Quién la da"), type: "text", max: 200 },
  { key: "status", label: t("Estado"), type: "select", options: opts(GRANT_STATUS) },
  { key: "amount", label: t("Importe"), type: "number", min: 0, nullable: true },
  { key: "deadline", label: t("Plazo de solicitud"), type: "date" },
  { key: "decision_date", label: t("Resolución"), type: "date" },
  { key: "min_average", label: t("Nota media mínima"), type: "number", min: 0, max: 10, step: 0.01, nullable: true },
  { key: "income_threshold", label: t("Umbral de renta"), type: "number", min: 0, nullable: true },
  { key: "url", label: t("Enlace"), type: "url", max: 500, wide: true, placeholder: "https://…" },
  { key: "notes", label: t("Notas"), type: "textarea", max: 5000 },
];
const PROCEDURE_FIELDS: FieldDef<ProcedureIn>[] = [
  { key: "title", label: t("Trámite"), type: "text", required: true, max: 200, wide: true },
  { key: "category", label: t("Tipo"), type: "select", options: opts(PROCEDURE_CATEGORY) },
  { key: "status", label: t("Estado"), type: "select", options: opts(PROCEDURE_STATUS) },
  { key: "window_start", label: t("Se abre"), type: "date" },
  { key: "deadline", label: t("Fecha límite"), type: "date" },
  { key: "url", label: t("Enlace"), type: "url", max: 500, wide: true, placeholder: "https://…" },
  { key: "notes", label: t("Notas"), type: "textarea", max: 5000 },
];

const NEW_GRANT: GrantIn = {
  name: "", provider: "", status: "idea", amount: null, deadline: null, decision_date: null, min_average: null, income_threshold: null, url: "", notes: "",
};
const NEW_PROCEDURE: ProcedureIn = { title: "", category: "admin", status: "todo", window_start: null, deadline: null, url: "", notes: "" };

export function Money() {
  const { settings, subjects, terms, currentTerm, careers } = useStore();
  const credits = rulesOf(careers.find((c) => !c.archived) ?? careers[0]).credit_label;
  const mode = useUiMode();
  const currency = settings?.currency ?? "EUR";
  const summary = useLoad(() => api.moneySummary());
  const expenses = useLoad(() => api.expenses.list());
  const grants = useLoad(() => api.grants.list());
  const eligibility = useLoad(() => api.grantsEligibility());
  const procedures = useLoad(() => api.procedures.list());
  const tuition = useLoad(() => (currentTerm ? api.tuition(currentTerm.id) : Promise.resolve(null)), [currentTerm?.id]);
  const [modal, setModal] = useState<null | "expense" | "grant" | "procedure" | { grant: Grant } | { procedure: Procedure }>(null);

  const reloadAll = () => {
    void summary.reload();
    void expenses.reload();
    void grants.reload();
    void eligibility.reload();
    void procedures.reload();
  };
  const close = () => {
    setModal(null);
    reloadAll();
  };

  const EXPENSE_FIELDS: FieldDef<ExpenseIn>[] = [
    { key: "date", label: t("Fecha"), type: "date", required: true },
    { key: "amount", label: t("Importe"), type: "number", required: true, step: 0.01, hint: t("En negativo, una devolución") },
    { key: "category", label: t("Categoría"), type: "select", options: opts(EXPENSE_CATEGORY) },
    { key: "description", label: t("Concepto"), type: "text", max: 200, wide: true },
    { key: "term_id", label: t("Semestre"), type: "select", nullable: true, numeric: true, options: terms.map((t) => [String(t.id), t.label]) },
    { key: "subject_id", label: t("Asignatura"), type: "select", nullable: true, numeric: true, options: subjects.map((s) => [String(s.id), s.name]) },
  ];

  const setProcedureStatus = async (p: Procedure, status: ProcedureStatus) => {
    await api.procedures.update(p.id, { ...p, status });
    void procedures.reload();
  };

  const today = todayIso();
  const openProcedures = (procedures.data ?? []).filter((p) => p.status !== "done");
  const doneProcedures = (procedures.data ?? []).filter((p) => p.status === "done");

  return (
    <div className="page">
      <PageHeader
        title={t("Dinero y trámites")}
        actions={
          <button type="button" className="btn btn--primary" onClick={() => setModal("expense")}>
            {t("+ Gasto")}
          </button>
        }
      />

      {summary.data && (
        <div className="stat-row">
          <div className="stat">
            <span className="stat__label">{t("Gastado en estudios")}</span>
            <span className="stat__value">{fmtMoney(summary.data.total, currency)}</span>
          </div>
          <div className="stat">
            <span className="stat__label">{t("Becas concedidas")}</span>
            <span className="stat__value">{fmtMoney(summary.data.grants_total, currency)}</span>
          </div>
          {tuition.data && (
            <div className="stat">
              <span className="stat__label">{t("Matrícula estimada")} {tuition.data.label}</span>
              <span className="stat__value">{fmtMoney(tuition.data.total, currency)}</span>
              {mode === "detailed" && <span className="muted small">{credits} {t("× precio por crédito")}</span>}
            </div>
          )}
        </div>
      )}

      <Card title={t("Trámites")} actions={<button type="button" className="btn btn--ghost btn--sm" onClick={() => setModal("procedure")}>{t("+ Trámite")}</button>}>
        {procedures.loading ? (
          <Loading />
        ) : procedures.error ? (
          <ErrorBox message={procedures.error} onRetry={procedures.reload} />
        ) : openProcedures.length === 0 ? (
          <Empty icon="📋" title={t("Sin trámites pendientes")} />
        ) : (
          <ul className="row-list">
            {openProcedures.map((p) => (
              <li key={p.id} className="row-list__item">
                <div>
                  <button type="button" className="link-btn" onClick={() => setModal({ procedure: p })}>
                    {p.title}
                  </button>
                  <div className={`small ${p.deadline && p.deadline < today ? "text-crit" : "muted"}`}>
                    {PROCEDURE_CATEGORY[p.category]}
                    {p.window_start && p.window_start > today && t(" · se abre el {0}", { 0: fmtDate(p.window_start) })}
                    {p.deadline && t(" · hasta el {0} ({1})", { 0: fmtDate(p.deadline), 1: relDays(p.deadline, today) })}
                  </div>
                </div>
                <select className="input-sm" aria-label={t("Estado de {0}", { 0: p.title })} value={p.status} onChange={(e) => void setProcedureStatus(p, e.target.value as ProcedureStatus)}>
                  {Object.entries(PROCEDURE_STATUS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
        )}
        {mode === "detailed" && doneProcedures.length > 0 && (
          <details className="details">
            <summary>{doneProcedures.length} {t("hechos")}</summary>
            <ul className="plain-list">
              {doneProcedures.map((p) => (
                <li key={p.id}>
                  <button type="button" className="link-btn" onClick={() => setModal({ procedure: p })}>
                    {p.title}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        )}
      </Card>

      <Card title={t("Becas y ayudas")} actions={<button type="button" className="btn btn--ghost btn--sm" onClick={() => setModal("grant")}>{t("+ Beca")}</button>}>
        {(grants.data ?? []).length === 0 ? (
          <Empty icon="💶" title={t("Sin becas apuntadas")} />
        ) : (
          <ul className="row-list">
            {(grants.data ?? []).map((g) => {
              const meets = eligibility.data?.meets_min_average[g.id];
              return (
                <li key={g.id} className="row-list__item">
                  <div>
                    <button type="button" className="link-btn" onClick={() => setModal({ grant: g })}>
                      {g.name}
                    </button>
                    <div className="muted small">
                      {GRANT_STATUS[g.status]}
                      {g.amount !== null && ` · ${fmtMoney(g.amount, currency)}`}
                      {g.deadline && t(" · plazo {0}", { 0: fmtDate(g.deadline) })}
                      {g.min_average !== null && (
                        <span className={meets === false ? " text-crit" : meets ? " text-ok" : ""}>
                          {" "}{t("· media mínima")} {fmtGrade(g.min_average)}
                          {meets === true && " ✓"}
                          {meets === false && t(" ✗ (tienes {0})", { 0: fmtGrade(eligibility.data?.average) })}
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card title={t("Gastos")}>
        {(expenses.data ?? []).length === 0 ? (
          <Empty icon="🧾" title={t("Sin gastos")} />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("Fecha")}</th>
                  <th>{t("Concepto")}</th>
                  {mode === "detailed" && <th>{t("Categoría")}</th>}
                  <th className="num">{t("Importe")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(expenses.data ?? []).map((e) => (
                  <tr key={e.id}>
                    <td>{fmtDate(e.date, true)}</td>
                    <td>{e.description || EXPENSE_CATEGORY[e.category]}</td>
                    {mode === "detailed" && <td>{EXPENSE_CATEGORY[e.category]}</td>}
                    <td className="num">{fmtMoney(e.amount, currency)}</td>
                    <td>
                      <ConfirmDelete label="✕" onConfirm={() => void api.expenses.remove(e.id).then(reloadAll)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {mode === "detailed" && tuition.data && tuition.data.rows.length > 0 && (
        <Card title={t("Matrícula estimada · {0}", { 0: tuition.data.label })}>
          <table className="table">
            <tbody>
              {tuition.data.rows.map((r) => (
                <tr key={r.subject_id}>
                  <td>
                    {r.name}
                    {r.attempt > 1 && <span className="muted small"> · {r.attempt}{t(".ª matrícula")}</span>}
                  </td>
                  <td className="num">{r.ects} {credits} × {fmtMoney(r.price_per_credit, currency)}</td>
                  <td className="num">{fmtMoney(r.amount, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">{t("El precio por crédito de cada asignatura (o el de Ajustes). Las segundas matrículas suelen costar más: ajústalo en la asignatura.")}</p>
        </Card>
      )}

      <Modal open={modal === "expense"} title={t("Nuevo gasto")} onClose={() => setModal(null)}>
        <AutoForm<ExpenseIn>
          fields={EXPENSE_FIELDS}
          initial={{ date: today, amount: 0, category: "tuition", description: "", term_id: currentTerm?.id ?? null, subject_id: null }}
          onSubmit={(d) => api.expenses.create(d).then(close)}
        />
      </Modal>
      <Modal open={modal === "grant"} title={t("Nueva beca")} onClose={() => setModal(null)}>
        <AutoForm<GrantIn> fields={GRANT_FIELDS} initial={NEW_GRANT} onSubmit={(d) => api.grants.create(d).then(close)} />
      </Modal>
      <Modal open={modal === "procedure"} title={t("Nuevo trámite")} onClose={() => setModal(null)}>
        <AutoForm<ProcedureIn> fields={PROCEDURE_FIELDS} initial={NEW_PROCEDURE} onSubmit={(d) => api.procedures.create(d).then(close)} />
      </Modal>
      <Modal open={!!modal && typeof modal === "object" && "grant" in modal} title={t("Beca")} onClose={() => setModal(null)}>
        {modal && typeof modal === "object" && "grant" in modal && (
          <>
            <AutoForm<GrantIn> fields={GRANT_FIELDS} initial={modal.grant} onSubmit={(d) => api.grants.update(modal.grant.id, d).then(close)} />
            <ConfirmDelete label={t("Borrar beca")} onConfirm={() => void api.grants.remove(modal.grant.id).then(close)} />
          </>
        )}
      </Modal>
      <Modal open={!!modal && typeof modal === "object" && "procedure" in modal} title={t("Trámite")} onClose={() => setModal(null)}>
        {modal && typeof modal === "object" && "procedure" in modal && (
          <>
            <AutoForm<ProcedureIn> fields={PROCEDURE_FIELDS} initial={modal.procedure} onSubmit={(d) => api.procedures.update(modal.procedure.id, d).then(close)} />
            <ConfirmDelete label={t("Borrar trámite")} onConfirm={() => void api.procedures.remove(modal.procedure.id).then(close)} />
          </>
        )}
      </Modal>
    </div>
  );
}
