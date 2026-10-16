/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
import type { MascotMood } from "../types";

/** El oso piloto (Bitácora): casco de cuero, gafas de aviador en la frente y bufanda. SVG propio. */
export function Oso({ mood = "happy", size = 96, className = "" }: { mood?: MascotMood; size?: number; className?: string }) {
  const mouth =
    mood === "sad" ? "M43 76 Q50 71 57 76" : mood === "think" ? "M44 75 L56 75" : mood === "cheer" ? "M41 72 Q50 84 59 72 Z" : "M43 73 Q50 79 57 73";
  return (
    <svg className={`mascot mascot--oso mascot--${mood} ${className}`} width={size} height={size} viewBox="0 0 100 100" aria-hidden>
      {/* orejas */}
      <circle cx="24" cy="30" r="10" className="oso__fur" />
      <circle cx="76" cy="30" r="10" className="oso__fur" />
      <circle cx="24" cy="30" r="5" className="oso__inner" />
      <circle cx="76" cy="30" r="5" className="oso__inner" />
      {/* bufanda */}
      <path d="M26 82 Q50 94 74 82 L72 90 Q50 100 28 90 Z" className="oso__scarf" />
      <path d="M66 86 L78 99 L84 94 L72 84 Z" className="oso__scarf" />
      {/* cabeza */}
      <circle cx="50" cy="56" r="30" className="oso__fur" />
      {/* casco de cuero */}
      <path d="M21 50 Q22 22 50 20 Q78 22 79 50 Q66 40 50 40 Q34 40 21 50 Z" className="oso__helmet" />
      <rect x="16" y="50" width="9" height="16" rx="4" className="oso__helmet" />
      <rect x="75" y="50" width="9" height="16" rx="4" className="oso__helmet" />
      {/* gafas de aviador en la frente */}
      <path d="M26 36 L74 36" className="oso__strap" />
      <circle cx="39" cy="35" r="8" className="oso__goggle" />
      <circle cx="61" cy="35" r="8" className="oso__goggle" />
      <circle cx="37" cy="33" r="2.4" className="oso__glint" />
      <circle cx="59" cy="33" r="2.4" className="oso__glint" />
      {/* hocico */}
      <ellipse cx="50" cy="69" rx="14" ry="11" className="oso__muzzle" />
      <ellipse cx="50" cy="64" rx="5" ry="3.6" className="oso__nose" />
      {/* ojos */}
      {mood === "cheer" ? (
        <>
          <path d="M36 54 Q40 49 44 54" className="mascot__eye-line oso__line" />
          <path d="M56 54 Q60 49 64 54" className="mascot__eye-line oso__line" />
        </>
      ) : (
        <>
          <circle cx="40" cy="54" r="3.6" className="oso__eye" />
          <circle cx="60" cy="54" r="3.6" className="oso__eye" />
          <circle cx="41.3" cy="52.7" r="1.1" className="mascot__shine" />
          <circle cx="61.3" cy="52.7" r="1.1" className="mascot__shine" />
        </>
      )}
      <path d={mouth} className={mood === "cheer" ? "oso__mouth-fill" : "oso__mouth"} />
      <circle cx="31" cy="64" r="3.4" className="mascot__blush" />
      <circle cx="69" cy="64" r="3.4" className="mascot__blush" />
    </svg>
  );
}
