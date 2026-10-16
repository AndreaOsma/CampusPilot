import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { setLocale } from "./i18n";
import { api, type Career, type Settings, type Subject, type Term } from "./api";
import { todayIso } from "./lib/format";

type Store = {
  settings: Settings | null;
  careers: Career[];
  subjects: Subject[];
  terms: Term[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  saveSettings: (s: Settings) => Promise<Settings>;
  subjectName: (id: number | null | undefined) => string;
  currentTerm: Term | null;
};

const StoreContext = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [careers, setCareers] = useState<Career[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const [s, c, sub, t] = await Promise.all([api.settings.get(), api.careers.list(), api.subjects.list(), api.terms.list()]);
      setLocale(s.language ?? "es");
      setSettings(s);
      setCareers(c);
      setSubjects(sub);
      setTerms(t);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const saveSettings = useCallback(async (s: Settings) => {
    const saved = await api.settings.save(s);
    setLocale(saved.language ?? "es");
    setSettings(saved);
    return saved;
  }, []);

  const value = useMemo<Store>(() => {
    const names = new Map(subjects.map((s) => [s.id, s.name]));
    const today = todayIso();
    // Semestre en curso: el que contiene hoy; si no, el último que ya empezó; si no, el primero.
    const sorted = [...terms].sort((a, b) => a.start_date.localeCompare(b.start_date));
    const currentTerm =
      sorted.find((t) => t.start_date <= today && (!t.end_date || t.end_date >= today)) ??
      [...sorted].reverse().find((t) => t.start_date <= today) ??
      sorted[0] ??
      null;
    return {
      settings,
      careers,
      subjects,
      terms,
      loading,
      error,
      reload,
      saveSettings,
      subjectName: (id) => (id ? names.get(id) ?? "Asignatura borrada" : ""),
      currentTerm,
    };
  }, [settings, careers, subjects, terms, loading, error, reload, saveSettings]);

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore fuera de StoreProvider");
  return ctx;
}
