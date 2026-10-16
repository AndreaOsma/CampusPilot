import { useEffect, useState } from "react";
import { intlTag, t } from "../i18n";

/** Texto de una tarjeta (Markdown + LaTeX ligero) pasado a algo que se pueda leer en voz alta. */
export function speakable(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/\$([^$]+)\$/g, (_, m: string) =>
      m
        .replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, (_, a: string, b: string) => t("{0} entre {1}", { 0: a, 1: b }))
        .replace(/\\sqrt\{([^}]*)\}/g, (_, a: string) => t("raíz de {0}", { 0: a }))
        .replace(/\^\{?2\}?/g, ` ${t("al cuadrado")}`)
        .replace(/\\cdot|\\times/g, ` ${t("por")} `)
        .replace(/\\[a-zA-Z]+/g, " ")
        .replace(/[{}_^]/g, " "),
    )
    .replace(/[*`#>|]/g, "")
    .replace(/^\s*-\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Lectura en voz alta con la voz del propio navegador/sistema: sin servicios ni coste. */
export function useSpeech() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => {
    if (supported) window.speechSynthesis.cancel();
  }, [supported]);
  const stop = () => {
    if (!supported) return;
    window.speechSynthesis.cancel();
    setSpeaking(false);
  };
  const speak = (text: string) => {
    if (!supported) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(speakable(text));
    u.lang = intlTag();
    u.onend = u.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(u);
  };
  return { supported, speaking, speak, stop };
}
