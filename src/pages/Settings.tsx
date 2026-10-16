import { useEffect, useState } from "react";
import { api, type Settings } from "../api";
import { AiSettingsCard } from "../components/AiSettingsCard";
import { CalendarFeedsCard } from "../components/CalendarFeeds";
import { LanguageSelect } from "../components/LanguageSelect";
import { useStore } from "../store";
import { Card, ErrorBox, Field, FormStatus, Loading, PageHeader, useLoad, useSubmit } from "../ui";
import { t } from "../i18n";

export function SettingsPage() {
  const { settings, saveSettings, reload } = useStore();
  const [form, setForm] = useState<Settings | null>(settings);
  const { state, run } = useSubmit();
  const restore = useSubmit();
  const test = useSubmit();
  const status = useLoad(() => api.notifications.status());
  const preview = useLoad(() => api.notifications.preview());
  const [daysText, setDaysText] = useState("");

  useEffect(() => {
    setForm(settings);
    if (settings) setDaysText(settings.notifications.days_before.join(", "));
  }, [settings]);

  if (!form) return <Loading />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const days = daysText
      .split(/[,\s]+/)
      .map((d) => Number(d))
      .filter((d) => Number.isInteger(d) && d >= 0);
    await run(() => saveSettings({ ...form, notifications: { ...form.notifications, days_before: days } }));
  };

  const onRestore = async (file: File | undefined) => {
    if (!file) return;
    if (!window.confirm(t("Restaurar sustituye TODOS los datos actuales por los de la copia. ¿Seguir?"))) return;
    if (await restore.run(() => api.restoreBackup(file), t("Copia restaurada"))) await reload();
  };

  const n = form.notifications;
  return (
    <div className="page">
      <PageHeader title={t("Ajustes")} />
      <form onSubmit={submit} className="stack">
        <Card title={t("General")}>
          <div className="form-grid">
            <LanguageSelect />
            <Field label={t("Precio por crédito por defecto")} hint={t("Para estimar la matrícula")}>
              {(id) => (
                <input id={id} type="number" min={0} step={0.01} value={form.default_price_per_credit}
                  onChange={(e) => setForm({ ...form, default_price_per_credit: Number(e.target.value) || 0 })} />
              )}
            </Field>
            <Field label={t("Moneda")}>
              {(id) => (
                <input id={id} maxLength={3} minLength={3} pattern="[A-Za-z]{3}" value={form.currency}
                  onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} />
              )}
            </Field>
            <Field label={t("Semana cargada (▲) desde")} hint={t("Entregas de al menos tantas asignaturas distintas")}>
              {(id) => (
                <input id={id} type="number" min={2} max={10} value={form.heavy_week_subjects}
                  onChange={(e) => setForm({ ...form, heavy_week_subjects: Number(e.target.value) || 2 })} />
              )}
            </Field>
            <Field label={t("Bóveda de Obsidian")} hint={t("Nombre exacto, para enlazar tus apuntes desde cada asignatura")}>
              {(id) => <input id={id} maxLength={120} value={form.obsidian_vault} onChange={(e) => setForm({ ...form, obsidian_vault: e.target.value })} />}
            </Field>
          </div>
        </Card>

        <Card title={t("Avisos (ntfy)")}>
          {status.data && !status.data.configured && (
            <p className="text-warn small">{t("El servidor no tiene ntfy configurado (CAMPUS_NTFY_URL): los avisos no saldrán.")}</p>
          )}
          <div className="form-grid">
            <Field label={t("Resumen diario")}>
              {(id) => (
                <input id={id} type="checkbox" checked={n.enabled}
                  onChange={(e) => setForm({ ...form, notifications: { ...n, enabled: e.target.checked } })} />
              )}
            </Field>
            <Field label={t("Topic")}>
              {(id) => (
                <input id={id} maxLength={64} pattern="[A-Za-z0-9_-]+" required value={n.topic}
                  onChange={(e) => setForm({ ...form, notifications: { ...n, topic: e.target.value } })} />
              )}
            </Field>
            <Field label={t("Hora")}>
              {(id) => (
                <input id={id} type="number" min={0} max={23} value={n.hour}
                  onChange={(e) => setForm({ ...form, notifications: { ...n, hour: Number(e.target.value) } })} />
              )}
            </Field>
            <Field label={t("Avisar de entregas con … días")} hint={t("Separados por comas: 7, 3, 1, 0")}>
              {(id) => <input id={id} value={daysText} onChange={(e) => setDaysText(e.target.value)} />}
            </Field>
          </div>
          {preview.data && (
            <details className="details">
              <summary>{t("Así sería el aviso de hoy")}</summary>
              {preview.data.lines.length ? (
                <ul className="plain-list small">
                  {preview.data.lines.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted small">{t("Hoy no habría nada que contar.")}</p>
              )}
            </details>
          )}
          <button type="button" className="btn btn--ghost btn--sm" disabled={!status.data?.configured}
            onClick={() => void test.run(() => api.notifications.test(), t("Enviado"))}>
            {t("Enviar una prueba")}
          </button>
          <FormStatus state={test.state} />
        </Card>

        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={state.status === "loading"}>
            {t("Guardar ajustes")}
          </button>
          <FormStatus state={state} />
        </div>
      </form>

      <AiSettingsCard />

      <CalendarFeedsCard />

      <Card title={t("Copia de seguridad")}>
        <p className="small">{t("Todo en un JSON: carreras, notas, agenda, estudio, dinero y trayectoria.")}</p>
        <div className="form-actions">
          <a className="btn btn--ghost" href={api.backupUrl} download>
            {t("⬇ Descargar copia")}
          </a>
          <label className="btn btn--ghost file-btn">
            {t("⬆ Restaurar copia")}
            <input type="file" accept="application/json,.json" className="sr-only" onChange={(e) => void onRestore(e.target.files?.[0])} />
          </label>
        </div>
        {restore.state.status === "error" && <ErrorBox message={restore.state.message ?? t("Error")} />}
        <FormStatus state={restore.state} />
      </Card>
    </div>
  );
}
