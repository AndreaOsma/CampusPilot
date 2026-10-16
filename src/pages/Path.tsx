import { useMemo, useState } from "react";
import { api, type PathItem, type PathItemIn, type PathKind, type PathStatus } from "../api";
import { AutoForm, type FieldDef } from "../components/AutoForm";
import { fmtDate, PATH_KIND, PATH_STATUS, SUBJECT_STATUS } from "../lib/format";
import { termLabel } from "../lib/rules";
import { useStore } from "../store";
import { Card, ConfirmDelete, Empty, ErrorBox, Loading, Modal, PageHeader, useLoad, useUiMode } from "../ui";
import { t } from "../i18n";

const KIND_ICON: Record<PathKind, string> = {
  course: "📘", certification: "🏅", project: "🛠️", internship: "🏢", job: "💼", language: "🗣️", volunteering: "🤝", award: "🏆", other: "✨",
};
const STATUS_ORDER: PathStatus[] = ["in_progress", "planned", "idea", "done", "dropped"];

const NEW_ITEM: PathItemIn = {
  kind: "course", title: "", organization: "", status: "planned", start_date: null, end_date: null, hours: null, url: "", skills: [], subject_id: null, notes: "",
};

function Itinerary() {
  const { careers, subjects } = useStore();
  const career = careers.find((c) => !c.archived) ?? careers[0];
  // Tu plan (semestre que eliges tú) manda; si aún no has planificado nada, se usa el recomendado de la uni.
  const { bySemester, personal } = useMemo(() => {
    if (!career) return { bySemester: [], personal: false };
    const mine = subjects.filter((x) => x.career_id === career.id && !(x.kind === "mencion" && career.track && x.track !== career.track));
    const personal = mine.some((s) => s.planned_term);
    const map = new Map<string, typeof subjects>();
    for (const s of mine) {
      const key = personal ? s.planned_term ?? "" : s.plan_semester ? String(s.plan_semester).padStart(2, "0") : "";
      if (!key) continue;
      map.set(key, [...(map.get(key) ?? []), s]);
    }
    return { bySemester: [...map.entries()].sort(([a], [b]) => a.localeCompare(b)), personal };
  }, [career, subjects]);
  if (!career || bySemester.length === 0) return null;
  return (
    <Card title={t("Itinerario · {0}", { 0: career.name })}>
      <div className="itinerary">
        {bySemester.map(([sem, list]) => {
          const done = list.filter((s) => s.status === "passed" || s.status === "convalidated").length;
          return (
            <section key={sem} className="itinerary__sem">
              <h3>
                {personal ? termLabel(sem, true) : t("Periodo {0}", { 0: Number(sem) })}{" "}
                <span className="muted small">
                  {done}/{list.length}
                </span>
              </h3>
              <ul>
                {list.map((s) => (
                  <li key={s.id} className={`itinerary__subject is-${s.status}`} title={SUBJECT_STATUS[s.status]}>
                    {s.name}
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
      <p className="muted small">
        {personal ? t("Según tu plan de semestres (Expediente).") : t("Según el semestre recomendado del plan; organiza el tuyo en Expediente.")} {t("En verde lo superado, en azul lo que cursas.")}
      </p>
    </Card>
  );
}

export function PathPage() {
  const { subjects } = useStore();
  const mode = useUiMode();
  const items = useLoad(() => api.path.list());
  const skills = useLoad(() => api.pathSkills());
  const [modal, setModal] = useState<null | "new" | { item: PathItem }>(null);

  const fields: FieldDef<PathItemIn>[] = [
    { key: "title", label: t("Qué"), type: "text", required: true, max: 200, wide: true },
    { key: "kind", label: t("Tipo"), type: "select", options: Object.entries(PATH_KIND) },
    { key: "status", label: t("Estado"), type: "select", options: Object.entries(PATH_STATUS) },
    { key: "organization", label: "Dónde / con quién", type: "text", max: 200 },
    { key: "start_date", label: t("Desde"), type: "date" },
    { key: "end_date", label: t("Hasta"), type: "date" },
    { key: "hours", label: t("Horas"), type: "number", min: 0, nullable: true },
    { key: "skills", label: t("Competencias"), type: "tags", wide: true, hint: t("Lo que aprendes o demuestras: redes, Python, inglés C1…") },
    { key: "subject_id", label: t("Relacionado con la asignatura"), type: "select", nullable: true, numeric: true, options: subjects.map((s) => [String(s.id), s.name]) },
    { key: "url", label: t("Enlace"), type: "url", max: 500, wide: true, placeholder: "https://…" },
    { key: "notes", label: t("Notas"), type: "textarea", max: 10000 },
  ];

  const close = () => {
    setModal(null);
    void items.reload();
    void skills.reload();
  };

  const grouped = useMemo(() => {
    const list = items.data ?? [];
    return STATUS_ORDER.map((st) => [st, list.filter((i) => i.status === st)] as const).filter(([, l]) => l.length);
  }, [items.data]);

  return (
    <div className="page">
      <PageHeader
        title={t("Trayectoria")}
        subtitle={t("Lo que suma además del expediente: cursos, certificaciones, proyectos, prácticas, idiomas…")}
        actions={
          <button type="button" className="btn btn--primary" onClick={() => setModal("new")}>
            {t("+ Añadir")}
          </button>
        }
      />

      {(skills.data ?? []).length > 0 && (
        <Card title={t("Competencias")}>
          <ul className="skill-cloud">
            {(skills.data ?? []).map((s) => (
              <li key={s.skill} className={`tag${s.done ? " tag--ok" : ""}`} title={t("{0} elemento(s), {1} terminado(s)", { 0: s.count, 1: s.done })}>
                {s.skill}
                {mode === "detailed" && <span className="muted"> ×{s.count}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {items.loading ? (
        <Loading />
      ) : items.error ? (
        <ErrorBox message={items.error} onRetry={items.reload} />
      ) : grouped.length === 0 ? (
        <Card>
          <Empty icon="🧭" title={t("Tu trayectoria empieza aquí")}>
            {t("Apunta un curso, una certificación o un proyecto propio: lo que haces por tu cuenta también cuenta.")}
          </Empty>
        </Card>
      ) : (
        grouped
          .filter(([st]) => mode === "detailed" || st !== "dropped")
          .map(([st, list]) => (
            <Card key={st} title={PATH_STATUS[st]}>
              <ul className="path-list">
                {list.map((i) => (
                  <li key={i.id} className="path-item">
                    <span className="path-item__icon" aria-hidden>
                      {KIND_ICON[i.kind]}
                    </span>
                    <div>
                      <button type="button" className="link-btn path-item__title" onClick={() => setModal({ item: i })}>
                        {i.title}
                      </button>
                      <div className="muted small">
                        {PATH_KIND[i.kind]}
                        {i.organization && ` · ${i.organization}`}
                        {(i.start_date || i.end_date) && ` · ${fmtDate(i.start_date, true)} – ${i.end_date ? fmtDate(i.end_date, true) : "…"}`}
                        {i.hours !== null && ` · ${i.hours} h`}
                      </div>
                      {i.skills.length > 0 && (
                        <div className="tag-row">
                          {i.skills.map((s) => (
                            <span key={s} className="tag">
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          ))
      )}

      <Itinerary />

      <Modal open={modal === "new"} title={t("Añadir a la trayectoria")} onClose={() => setModal(null)}>
        <AutoForm<PathItemIn> fields={fields} initial={NEW_ITEM} onSubmit={(d) => api.path.create(d).then(close)} />
      </Modal>
      <Modal open={typeof modal === "object" && modal !== null} title={t("Trayectoria")} onClose={() => setModal(null)}>
        {typeof modal === "object" && modal !== null && (
          <>
            <AutoForm<PathItemIn> fields={fields} initial={modal.item} onSubmit={(d) => api.path.update(modal.item.id, d).then(close)} />
            <ConfirmDelete label={t("Borrar")} onConfirm={() => void api.path.remove(modal.item.id).then(close)} />
          </>
        )}
      </Modal>
    </div>
  );
}
