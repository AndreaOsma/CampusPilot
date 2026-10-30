/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
import { useEffect, useState } from "react";
import { Check, Icon, Shuffle } from "../icons";
import { spanish, type Tx } from "./types";

export type MixedGroup = { id: number; title: string; count: number };

const MIXED_N = 10;

function loadOff(key: string): number[] {
  try {
    const v = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "number") : [];
  } catch {
    return [];
  }
}

/**
 * Repaso mixto: preguntas al azar de asignaturas al azar, solo de lo que ya se ha visto.
 * Cada app da sus grupos (asignaturas, cursos o materias con cuántas preguntas vistas tienen) y qué hacer al empezar.
 */
export function MixedReviewCard({
  groups,
  storageKey,
  onStart,
  groupLabel = "asignaturas",
  tx = spanish,
}: {
  groups: MixedGroup[];
  storageKey: string;
  onStart: (ids: number[]) => void;
  groupLabel?: string;
  tx?: Tx;
}) {
  const [off, setOff] = useState<number[]>(() => loadOff(storageKey));
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(off));
    } catch {
      /* sin almacenamiento: la selección dura lo que la página */
    }
  }, [off, storageKey]);

  const available = groups.filter((g) => g.count > 0);
  const chosen = available.filter((g) => !off.includes(g.id));
  const pool = chosen.reduce((n, g) => n + g.count, 0);
  const toggle = (id: number) => setOff((o) => (o.includes(id) ? o.filter((x) => x !== id) : [...o, id]));

  return (
    <section className="card mixed">
      <div className="card__head">
        <h2 className="card__title">
          <Icon svg={Shuffle} /> {tx("Repaso mixto")}
        </h2>
      </div>
      {available.length === 0 ? (
        <p className="muted small">{tx("Cuando termines alguna lección, aquí te preguntaré al azar de todo lo que ya has visto, mezclando {0}.", { 0: tx(groupLabel) })}</p>
      ) : (
        <>
          <p className="muted small">
            {tx("{0} preguntas al azar de lo que ya has visto, saltando de una a otra. Lo que más te cuesta sale más.", { 0: Math.min(MIXED_N, pool) })}
          </p>
          {available.length > 1 && (
            <div className="mixed__groups" role="group" aria-label={tx("Qué entra en el repaso")}>
              {available.map((g) => {
                const on = !off.includes(g.id);
                return (
                  <button key={g.id} type="button" className={`mixed__chip${on ? " is-on" : ""}`} aria-pressed={on} onClick={() => toggle(g.id)}>
                    {on && <Icon svg={Check} />} {g.title}
                  </button>
                );
              })}
            </div>
          )}
          <button type="button" className="btn mixed__start" disabled={!chosen.length} onClick={() => onStart(chosen.map((g) => g.id))}>
            <Icon svg={Shuffle} /> {chosen.length ? tx("Empezar") : tx("Elige al menos una")}
          </button>
        </>
      )}
    </section>
  );
}
