/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
import type { MascotMood } from "../types";

/** Ruti (Insignia): un router pequeño con antenas y LEDs de estado. SVG propio, sin assets externos. */
export function Ruti({ mood = "happy", size = 96, className = "" }: { mood?: MascotMood; size?: number; className?: string }) {
  const mouth =
    mood === "sad" ? "M41 67 Q50 60 59 67" : mood === "think" ? "M43 64 L57 64" : mood === "cheer" ? "M39 61 Q50 74 61 61 Z" : "M41 62 Q50 70 59 62";
  return (
    <svg className={`mascot mascot--ruti mascot--${mood} ${className}`} width={size} height={size} viewBox="0 0 100 100" aria-hidden>
      {/* antenas */}
      <line x1="27" y1="38" x2="19" y2="14" className="ruti__antenna" />
      <line x1="73" y1="38" x2="81" y2="14" className="ruti__antenna" />
      <circle cx="18" cy="12" r="3.5" className="ruti__tip" />
      <circle cx="82" cy="12" r="3.5" className="ruti__tip" />
      {/* patas */}
      <rect x="26" y="79" width="10" height="7" rx="2.5" className="ruti__foot" />
      <rect x="64" y="79" width="10" height="7" rx="2.5" className="ruti__foot" />
      {/* cuerpo (caja del router) */}
      <rect x="16" y="36" width="68" height="44" rx="12" className="ruti__body" />
      <rect x="20" y="40" width="60" height="36" rx="9" className="ruti__panel" />
      {/* rejilla de ventilación */}
      <line x1="24" y1="50" x2="31" y2="50" className="ruti__vent" />
      <line x1="24" y1="56" x2="31" y2="56" className="ruti__vent" />
      <line x1="24" y1="62" x2="31" y2="62" className="ruti__vent" />
      {/* LEDs de estado */}
      <circle cx="75" cy="48" r="2.6" className="ruti__led ruti__led--on" />
      <circle cx="75" cy="57" r="2.6" className="ruti__led ruti__led--gold" />
      <circle cx="75" cy="66" r="2.6" className="ruti__led" />
      {/* cara */}
      {mood === "cheer" ? (
        <>
          <path d="M36 52 Q40 47 44 52" className="mascot__eye-line" />
          <path d="M56 52 Q60 47 64 52" className="mascot__eye-line" />
        </>
      ) : (
        <>
          <circle cx="40" cy="52" r="4" className="mascot__eye" />
          <circle cx="60" cy="52" r="4" className="mascot__eye" />
          <circle cx="41.5" cy="50.5" r="1.3" className="mascot__shine" />
          <circle cx="61.5" cy="50.5" r="1.3" className="mascot__shine" />
        </>
      )}
      <path d={mouth} className={mood === "cheer" ? "mascot__mouth-fill" : "mascot__mouth"} />
      <circle cx="33" cy="60" r="3.2" className="mascot__blush" />
      <circle cx="67" cy="60" r="3.2" className="mascot__blush" />
    </svg>
  );
}
