import { useState } from "react";
import { api, type ModuleId, type PackSummary } from "../api";
import { DegreePlanCard } from "../components/DegreePlan";
import { fmtDate } from "../lib/format";
import { linkTo, type Navigate } from "../router";
import { useStore } from "../store";
import { Card, Empty, ErrorBox, FormStatus, Loading, PageHeader, useLoad, useSubmit } from "../ui";
import { t } from "../i18n";

const FEATURES: Array<{ id: ModuleId; icon: string; name: string; description: string }> = [
  { id: "semestre", icon: "🗓️", name: "Semestre", description: t("Agenda de entregas y ventanas, semanas cargadas ▲, eventos, hábitos, feed iCal y avisos.") },
  { id: "aprender", icon: "🎯", name: "Aprender", description: t("Lecciones paso a paso con ejercicios corregidos al momento, racha, XP y repaso de lo fallado.") },
  { id: "estudio", icon: "🧠", name: "Estudio", description: t("Temporizador focus, horas reales frente a previstas y preguntas de repaso espaciado.") },
  { id: "dinero", icon: "💶", name: "Dinero y trámites", description: t("Gastos, matrícula estimada, becas (con la media que piden) y trámites con plazo.") },
  { id: "trayectoria", icon: "🧭", name: "Trayectoria", description: t("Cursos, certificaciones, proyectos, prácticas e idiomas, con sus competencias.") },
  { id: "bandeja", icon: "📥", name: "Bandeja de la universidad", description: t("Correos de la universidad reenviados a la app, clasificados por asignatura, con las fechas que traen como propuestas para la agenda.") },
];

