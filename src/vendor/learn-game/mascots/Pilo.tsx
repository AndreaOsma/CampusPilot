/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
/** Pilo (Campus Pilot): un satélite con birrete. SVG propio, sin assets externos. */
import type { MascotMood } from "../types";

export function Pilo({ mood = "happy", size = 96, className = "" }: { mood?: MascotMood; size?: number; className?: string }) {
  const mouth =
    mood === "sad" ? "M40 70 Q50 63 60 70" : mood === "think" ? "M42 68 L58 68" : mood === "cheer" ? "M38 64 Q50 80 62 64 Z" : "M40 65 Q50 74 60 65";
  return (
    <svg className={`mascot mascot--${mood} ${className}`} width={size} height={size} viewBox="0 0 100 100" aria-hidden>
      {/* paneles solares */}
      <rect x="2" y="44" width="16" height="22" rx="3" className="mascot__panel" />
      <rect x="82" y="44" width="16" height="22" rx="3" className="mascot__panel" />
      <rect x="18" y="53" width="8" height="4" className="mascot__arm" />
      <rect x="74" y="53" width="8" height="4" className="mascot__arm" />
      {/* antena */}
      <line x1="50" y1="24" x2="50" y2="12" className="mascot__arm" strokeWidth="3" />
      <circle cx="50" cy="10" r="4" className="mascot__light" />
      {/* cuerpo */}
      <circle cx="50" cy="56" r="28" className="mascot__body" />
      {/* birrete */}
      <polygon points="26,30 50,20 74,30 50,40" className="mascot__cap" />
      <rect x="40" y="31" width="20" height="8" className="mascot__cap" />
      <line x1="70" y1="30" x2="72" y2="42" className="mascot__tassel" strokeWidth="2" />
      {/* cara */}
      {mood === "cheer" ? (
        <>
          <path d="M37 52 Q41 47 45 52" className="mascot__eye-line" />
          <path d="M55 52 Q59 47 63 52" className="mascot__eye-line" />
        </>
      ) : (
        <>
          <circle cx="41" cy="52" r="4" className="mascot__eye" />
          <circle cx="59" cy="52" r="4" className="mascot__eye" />
          <circle cx="42.5" cy="50.5" r="1.3" className="mascot__shine" />
          <circle cx="60.5" cy="50.5" r="1.3" className="mascot__shine" />
        </>
      )}
      <path d={mouth} className={mood === "cheer" ? "mascot__mouth-fill" : "mascot__mouth"} />
      <circle cx="33" cy="62" r="3.5" className="mascot__blush" />
      <circle cx="67" cy="62" r="3.5" className="mascot__blush" />
    </svg>
  );
}
