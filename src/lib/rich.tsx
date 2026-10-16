import { Fragment, type ReactNode } from "react";
import { MathText } from "./math";

/** **negrita** y $fórmulas$ dentro de una línea. Todo el texto lo pinta React (escapado). */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  parts.forEach((p, i) => {
    if (p.startsWith("**") && p.endsWith("**") && p.length > 4) out.push(<strong key={i}><MathText text={p.slice(2, -2)} /></strong>);
    else if (p) out.push(<MathText key={i} text={p} />);
  });
  return out;
}

/** Markdown mínimo: párrafos, `# títulos`, listas `-`/`1.` y bloques `$$…$$` en su línea. */
export function RichText({ text, className = "" }: { text: string; className?: string }) {
  const blocks: ReactNode[] = [];
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  let para: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (para.length) {
      blocks.push(<p key={blocks.length}>{para.flatMap((l, i) => (i ? [<br key={`b${i}`} />, ...inline(l)] : inline(l)))}</p>);
      para = [];
    }
    if (list) {
      const items = list.items.map((it, i) => <li key={i}>{inline(it)}</li>);
      blocks.push(list.ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>);
      list = null;
    }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const display = line.trim().match(/^\$\$(.+)\$\$$/);
    const heading = line.match(/^#{1,3}\s+(.*)$/);
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (!line.trim()) flush();
    else if (display) {
      flush();
      blocks.push(
        <p key={blocks.length} className="rich__display">
          <MathText text={`$${display[1]}$`} />
        </p>
      );
    } else if (heading) {
      flush();
      blocks.push(<h3 key={blocks.length}>{inline(heading[1])}</h3>);
    } else if (bullet || numbered) {
      if (para.length) flush();
      const ordered = Boolean(numbered);
      if (list && list.ordered !== ordered) flush();
      list = list ?? { ordered, items: [] };
      list.items.push((bullet ?? numbered)![1]);
    } else {
      if (list) flush();
      para.push(line);
    }
  }
  flush();
  return <div className={`rich ${className}`}>{blocks.map((b, i) => <Fragment key={i}>{b}</Fragment>)}</div>;
}

/** Variante en línea (sin bloques): para opciones, pasos a ordenar y soluciones. */
export function InlineRich({ text }: { text: string }) {
  return <>{inline(text)}</>;
}

/** Figura de la teoría (SVG generado por la IA y saneado en el servidor). Va como <img>: así
 *  el SVG no puede ejecutar nada ni cargar recursos, aunque el saneado fallara. */
export function TheoryFigure({ figure }: { figure: { svg: string; alt: string; caption?: string } }) {
  return (
    <figure className="theory-figure">
      <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(figure.svg)}`} alt={figure.alt} loading="lazy" />
      {figure.caption && <figcaption className="small muted">{figure.caption}</figcaption>}
    </figure>
  );
}