function PackCard({ pack, onChange, navigate }: { pack: PackSummary; onChange: () => void; navigate: Navigate }) {
  const { reload } = useStore();
  const { state, run } = useSubmit();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const installed = pack.installed_version !== null;
  const outdated = installed && pack.in_catalog && pack.installed_version !== pack.version;

  const act = async (action: () => Promise<unknown>, message: string) => {
    if (await run(action, message)) {
      await reload();
      onChange();
    }
  };

  return (
    <Card
      className="pack-card"
      title={
        <>
          {pack.name} {installed && <span className="tag tag--ok">{t("instalado")}</span>} {outdated && <span className="tag">{t("actualización disponible")}</span>}
        </>
      }
    >
      {pack.description && <p className="small detail-only">{pack.description}</p>}
      <p className="muted small detail-only">
        {pack.institution && `${pack.institution} · `}
        {pack.ects_total} {pack.credit_label ?? "ECTS"} · {pack.subjects} {t("asignaturas")}
        {pack.tracks.length > 0 && ` · ${pack.tracks.map((t) => t.name).join(" / ")}`}
        {pack.updated && t(" · actualizado el {0}", { 0: fmtDate(pack.updated, true) })}
        {pack.source_url && (
          <>
            {" · "}
            <a href={pack.source_url} target="_blank" rel="noreferrer">
              {t("fuente oficial")}
            </a>
          </>
        )}
      </p>
      <div className="form-actions">
        <button
          type="button"
          className={`btn ${installed && !outdated ? "btn--ghost" : "btn--primary"}`}
          disabled={state.status === "loading"}
          onClick={() => void act(() => api.packs.install(pack.slug), installed ? t("Actualizado") : t("Instalado"))}
        >
          {installed ? (outdated ? t("Actualizar") : t("Reinstalar")) : t("Instalar")}
        </button>
        {pack.career_id && (
          <a className="btn btn--ghost" href="/expediente" onClick={linkTo(navigate, { name: "career" })}>
            {t("Ver expediente")}
          </a>
        )}
        <a className="btn btn--ghost" href={api.packs.downloadUrl(pack.slug)} download={`${pack.slug}.json`}>
          {t("⬇ JSON")}
        </a>
      </div>

      {installed && pack.terms.length > 0 && (
        <div className="pack-terms">
          <h3 className="small">{t("Semestres con calendario")}</h3>
          <ul className="plain-list">
            {pack.terms.map((term) => (
              <li key={term.ref} className="row-list__item">
                <span>
                  <strong>{term.label}</strong> <span className="muted small">· {term.subjects} {t("asignaturas")} {term.applied && t("· aplicado ✓")}</span>
                </span>
                <button
                  type="button"
                  className="btn btn--ghost btn--sm"
                  disabled={state.status === "loading"}
                  onClick={() =>
                    void act(
                      () => api.packs.applyTerm(pack.slug, term.ref).then((r) => r),
                      term.applied ? t("Fechas actualizadas (tus notas no se tocan)") : t("Semestre aplicado: asignaturas matriculadas y calendario añadido")
                    )
                  }
                >
                  {term.applied ? t("Actualizar fechas") : t("Me he matriculado: aplicar")}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {installed && (
        <div className="pack-danger detail-only">
          {confirmDelete ? (
            <div className="inline-form">
              <span className="small">{t("¿Borrar también la carrera y todo lo tuyo dentro (notas, actividades)?")}</span>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => void act(() => api.packs.uninstall(pack.slug, false), t("Desinstalado (tu carrera se queda)"))}>
                {t("No, conservar la carrera")}
              </button>
              <button type="button" className="btn btn--danger btn--sm" onClick={() => void act(() => api.packs.uninstall(pack.slug, true), t("Desinstalado y borrado"))}>
                {t("Sí, borrar todo")}
              </button>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setConfirmDelete(false)}>
                {t("Cancelar")}
              </button>
            </div>
          ) : (
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setConfirmDelete(true)}>
              {t("Desinstalar")}
            </button>
          )}
        </div>
      )}
      <FormStatus state={state} />
    </Card>
  );
}

export function Modules({ navigate }: { navigate: Navigate }) {
  const { settings, saveSettings } = useStore();
  const packs = useLoad(() => api.packs.list());
  const toggle = useSubmit();
  const uploadState = useSubmit();
  const { reload } = useStore();

  const setFeature = (id: ModuleId, on: boolean) => {
    if (!settings) return;
    void toggle.run(() => saveSettings({ ...settings, modules: { ...settings.modules, [id]: on } }), on ? t("Activado") : t("Desactivado"));
  };

  const onUpload = async (file: File | undefined) => {
    if (!file) return;
    if (await uploadState.run(() => api.packs.upload(file), t("Módulo instalado"))) {
      await reload();
      void packs.reload();
    }
  };

  return (
    <div className="page">
      <PageHeader title={t("Módulos")} subtitle={t("Usa solo lo que te sirva. El expediente va siempre; el resto se enciende y se apaga.")} />

      <Card title={t("Funciones")}>
        <ul className="feature-list">
          {FEATURES.map((f) => (
            <li key={f.id} className="feature">
              <span className="feature__icon" aria-hidden>
                {f.icon}
              </span>
              <div className="feature__body">
                <label className="feature__name" htmlFor={`feat-${f.id}`}>
                  {f.name}
                </label>
                <p className="muted small detail-only">{f.description}</p>
              </div>
              <input
                id={`feat-${f.id}`}
                type="checkbox"
                role="switch"
                className="switch"
                checked={settings?.modules[f.id] !== false}
                onChange={(e) => setFeature(f.id, e.target.checked)}
              />
            </li>
          ))}
        </ul>
        <FormStatus state={toggle.state} />
      </Card>

      <h2 className="section-title">{t("Módulos de estudios")}</h2>
      <p className="muted small detail-only">
        {t("Lo específico de una titulación (plan de estudios, reglas de evaluación, política de IA de cada asignatura, calendario de un semestre) viene en un módulo que instalas si te sirve. Puedes exportar tu propia carrera como módulo desde el expediente y compartirla.")}
      </p>

      {packs.loading ? (
        <Loading />
      ) : packs.error ? (
        <ErrorBox message={packs.error} onRetry={packs.reload} />
      ) : (packs.data ?? []).length === 0 ? (
        <Card>
          <Empty icon="🧩" title={t("No hay módulos en el catálogo de este servidor")} />
        </Card>
      ) : (
        (packs.data ?? []).map((p) => <PackCard key={p.slug} pack={p} onChange={() => void packs.reload()} navigate={navigate} />)
      )}

      <DegreePlanCard navigate={navigate} />

      <Card title={t("Instalar un módulo desde archivo")}>
        <label className="btn btn--ghost file-btn">
          {t("⬆ Elegir .json")}
          <input type="file" accept="application/json,.json" className="sr-only" onChange={(e) => void onUpload(e.target.files?.[0])} />
        </label>
        <FormStatus state={uploadState.state} />
      </Card>
    </div>
  );
}
