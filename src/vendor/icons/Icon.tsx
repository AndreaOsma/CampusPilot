// Generado por lib/icons/sync.mjs. No editar: se cambia en lib y se vuelve a ejecutar.
import type { CSSProperties } from "react";

/** Icono de lib/icons/ui (Lucide 0.460.0 y propios del homelab): trazo en el color del texto (currentColor).
 *  Decorativo por defecto (aria-hidden): lo nombra el texto de al lado o el aria-label del botón que lo
 *  lleva. Con `label` es una imagen con nombre propio (icono suelto que transmite algo). */
export function Icon({ svg, size = "1.25em", label, className, style }: {
  svg: string;
  size?: number | string;
  label?: string;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      className={className ? `ico ${className}` : "ico"}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      style={{ display: "inline-block", flex: "none", width: size, height: size, lineHeight: 0, verticalAlign: "-0.2em", ...style }}
      // Cadenas fijas de lib/icons/ui generadas en build, nunca contenido de usuarios.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
