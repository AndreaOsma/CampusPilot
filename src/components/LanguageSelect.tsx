import { LOCALES, locale, setLocale, t, type Locale } from "../i18n";
import { useStore } from "../store";
import { Field } from "../ui";

/** Cambia el idioma, lo guarda en Ajustes y recarga para que todo salga ya traducido. */
export function LanguageSelect() {
  const { settings, saveSettings } = useStore();
  const change = async (l: Locale) => {
    setLocale(l);
    if (settings) await saveSettings({ ...settings, language: l }).catch(() => null);
    window.location.reload();
  };
  return (
    <Field label={t("Idioma")}>
      {(id) => (
        <select id={id} value={locale()} onChange={(e) => void change(e.target.value as Locale)}>
          {(Object.keys(LOCALES) as Locale[]).map((l) => (
            <option key={l} value={l} lang={l}>
              {LOCALES[l]}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}
