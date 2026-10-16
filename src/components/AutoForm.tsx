import { useState } from "react";
import { numOrNull } from "../lib/format";
import { Field, FormStatus, useSubmit } from "../ui";
import { t } from "../i18n";

export type FieldDef<T> =
  | { key: keyof T & string; label: string; type: "text" | "url" | "textarea"; required?: boolean; max?: number; wide?: boolean; hint?: string; placeholder?: string }
  | { key: keyof T & string; label: string; type: "number"; required?: boolean; min?: number; max?: number; step?: number; nullable?: boolean; hint?: string }
  | { key: keyof T & string; label: string; type: "date"; required?: boolean; hint?: string }
  | { key: keyof T & string; label: string; type: "checkbox"; hint?: string }
  | { key: keyof T & string; label: string; type: "select"; options: Array<[string, string]>; nullable?: boolean; numeric?: boolean; hint?: string }
  | { key: keyof T & string; label: string; type: "tags"; hint?: string; wide?: boolean };

/** Formulario a partir de una lista de campos. Cubre los recursos "planos" (gastos, becas,
 *  trámites, trayectoria) con estados loading/success/error y validación nativa. */
export function AutoForm<T extends Record<string, unknown>>({
  fields,
  initial,
  onSubmit,
  submitLabel = t("Guardar"),
}: {
  fields: FieldDef<T>[];
  initial: T;
  onSubmit: (data: T) => Promise<unknown>;
  submitLabel?: string;
}) {
  const [form, setForm] = useState<T>(initial);
  const [tagDraft, setTagDraft] = useState<Record<string, string>>({});
  const { state, run } = useSubmit();
  const set = (key: string, value: unknown) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Etiquetas escritas pero sin confirmar con Enter: también cuentan.
    let data = form;
    for (const [key, draft] of Object.entries(tagDraft)) {
      const extra = draft.split(",").map((s) => s.trim()).filter(Boolean);
      if (extra.length) data = { ...data, [key]: [...((data[key] as string[]) ?? []), ...extra] };
    }
    await run(() => onSubmit(data));
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="form-grid">
        {fields.map((f) => {
          const value = form[f.key];
          const wide = "wide" in f && f.wide;
          return (
            <Field key={f.key} label={f.label} hint={f.hint} wide={wide || f.type === "textarea"}>
              {(id) => {
                switch (f.type) {
                  case "textarea":
                    return <textarea id={id} rows={3} maxLength={f.max} required={f.required} value={(value as string) ?? ""} onChange={(e) => set(f.key, e.target.value)} />;
                  case "text":
                  case "url":
                    return (
                      <input id={id} type={f.type} maxLength={f.max} required={f.required} placeholder={f.placeholder}
                        value={(value as string) ?? ""} onChange={(e) => set(f.key, e.target.value)} />
                    );
                  case "number":
                    return (
                      <input id={id} type="number" min={f.min} max={f.max} step={f.step ?? "any"} required={f.required}
                        value={value === null || value === undefined ? "" : String(value)}
                        onChange={(e) => set(f.key, f.nullable ? numOrNull(e.target.value) : Number(e.target.value))} />
                    );
                  case "date":
                    return <input id={id} type="date" required={f.required} value={(value as string) ?? ""} onChange={(e) => set(f.key, e.target.value || null)} />;
                  case "checkbox":
                    return <input id={id} type="checkbox" checked={Boolean(value)} onChange={(e) => set(f.key, e.target.checked)} />;
                  case "select":
                    return (
                      <select id={id} value={value === null || value === undefined ? "" : String(value)}
                        onChange={(e) => set(f.key, e.target.value === "" ? null : f.numeric ? Number(e.target.value) : e.target.value)}>
                        {f.nullable && <option value="">—</option>}
                        {f.options.map(([v, label]) => (
                          <option key={v} value={v}>
                            {label}
                          </option>
                        ))}
                      </select>
                    );
                  case "tags": {
                    const tags = (value as string[]) ?? [];
                    const commit = () => {
                      const extra = (tagDraft[f.key] ?? "").split(",").map((s) => s.trim()).filter(Boolean);
                      if (extra.length) set(f.key, [...tags, ...extra]);
                      setTagDraft((d) => ({ ...d, [f.key]: "" }));
                    };
                    return (
                      <div className="tags-input">
                        {tags.map((tag) => (
                          <span key={tag} className="tag">
                            {tag}
                            <button type="button" className="tag__x" aria-label={t("Quitar {0}", { 0: tag })} onClick={() => set(f.key, tags.filter((x) => x !== tag))}>
                              ✕
                            </button>
                          </span>
                        ))}
                        <input id={id} placeholder={t("Escribe y pulsa Enter")} value={tagDraft[f.key] ?? ""}
                          onChange={(e) => setTagDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === ",") {
                              e.preventDefault();
                              commit();
                            }
                          }}
                          onBlur={commit} />
                      </div>
                    );
                  }
                }
              }}
            </Field>
          );
        })}
      </div>
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={state.status === "loading"}>
          {submitLabel}
        </button>
        <FormStatus state={state} />
      </div>
    </form>
  );
}
