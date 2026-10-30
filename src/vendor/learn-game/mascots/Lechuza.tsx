/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
import type { MascotMood } from "../types";

/** La lechuza de Atenea (Clío): penachos, ojos grandes, corona de laurel y una estrella en el pecho. SVG propio. */
export function Lechuza({ mood = "happy", size = 96, className = "" }: { mood?: MascotMood; size?: number; className?: string }) {
  const wingL = mood === "cheer" ? "M22 62 Q8 44 14 30 Q22 46 30 52 Z" : "M24 58 Q12 70 20 86 Q26 74 32 66 Z";
  const wingR = mood === "cheer" ? "M78 62 Q92 44 86 30 Q78 46 70 52 Z" : "M76 58 Q88 70 80 86 Q74 74 68 66 Z";
  return (
    <svg className={`mascot mascot--lechuza mascot--${mood} ${className}`} width={size} height={size} viewBox="0 0 100 100" aria-hidden>
      {/* alas */}
      <path d={wingL} className="lechuza__wing" />
      <path d={wingR} className="lechuza__wing" />
      {/* cuerpo y cabeza */}
      <ellipse cx="50" cy="66" rx="25" ry="27" className="lechuza__body" />
      <ellipse cx="50" cy="72" rx="15" ry="16" className="lechuza__belly" />
      <path d="M43 70 Q46 73 49 70 M51 70 Q54 73 57 70 M45 78 Q48 81 51 78 M49 78 Q52 81 55 78" className="lechuza__line" />
      {/* estrella en el pecho */}
      <path d="M50 84 l1.3 3 3.1.3-2.4 2 .8 3-2.8-1.6-2.8 1.6.8-3-2.4-2 3.1-.3z" className="lechuza__star" />
      <ellipse cx="50" cy="42" rx="27" ry="23" className="lechuza__body" />
      {/* penachos */}
      <path d="M27 30 L22 12 L37 24 Z" className="lechuza__body" />
      <path d="M73 30 L78 12 L63 24 Z" className="lechuza__body" />
      {/* corona de laurel */}
      <path d="M30 24 Q50 12 70 24" className="lechuza__laurel-stem" />
      {[34, 41, 48, 55, 62].map((x, i) => (
        <ellipse key={x} cx={x + 1} cy={i === 2 ? 17 : i % 4 === 0 ? 21.5 : 18.5} rx="3.6" ry="1.9" transform={`rotate(${-30 + i * 15} ${x + 1} ${i === 2 ? 17 : i % 4 === 0 ? 21.5 : 18.5})`} className="lechuza__laurel" />
      ))}
      {/* disco facial */}
      <circle cx="38" cy="44" r="12.5" className="lechuza__face" />
      <circle cx="62" cy="44" r="12.5" className="lechuza__face" />
      {/* ojos */}
      {mood === "cheer" ? (
        <>
          <path d="M31 45 Q38 37 45 45" className="mascot__eye-line lechuza__eyeline" />
          <path d="M55 45 Q62 37 69 45" className="mascot__eye-line lechuza__eyeline" />
        </>
      ) : (
        <>
          <circle cx="38" cy="44" r="7.5" className="lechuza__iris" />
          <circle cx="62" cy="44" r="7.5" className="lechuza__iris" />
          <circle cx="38" cy="44" r="4" className="lechuza__pupil" />
          <circle cx="62" cy="44" r="4" className="lechuza__pupil" />
          <circle cx="39.6" cy="42.4" r="1.4" className="mascot__shine" />
          <circle cx="63.6" cy="42.4" r="1.4" className="mascot__shine" />
          {mood === "sad" && (
            <>
              <path d="M30.2 45 A7.8 7.8 0 0 1 45.8 42.5 Q38 41 30.2 45 Z" className="lechuza__face" />
              <path d="M54.2 42.5 A7.8 7.8 0 0 1 69.8 45 Q62 41 54.2 42.5 Z" className="lechuza__face" />
              <path d="M30.2 45 Q38 41 45.8 42.5 M54.2 42.5 Q62 41 69.8 45" className="lechuza__line" />
            </>
          )}
          {mood === "think" && <path d="M54.2 43 A7.8 7.8 0 0 1 69.8 43 Q62 40.5 54.2 43 Z" className="lechuza__face" />}
        </>
      )}
      {/* pico */}
      {mood === "cheer" ? (
        <path d="M45 52 L55 52 L50 62 Z M46 55 L54 55" className="lechuza__beak" />
      ) : (
        <path d="M46 52 L54 52 L50 60 Z" className="lechuza__beak" />
      )}
      <circle cx="28" cy="54" r="3" className="mascot__blush" />
      <circle cx="72" cy="54" r="3" className="mascot__blush" />
    </svg>
  );
}
