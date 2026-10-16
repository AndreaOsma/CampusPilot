/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
import { Oso } from "./mascots/Oso";
import { Pilo } from "./mascots/Pilo";
import { Ruti } from "./mascots/Ruti";
import type { MascotMood } from "./types";

export type MascotKind = "pilo" | "oso" | "ruti";

/** La mascota de cada app, con los mismos estados de ánimo: happy, cheer (acierto), think, sad (fallo). */
export function Mascot({ kind = "pilo", mood = "happy", size = 96, className = "" }: { kind?: MascotKind; mood?: MascotMood; size?: number; className?: string }) {
  if (kind === "oso") return <Oso mood={mood} size={size} className={className} />;
  if (kind === "ruti") return <Ruti mood={mood} size={size} className={className} />;
  return <Pilo mood={mood} size={size} className={className} />;
}
