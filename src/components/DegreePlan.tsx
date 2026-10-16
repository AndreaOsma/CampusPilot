import { useState } from "react";
import { api, type GenerationJob } from "../api";
import { SUBJECT_KIND } from "../lib/format";
import { linkTo, type Navigate } from "../router";
import { useStore } from "../store";
import { Card, Field, FormStatus, PageHeader, useSubmit } from "../ui";
import { t } from "../i18n";
import { useJobWatch } from "./Syllabus";

/** Módulos: crear la carrera desde el plan de estudios oficial (lo lee la IA de Ajustes). */
export function DegreePlanCard({ navigate }: { navigate: Navigate }) {
  const [file, setFile] = useState<File | null>(null);
  const { state, run } = useSubmit();
  const { job, watch, watching } = useJobWatch((j) => {
    if (j.status === "done") navigate({ name: "draft", id: j.id });
  });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const res = await run(() => api.degreePlan(file), t("Leyendo el plan de estudios: tarda un par de minutos"));
    if (res) watch(res.id);
  };
  return (
    <Card title={t("Crear tu carrera desde el plan de estudios")}>
      <p className="muted small">
        {t("Sube el plan de estudios oficial de tu titulación (PDF, o la página web guardada como HTML) y la IA configurada en Ajustes saca las asignaturas, créditos, tipos, semestres y menciones. Lo revisas, se crea la carrera y puedes descargar el módulo para compartirlo con tu universidad.")}
      </p>
      <form className="form" onSubmit={submit}>
        <div className="form-grid">
          <Field label={t("Plan de estudios")} wide>
            {(id) => <input id={id} type="file" accept=".pdf,.md,.txt,.html,.htm,application/pdf,text/markdown,text/plain,text/html" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
          </Field>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={!file || watching || state.status === "loading"}>
            {watching ? t("Leyendo…") : t("✨ Leer plan de estudios")}
          </button>
          <FormStatus state={state} />
          {job?.status === "error" && <p className="small text-crit">{job.error}</p>}
        </div>
      </form>
    </Card>
  );
}

/** Revisión del módulo de estudios que salió del plan de estudios. */
export function DegreeReview({ job, navigate }: { job: GenerationJob; navigate: Navigate }) {
  const pack = job.draft?.pack;
  const { reload } = useStore();
  const { state, run } = useSubmit();
  if (!pack) return null;
  const credit = pack.config?.credit_label ?? "ECTS";
  const bySemester = new Map<string, typeof pack.subjects>();
  for (const s of pack.subjects) {
    const key = s.plan_semester ? t("Semestre {0}", { 0: s.plan_semester }) : t("Sin semestre");
    bySemester.set(key, [...(bySemester.get(key) ?? []), s]);
  }
  const download = () => {
    const blob = new Blob([JSON.stringify({ ...pack, format: "campus-pilot-pack", format_version: 1 }, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${pack.slug}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const apply = async () => {
    const res = await run(() => api.learn.importJob(job.id, { subject_id: null, exclude: [] }), t("Carrera creada"));
    if (res) {
      await reload();
      navigate({ name: "career" });
    }
  };
  const tracks = new Map(pack.tracks.map((x) => [x.id, x.name]));
  return (
    <div className="page">
      <PageHeader
        title={pack.degree}
        subtitle={`${pack.institution ? `${pack.institution} · ` : ""}${pack.ects_total} ${credit} · ${t("{0} asignaturas", { 0: pack.subjects.length })}`}
        actions={
          <a className="btn btn--ghost" href="/modulos" onClick={linkTo(navigate, { name: "modules" })}>
            {t("← Módulos")}
          </a>
        }
      />
      <p className="banner banner--warn small">{t("Lo ha extraído una IA del plan de estudios: compáralo con el original antes de crear la carrera.")}</p>
      {(job.warnings ?? []).length > 0 && (
        <p className="muted small">{t("Descartado: {0}", { 0: (job.warnings ?? []).map((w) => `${w.lesson || w.step} (${w.message})`).join(" · ") })}</p>
      )}
      {Object.keys(pack.requirements).length > 0 && (
        <Card title={t("Créditos para titularse")}>
          <ul className="plain-list small">
            {Object.entries(pack.requirements).map(([k, v]) => (
              <li key={k}>
                {SUBJECT_KIND[k as keyof typeof SUBJECT_KIND] ?? k}: <strong>{v}</strong> {credit}
              </li>
            ))}
          </ul>
        </Card>
      )}
      {[...bySemester.entries()].map(([label, list]) => (
        <Card key={label} title={label}>
          <ul className="plain-list small">
            {list.map((s) => (
              <li key={s.ref}>
                {s.code && <span className="muted">{s.code} · </span>}
                <strong>{s.name}</strong> · {s.ects} {credit} · {SUBJECT_KIND[s.kind] ?? s.kind}
                {s.track && ` · ${tracks.get(s.track) ?? s.track}`}
              </li>
            ))}
          </ul>
        </Card>
      ))}
      <Card title={t("Crear la carrera")}>
        <div className="form-actions">
          <button type="button" className="btn btn--primary" disabled={state.status === "loading"} onClick={() => void apply()}>
            {t("Crear la carrera")}
          </button>
          <button type="button" className="btn btn--ghost" onClick={download}>
            {t("⬇ Descargar módulo (.json)")}
          </button>
          <FormStatus state={state} />
        </div>
      </Card>
    </div>
  );
}
