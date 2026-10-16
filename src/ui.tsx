import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { t } from "./i18n";

export type UiMode = "minimal" | "detailed";

export const UiModeContext = createContext<UiMode>("minimal");
export const useUiMode = () => useContext(UiModeContext);

export function readStored<T extends string>(key: string, fallback: T, allowed: readonly T[]): T {
  try {
    const v = localStorage.getItem(key) as T | null;
    return v && allowed.includes(v) ? v : fallback;
  } catch {
    return fallback;
  }
}

export function writeStored(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* almacenamiento bloqueado: la preferencia vive solo en memoria */
  }
}

/** Carga asíncrona con estados loading/error y recarga manual. */
export function useLoad<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await loaderRef.current());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload, setData };
}

export type SubmitState = { status: "idle" | "loading" | "success" | "error"; message?: string };

/** Envuelve una acción de formulario con estados loading/success/error. */
export function useSubmit() {
  const [state, setState] = useState<SubmitState>({ status: "idle" });
  const run = useCallback(async <T,>(action: () => Promise<T>, successMessage = t("Guardado")): Promise<T | undefined> => {
    setState({ status: "loading" });
    try {
      const result = await action();
      setState({ status: "success", message: successMessage });
      return result;
    } catch (e) {
      setState({ status: "error", message: e instanceof Error ? e.message : String(e) });
      return undefined;
    }
  }, []);
  const reset = useCallback(() => setState({ status: "idle" }), []);
  return { state, run, reset };
}

export function FormStatus({ state }: { state: SubmitState }) {
  if (state.status === "idle") return null;
  if (state.status === "loading")
    return (
      <p className="form-status form-status--loading" role="status">
        {t("Guardando…")}
      </p>
    );
  return (
    <p className={`form-status form-status--${state.status}`} role={state.status === "error" ? "alert" : "status"}>
      {state.status === "success" ? "✓ " : "⚠ "}
      {state.message}
    </p>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted page-header__subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  );
}

export function Card({ title, children, actions, className = "" }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card__head">
          {title && <h2 className="card__title">{title}</h2>}
          {actions && <div className="card__actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Loading() {
  return (
    <p className="muted loading" role="status">
      {t("Cargando…")}
    </p>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-box" role="alert">
      <span>⚠ {message}</span>
      {onRetry && (
        <button type="button" className="btn btn--ghost btn--sm" onClick={onRetry}>
          {t("Reintentar")}
        </button>
      )}
    </div>
  );
}

export function Empty({ icon, title, children }: { icon: string; title: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon" aria-hidden>
        {icon}
      </div>
      <p className="empty-state__title">{title}</p>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

let fieldSeq = 0;
export function useFieldId(prefix = "f") {
  const ref = useRef<string>();
  if (!ref.current) ref.current = `${prefix}-${++fieldSeq}`;
  return ref.current;
}

export function Field({ label, hint, children, wide }: { label: string; hint?: string; children: (id: string) => ReactNode; wide?: boolean }) {
  const id = useFieldId();
  return (
    <div className={`field${wide ? " field--wide" : ""}`}>
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <small className="muted">{hint}</small>}
    </div>
  );
}

/** Diálogo modal accesible basado en <dialog> (foco atrapado y Escape nativos). */
export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) dlg.showModal();
    if (!open && dlg.open) dlg.close();
  }, [open]);
  return (
    <dialog ref={ref} className="modal" onClose={onClose} aria-label={title}>
      <div className="modal__head">
        <h2>{title}</h2>
        <button type="button" className="icon-btn" onClick={onClose} aria-label={t("Cerrar")}>
          ✕
        </button>
      </div>
      {open && <div className="modal__body">{children}</div>}
    </dialog>
  );
}

export function ConfirmDelete({ onConfirm, label = t("Borrar") }: { onConfirm: () => void; label?: string }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = window.setTimeout(() => setArmed(false), 4000);
    return () => window.clearTimeout(t);
  }, [armed]);
  return (
    <button
      type="button"
      className={`btn btn--sm ${armed ? "btn--danger" : "btn--ghost"}`}
      onClick={() => (armed ? onConfirm() : setArmed(true))}
    >
      {armed ? t("¿Seguro? Pulsa otra vez") : label}
    </button>
  );
}

export function ProgressBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : value > 0 ? 100 : 0;
  return (
    <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
      <div className={`progress__fill${pct >= 100 ? " is-done" : ""}`} style={{ width: `${pct}%` }} />
    </div>
  );
}
