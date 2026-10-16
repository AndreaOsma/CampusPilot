import katex from "katex";
import "katex/dist/katex.min.css";
import { useMemo } from "react";

export type MathPart = { math: boolean; text: string };

/** Separa `texto $fórmula$ texto` en trozos. `\$` es un dólar literal; un `$` sin cerrar queda como texto. */
export function splitMath(input: string): MathPart[] {
  const parts: MathPart[] = [];
  let buf = "";
  let i = 0;
  while (i < input.length) {
    const ch = input[i];
    if (ch === "\\" && input[i + 1] === "$") {
      buf += "$";
      i += 2;
      continue;
    }
    if (ch === "$") {
      const close = input.indexOf("$", i + 1);
      if (close > i + 1) {
        if (buf) parts.push({ math: false, text: buf });
        parts.push({ math: true, text: input.slice(i + 1, close) });
        buf = "";
        i = close + 1;
        continue;
      }
    }
    buf += ch;
    i += 1;
  }
  if (buf) parts.push({ math: false, text: buf });
  return parts;
}

/** Texto con fórmulas inline. El texto normal lo pinta React (escapado); solo el HTML que
 *  genera KaTeX (trust: false, sin \href ni \htmlClass) entra como HTML. */
export function MathText({ text }: { text: string }) {
  const parts = useMemo(() => splitMath(text), [text]);
  return (
    <>
      {parts.map((p, i) =>
        p.math ? (
          <span
            key={i}
            dangerouslySetInnerHTML={{ __html: katex.renderToString(p.text, { throwOnError: false, trust: false, output: "html" }) }}
          />
        ) : (
          <span key={i}>{p.text}</span>
        )
      )}
    </>
  );
}
