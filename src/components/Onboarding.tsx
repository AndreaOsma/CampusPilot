import { useState } from "react";
import { api, type CareerConfig, type CareerIn } from "../api";
import { DEFAULT_CONFIG, rulesOf } from "../lib/rules";
import { type Navigate } from "../router";
import { useStore } from "../store";
import { Card, Field, FormStatus, Loading, PageHeader, useLoad, useSubmit } from "../ui";
import { AiSettingsCard } from "./AiSettingsCard";
import { CareerRulesFields } from "./CareerRulesFields";
import { LanguageSelect } from "./LanguageSelect";
import { t } from "../i18n";

type Step = "university" | "rules" | "ai" | "done";
const STEPS: { id: Step; label: string }[] = [
  { id: "university", label: t("Tu universidad") },
  { id: "rules", label: t("Sus reglas") },
  { id: "ai", label: t("IA (opcional)") },
  { id: "done", label: t("Listo") },
];

/** Primer arranque: universidad (módulo del catálogo, archivo o a mano) → reglas → IA → listo. */
export function Onboarding({ navigate }: { navigate: Navigate }) {
  const { reload } = useStore();
  const catalog = useLoad(() => api.packs.list());
  const [step, setStep] = useState<Step>("university");
  const [careerId, setCareerId] = useState<number | null>(null);
  const [manual, setManual] = useState<CareerIn>({
    name: "",
    institution: "",
    ects_goal: 240,
    track: null,
    requirements: {},
    config: DEFAULT_CONFIG,
    archived: false,
  });
  const [rules, setRules] = useState<CareerConfig>(DEFAULT_CONFIG);
  const install = useSubmit();
  const save = useSubmit();

  const afterCareer = async (id: number) => {
    setCareerId(id);
    const career = await api.careers.get(id);
    setRules(rulesOf(career));
    setStep("rules");
  };

  const fromPack = async (slug: string) => {
    const res = await install.run(() => api.packs.install(slug), t("Instalado"));
    if (res) await afterCareer(res.career_id);
  };
  const fromFile = async (file: File | undefined) => {
    if (!file) return;
    const res = await install.run(() => api.packs.upload(file), t("Instalado"));
    if (res) await afterCareer(res.career_id);
  };
  const createManual = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await install.run(() => api.careers.create(manual), t("Carrera creada"));
    if (res) await afterCareer(res.id);
  };
  const saveRules = async () => {
    if (!careerId) return;
    const career = await api.careers.get(careerId);
    const { id: _id, pack_slug: _p, tracks: _t, ...rest } = career;
    const res = await save.run(() => api.careers.update(careerId, { ...rest, config: rules }), t("Guardado"));
    if (res) setStep("ai");
  };
  // La tienda se recarga al salir: si se recargara antes, Hoy dejaría de enseñar el asistente.
  const go = async (e: React.MouseEvent, to: Parameters<Navigate>[0]) => {
    e.preventDefault();
    await reload();
    navigate(to);
  };

  const idx = STEPS.findIndex((s) => s.id === step);
  return (
    <div className="page onboarding">
      <PageHeader title={t("Te damos la bienvenida a Campus Pilot")} subtitle={t("Tu centro de mando para la carrera. Lo dejamos listo en un minuto.")} />
      <div className="onboarding__lang">
        <LanguageSelect />
      </div>
      <ol className="onboarding__steps" aria-label={t("Pasos")}>
        {STEPS.map((s, i) => (
          <li key={s.id} className={i < idx ? "is-done" : i === idx ? "is-current" : ""} aria-current={i === idx ? "step" : undefined}>
            <span className="onboarding__n" aria-hidden>
              {i < idx ? "✓" : i + 1}
            </span>
            {s.label}
          </li>
        ))}
      </ol>

      {step === "university" && (
        <>
          <Card title={t("¿Hay un módulo de tu titulación?")}>
            <p className="muted small">{t("Un módulo trae el plan de estudios, las reglas de evaluación y el calendario. Se instala en un clic.")}</p>
            {catalog.loading ? (
              <Loading />
            ) : (catalog.data ?? []).length === 0 ? (
              <p className="muted">{t("Este servidor no trae ninguno: sube el tuyo o crea la carrera a mano.")}</p>
            ) : (
              <ul className="row-list">
                {(catalog.data ?? []).map((p) => (
                  <li key={p.slug} className="row-list__item">
                    <div>
                      <strong>{p.degree || p.name}</strong>
                      <div className="muted small">
                        {p.institution} · {p.ects_total} {p.credit_label ?? "ECTS"} · {p.subjects} {t("asignaturas")}
                      </div>
                    </div>
                    <button type="button" className="btn btn--primary btn--sm" disabled={install.state.status === "loading"} onClick={() => void fromPack(p.slug)}>
                      {t("Instalar")}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <label className="btn btn--ghost file-btn">
              {t("⬆ Subir un módulo (.json)")}
              <input type="file" accept="application/json,.json" className="sr-only" onChange={(e) => void fromFile(e.target.files?.[0])} />
            </label>
            <FormStatus state={install.state} />
          </Card>
          <Card title={t("O créala a mano")}>
            <p className="muted small">
              {t("¿Tienes el plan de estudios oficial de tu titulación? Cuando configures la IA, en Módulos → Crear tu carrera desde el plan de estudios se crea entera con sus asignaturas.")}
            </p>
            <form className="form" onSubmit={createManual}>
              <div className="form-grid">
                <Field label={t("Titulación")} wide>
                  {(id) => <input id={id} required maxLength={200} value={manual.name} onChange={(e) => setManual({ ...manual, name: e.target.value })} />}
                </Field>
                <Field label={t("Universidad")} wide>
                  {(id) => <input id={id} maxLength={200} value={manual.institution} onChange={(e) => setManual({ ...manual, institution: e.target.value })} />}
                </Field>
                <Field label={t("Créditos totales")}>
                  {(id) => (
                    <input id={id} type="number" min={1} max={1000} required value={manual.ects_goal}
                      onChange={(e) => setManual({ ...manual, ects_goal: Number(e.target.value) })} />
                  )}
                </Field>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn--primary" disabled={install.state.status === "loading"}>
                  {t("Seguir")}
                </button>
              </div>
            </form>
          </Card>
        </>
      )}

      {step === "rules" && (
        <Card title={t("Comprueba que cuadran")}>
          <p className="muted small">{t("Así las notas, el «¿cuánto necesito?» y tu plan de periodos salen bien. Lo puedes cambiar luego en el expediente.")}</p>
          <CareerRulesFields value={rules} onChange={setRules} />
          <div className="form-actions">
            <button type="button" className="btn btn--primary" disabled={save.state.status === "loading"} onClick={() => void saveRules()}>
              {t("Seguir")}
            </button>
            <FormStatus state={save.state} />
          </div>
        </Card>
      )}

      {step === "ai" && (
        <>
          <AiSettingsCard />
          <div className="form-actions">
            <button type="button" className="btn btn--primary" onClick={() => setStep("done")}>
              {t("Seguir")}
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setStep("done")}>
              {t("Ahora no")}
            </button>
          </div>
        </>
      )}

      {step === "done" && (
        <Card title={t("¡Listo!")}>
          <p>{t("Ya tienes tu carrera. Lo siguiente:")}</p>
          <div className="form-actions">
            <a className="btn btn--primary" href="/expediente" onClick={(e) => void go(e, { name: "career" })}>
              {t("🎓 Ver mi expediente")}
            </a>
            <a className="btn btn--ghost" href="/aprender" onClick={(e) => void go(e, { name: "learn" })}>
              {t("🎯 Aprender")}
            </a>
          </div>
        </Card>
      )}
    </div>
  );
}
