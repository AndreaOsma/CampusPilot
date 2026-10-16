/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
import { type MouseEvent, type ReactNode } from "react";
import { dayIsOn, spanish, WEEKDAYS_ES, type GameState, type Tx } from "./types";

function Card({ title, children, className = "" }: { title: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      <div className="card__head">
        <h2 className="card__title">{title}</h2>
      </div>
      {children}
    </section>
  );
}

/** Barra de arriba: lo que elija cada app a la izquierda (curso, asignatura…) y racha/chispas a la derecha. */
export function GameBar({ game, children, tx = spanish }: { game: GameState | null; children?: ReactNode; tx?: Tx }) {
  return (
    <div className="learn-bar">
      {children}
      {game && (
        <span className="learn-bar__stats">
          <span className={`learn-stat learn-stat--streak${game.streak ? " is-on" : ""}`} title={tx("Días de racha")}>
            🔥 {game.streak}
          </span>
          <span className="learn-stat learn-stat--gems" title={tx("Chispas")}>
            ✨ {game.gems}
          </span>
          {game.streak_freezes > 0 && (
            <span className="learn-stat" title={tx("Días libres guardados")}>
              🌴 {game.streak_freezes}
            </span>
          )}
        </span>
      )}
    </div>
  );
}

export function WeekDots({ game, weekdays = WEEKDAYS_ES, big = false }: { game: GameState; weekdays?: string[]; big?: boolean }) {
  return (
    <ol className={`week-dots${big ? " week-dots--big" : ""}`}>
      {game.week.map((d, i) => (
        <li key={d.date} className={dayIsOn(d) ? "is-on" : d.frozen ? "is-frozen" : d.future ? "is-future" : ""} title={d.date}>
          <span className="week-dots__day">{weekdays[i]}</span>
          <span className="week-dots__mark" aria-hidden>
            {dayIsOn(d) ? "🔥" : d.frozen ? "🌴" : "·"}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function StreakCard({ game, weekdays, tx = spanish }: { game: GameState; weekdays?: string[]; tx?: Tx }) {
  const pct = Math.min(1, game.goal ? game.today_xp / game.goal : 0);
  return (
    <Card title={tx("🔥 {0} día{1} de racha", { 0: game.streak, 1: game.streak === 1 ? "" : "s" })}>
      <WeekDots game={game} weekdays={weekdays} />
      <div className="goal-line">
        <span className="small">{tx("Meta diaria")}</span>
        <span className="goal-line__bar" role="progressbar" aria-valuemin={0} aria-valuemax={game.goal} aria-valuenow={game.today_xp} aria-label={tx("XP de hoy")}>
          <span className="goal-line__fill" style={{ width: `${pct * 100}%` }} />
        </span>
        <span className="small goal-line__num">
          {game.today_xp}/{game.goal} {tx("XP")}
        </span>
      </div>
    </Card>
  );
}

export function Quests({ game, onClaim, icons = {}, tx = spanish }: { game: GameState; onClaim: (id: string) => void; icons?: Record<string, string>; tx?: Tx }) {
  return (
    <Card title={tx("Misiones del día")}>
      <ul className="quests">
        {game.quests.map((q) => (
          <li key={q.id} className={`quest${q.done ? " is-done" : ""}`}>
            <span className="quest__icon" aria-hidden>
              {icons[q.id] ?? "⭐"}
            </span>
            <div className="quest__body">
              <span className="quest__title">{q.title}</span>
              <span className="quest__bar" role="progressbar" aria-valuemin={0} aria-valuemax={q.target} aria-valuenow={q.progress} aria-label={q.title}>
                <span className="quest__fill" style={{ width: `${(q.progress / q.target) * 100}%` }} />
                <span className="quest__count">
                  {q.progress}/{q.target}
                </span>
              </span>
            </div>
            {q.claimed ? (
              <span className="quest__reward is-claimed" title={tx("Recompensa cobrada")}>
                ✓
              </span>
            ) : q.done ? (
              <button type="button" className="btn btn--sm quest__claim" onClick={() => onClaim(q.id)}>
                +{q.gems} ✨
              </button>
            ) : (
              <span className="quest__reward muted small">{q.gems} ✨</span>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function Shop({ game, onBuy, tx = spanish }: { game: GameState; onBuy: () => void; tx?: Tx }) {
  const full = game.streak_freezes >= game.max_freezes;
  return (
    <Card title={tx("Canjear chispas")}>
      <div className="shop-item">
        <span className="shop-item__icon" aria-hidden>
          🌴
        </span>
        <div>
          <p className="shop-item__title">{tx("Día libre")}</p>
          <p className="muted small">
            {tx("Si un día no puedes estudiar, la racha no se rompe. Guardados:")} {game.streak_freezes}/{game.max_freezes}.
          </p>
        </div>
        <button type="button" className="btn btn--sm shop-item__buy" disabled={full || game.gems < game.prices.freeze} onClick={onBuy}>
          {full ? tx("Al máximo") : `${game.prices.freeze} ✨`}
        </button>
      </div>
    </Card>
  );
}

export type PathLesson = {
  id: string | number;
  title: string;
  done: boolean;
  locked: boolean;
  current: boolean;
  level: number;
  /** Texto bajo el título en el globo (nº de ejercicios, mejor resultado…). */
  detail?: string;
  href: string;
};
export type PathUnit = { id: string | number; title: string; done: boolean; badgeClaimed: boolean; lessons: PathLesson[] };

/** Dominio de una lección (veces completada, hasta 5) como cinco segmentos. */
function Mastery({ level, tx }: { level: number; tx: Tx }) {
  return (
    <span className="syl-mastery" role="img" aria-label={tx("Dominio {0} de 5", { 0: level })} title={tx("Dominio {0} de 5", { 0: level })}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={n <= level ? "is-on" : ""} />
      ))}
    </span>
  );
}

/** Temario: unidades → lecciones en lista (bloqueadas, la siguiente, hechas), con la insignia al final de cada unidad.
 * Lista con el título siempre visible a propósito: nada de camino en zigzag ni cofres (identidad propia, ver README). */
export function PathView({
  units,
  onGo,
  onBadge,
  extra,
  unitLabel,
  tx = spanish,
}: {
  units: PathUnit[];
  onGo: (lesson: PathLesson, e: MouseEvent) => void;
  onBadge: (unitId: PathUnit["id"]) => void;
  /** Botones extra en el globo de una lección (p. ej. la guía). */
  extra?: (lesson: PathLesson) => ReactNode;
  unitLabel?: (unit: PathUnit, index: number) => string;
  tx?: Tx;
}) {
  let number = 0;
  return (
    <div className="syl">
      {units.map((u, ui) => {
        const done = u.lessons.filter((l) => l.done).length;
        const pct = u.lessons.length ? (done / u.lessons.length) * 100 : 0;
        return (
          <section key={u.id} className={`syl-unit${u.done ? " is-done" : ""}`} aria-label={u.title}>
            <header className="syl-unit__head">
              <div className="syl-unit__titles">
                <p className="syl-unit__kicker">{unitLabel ? unitLabel(u, ui) : `${tx("Unidad")} ${ui + 1}`}</p>
                <h2 className="syl-unit__title">{u.title}</h2>
              </div>
              <span className="syl-unit__count">
                {done}/{u.lessons.length}
              </span>
            </header>
            <span className="syl-unit__bar" role="progressbar" aria-label={tx("Progreso de la unidad")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
              <span style={{ width: `${pct}%` }} />
            </span>
            <ol className="syl-list">
              {u.lessons.map((l) => {
                number += 1;
                const state = l.locked ? "locked" : l.current ? "current" : l.done ? "done" : "open";
                return (
                  <li key={l.id} className={`syl-row syl-row--${state}`}>
                    <span className="syl-row__mark" aria-hidden>
                      {l.done ? "✓" : l.locked ? "" : number}
                    </span>
                    <div className="syl-row__body">
                      <p className="syl-row__title">
                        {l.title}
                        {l.current && <span className="syl-row__next">{tx("Siguiente")}</span>}
                      </p>
                      {l.locked ? (
                        <p className="syl-row__detail">{tx("Se abre al completar la anterior")}</p>
                      ) : (
                        l.detail && <p className="syl-row__detail">{l.detail}</p>
                      )}
                      {l.done && l.level > 0 && <Mastery level={l.level} tx={tx} />}
                    </div>
                    <div className="syl-row__actions">
                      {!l.locked && (
                        <a className={`btn btn--sm ${l.current ? "btn--primary" : "btn--ghost"} syl-row__go`} href={l.href} onClick={(e) => onGo(l, e)}>
                          {l.done ? tx("Repasar") : tx("Empezar")}
                        </a>
                      )}
                      {l.locked && (
                        <span className="syl-row__lock" role="img" aria-label={tx("Bloqueada")}>
                          🔒
                        </span>
                      )}
                      {!l.locked && extra?.(l)}
                    </div>
                  </li>
                );
              })}
              <li className={`syl-row syl-row--badge${u.done ? (u.badgeClaimed ? " is-claimed" : " is-ready") : ""}`}>
                <span className="syl-row__mark" aria-hidden>
                  {u.badgeClaimed ? "🎓" : "🏅"}
                </span>
                <div className="syl-row__body">
                  <p className="syl-row__title">{tx("Insignia de la unidad")}</p>
                  <p className="syl-row__detail">
                    {u.badgeClaimed ? tx("Conseguida") : u.done ? tx("Unidad terminada: recógela") : tx("Termina todas las lecciones de la unidad")}
                  </p>
                </div>
                <div className="syl-row__actions">
                  {u.done && !u.badgeClaimed && (
                    <button type="button" className="btn btn--sm btn--primary" onClick={() => onBadge(u.id)}>
                      {tx("Recoger")}
                    </button>
                  )}
                </div>
              </li>
            </ol>
          </section>
        );
      })}
    </div>
  );
}
