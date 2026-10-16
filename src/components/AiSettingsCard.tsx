import { useEffect, useState } from "react";
import { api, type AiProvider, type AiPublic } from "../api";
import { Card, ErrorBox, Field, FormStatus, Loading, useLoad, useSubmit } from "../ui";
import { t } from "../i18n";

const HELP: Record<AiProvider, string> = {
  claude_code:
    t("Usa tu propia suscripción de Claude: ejecuta `claude setup-token` en tu ordenador y pega aquí el token. Solo para tu propia instalación: no lo compartas ni lo uses para dar servicio a otras personas."),
  anthropic: t("Clave de API de Claude (console.anthropic.com). Se paga por uso."),
  gemini: t("Clave de API de Gemini (aistudio.google.com → Get API key). Tiene un nivel gratuito con límites."),
  openrouter: t("Clave de OpenRouter (openrouter.ai/keys). El modelo va como proveedor/modelo; openrouter/auto elige uno solo."),
  ollama: t("Modelos locales y gratuitos. Pon la dirección de tu servidor Ollama, accesible desde donde corre Campus Pilot, y el nombre del modelo (ollama list)."),
  openai_compatible: t("Cualquier otro servicio con API /chat/completions: LM Studio, vLLM… La URL suele acabar en /v1."),
};

/** Proveedor de IA para el generador de lecciones y la bandeja. La clave se escribe, nunca se lee. */
export function AiSettingsCard() {
  const q = useLoad(() => api.ai.get());
  const [form, setForm] = useState<{ provider: AiProvider | ""; base_url: string; model_generator: string; model_inbox: string }>({
    provider: "",
    base_url: "",
    model_generator: "",
    model_inbox: "",
  });
  const [key, setKey] = useState("");
  const [editingKey, setEditingKey] = useState(false);
  const save = useSubmit();
  const test = useSubmit();
  const removeKey = useSubmit();

  useEffect(() => {
    if (!q.data) return;
    setForm({ provider: q.data.provider ?? "", base_url: q.data.base_url, model_generator: q.data.model_generator, model_inbox: q.data.model_inbox });
  }, [q.data]);

  if (q.loading && !q.data) return <Card title={t("Inteligencia artificial")}><Loading /></Card>;
  if (q.error || !q.data) return <Card title={t("Inteligencia artificial")}><ErrorBox message={q.error ?? t("Error")} onRetry={q.reload} /></Card>;

  const data: AiPublic = q.data;
  const meta = form.provider ? data.providers[form.provider] : null;
  const st = data.status;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await save.run(
      () =>
        api.ai.save({
          provider: form.provider || null,
          base_url: form.base_url,
          model_generator: form.model_generator,
          model_inbox: form.model_inbox,
          key: key.trim() || undefined,
        }),
      t("Guardado")
    );
    if (res) {
      q.setData(res);
      setKey("");
      setEditingKey(false);
    }
  };

  return (
    <Card title={t("Inteligencia artificial")} className="ai-card">
      <p id="ia" className={`banner small ${st.enabled ? "banner--ok" : "banner--warn"}`} role="status">
        {st.enabled
          ? t("Activa: {0} · {1}{2}", { 0: data.providers[st.provider].label, 1: st.model, 2: st.source === "server" ? " (configurada en el servidor)" : "" })
          : t("Sin IA: {0}.", { 0: st.reason })}
      </p>
      <p className="muted small">
        {t("La usan el generador de lecciones y la clasificación de la bandeja. Cada instalación pone la suya. Al proveedor solo le llega el material que mandas a generar y los correos de la bandeja que se clasifican.")}
      </p>
      <form className="form" onSubmit={submit}>
        <div className="form-grid">
          <Field label={t("Proveedor")} wide>
            {(id) => (
              <select id={id} value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value as AiProvider | "" })}>
                <option value="">{t("Lo que traiga el servidor")}</option>
                {(Object.keys(data.providers) as AiProvider[]).map((p) => (
                  <option key={p} value={p}>
                    {data.providers[p].label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          {form.provider && <p className="muted small field--wide ai-card__help">{HELP[form.provider]}</p>}
          {meta?.needs_url && (
            <Field label={t("URL del servidor")} wide>
              {(id) => (
                <input id={id} type="url" inputMode="url" placeholder={meta.default_url} value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
              )}
            </Field>
          )}
          {meta && (
            <>
              <Field label={t("Modelo para generar lecciones")}>
                {(id) => <input id={id} placeholder={meta.models.generator || t("nombre del modelo")} value={form.model_generator}
                  onChange={(e) => setForm({ ...form, model_generator: e.target.value })} />}
              </Field>
              <Field label={t("Modelo para la bandeja (uno rápido basta)")}>
                {(id) => <input id={id} placeholder={meta.models.inbox || t("nombre del modelo")} value={form.model_inbox}
                  onChange={(e) => setForm({ ...form, model_inbox: e.target.value })} />}
              </Field>
            </>
          )}
          {form.provider && form.provider !== "ollama" && (
            <Field label={form.provider === "claude_code" ? t("Token de Claude Code") : t("Clave de API")} wide
              hint={form.provider === "openai_compatible" ? t("Opcional si tu servidor no la pide") : undefined}>
              {(id) =>
                data.has_key && !editingKey ? (
                  <div className="row-actions">
                    <span className="muted">{t("•••••••• guardada (cifrada)")}</span>
                    <button type="button" className="btn btn--ghost btn--sm" onClick={() => setEditingKey(true)}>
                      {t("Cambiar")}
                    </button>
                    <button type="button" className="btn btn--ghost btn--sm"
                      onClick={() => void removeKey.run(() => api.ai.removeKey(), t("Clave borrada")).then((r) => r && q.setData(r))}>
                      {t("Borrar")}
                    </button>
                  </div>
                ) : (
                  <input id={id} type="password" autoComplete="off" spellCheck={false} value={key} onChange={(e) => setKey(e.target.value)}
                    placeholder={form.provider === "claude_code" ? "sk-ant-oat…" : "sk-…"} />
                )
              }
            </Field>
          )}
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={save.state.status === "loading"}>
            {t("Guardar")}
          </button>
          <button type="button" className="btn btn--ghost" disabled={test.state.status === "loading" || !st.enabled}
            onClick={() => void test.run(() => api.ai.test(), t("Conexión correcta ✓"))}>
            {test.state.status === "loading" ? t("Probando…") : t("Probar conexión")}
          </button>
          <FormStatus state={save.state} />
          <FormStatus state={test.state.status === "loading" ? { status: "idle" } : test.state} />
          <FormStatus state={removeKey.state} />
        </div>
      </form>
    </Card>
  );
}
