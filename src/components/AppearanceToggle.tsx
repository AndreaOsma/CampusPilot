import { useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import { Check, Icon, Moon, Sun, SunMoon } from "../vendor/icons";

type DayNightMode = "day" | "night" | "auto";

type Props = {
  value: DayNightMode;
  onChange: (mode: DayNightMode) => void;
};

// Selector de tema (AGENTS.md): el botón lleva el icono del tema activo y el menú, icono + texto con el
// elegido marcado. Iconos de lib/icons/ui vía src/vendor/icons.
const OPTIONS: Array<{ id: DayNightMode; icon: string; text: string; label: string }> = [
  { id: "day", icon: Sun, text: t("Día"), label: t("Tema día") },
  { id: "night", icon: Moon, text: t("Noche"), label: t("Tema noche") },
  { id: "auto", icon: SunMoon, text: t("Automático"), label: t("Tema automático: como el sistema") },
];

export function AppearanceToggle({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const active = OPTIONS.find((o) => o.id === value) ?? OPTIONS[2];

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={`appearance-toggle${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="appearance-toggle__trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls="appearance-toggle-menu"
        title={t("{0}. Cambiar tema", { 0: active.label })}
        aria-label={t("{0}. Cambiar tema", { 0: active.label })}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon svg={active.icon} size={20} />
      </button>
      <div
        id="appearance-toggle-menu"
        className="appearance-toggle__menu"
        role="listbox"
        aria-label={t("Tema")}
        aria-hidden={!open}
        // Cerrado no se ve: que tampoco reciba el foco con Tab.
        {...(!open ? { inert: "" } : {})}
      >
        {OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            role="option"
            aria-selected={value === opt.id}
            className={`appearance-toggle__btn${value === opt.id ? " is-active" : ""}`}
            title={opt.label}
            onClick={() => {
              onChange(opt.id);
              setOpen(false);
            }}
          >
            <Icon svg={opt.icon} size={20} />
            <span className="appearance-toggle__text">{opt.text}</span>
            {value === opt.id && <Icon svg={Check} size={16} className="appearance-toggle__check" />}
          </button>
        ))}
      </div>
    </div>
  );
}

export type { DayNightMode };
