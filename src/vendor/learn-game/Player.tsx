/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
import { useMemo, type MouseEvent, type ReactNode } from "react";
import { Mascot, type MascotKind } from "./Mascot";
import { WeekDots } from "./Game";
import { fmtClock, spanish, type GameState, type Tx } from "./types";

/** Barra de arriba del reproductor: salir, progreso (se enciende con racha de aciertos), XP o reloj, sonido y extras. */
export function PlayerTop({
  exitHref,
  onExit,
  progress,
  hot,
  xp,
  remainingSec,
  sounds,
  onToggleSounds,
  children,
  tx = spanish,
}: {
  exitHref: string;
  onExit: (e: MouseEvent) => void;
  progress: number;
  hot: boolean;
  xp: number;
  remainingSec?: number | null;
  sounds: boolean;
  onToggleSounds: () => void;
  children?: ReactNode;
  tx?: Tx;
}) {
  return (
    <div className="lp-top">
      <a className="lp-x" href={exitHref} onClick={onExit} aria-label={tx("Salir")}>
        ✕
      </a>
      <div className={`lp-bar${hot ? " is-hot" : ""}`} role="progressbar" aria-label={tx("Progreso")} aria-valuemin={0} aria-valuemax={100}
        aria-valuenow={Math.round(progress * 100)}>
        <div className="lp-bar__fill" style={{ width: `${Math.max(progress * 100, 3)}%` }} />
      </div>
      {remainingSec !== null && remainingSec !== undefined ? (
        <span className={`lp-clock${remainingSec < 60 ? " text-crit" : ""}`} aria-label={tx("Quedan {0}", { 0: fmtClock(remainingSec) })}>
          ⏱ {fmtClock(remainingSec)}
        </span>
      ) : (
        <span className="lp-xp" aria-label={tx("{0} XP", { 0: xp })}>
          ⚡{xp}
        </span>
      )}
      <button type="button" className="lp-icon" aria-label={sounds ? tx("Silenciar") : tx("Activar sonido")} aria-pressed={sounds} onClick={onToggleSounds}>
        {sounds ? "🔊" : "🔇"}
      </button>
      {children}
    </div>
  );
}

export function ComboFlash({ n, tx = spanish }: { n: number | null; tx?: Tx }) {
  if (!n) return null;
  return (
    <div className="lp-combo" role="status">
      🔥 ¡{n} {tx("seguidas!")}
    </div>
  );
}

/** Pie fijo: verde si acertaste, rojo si no; el contenido (botones, veredicto) lo pone la app. */
export function PlayerFoot({ result, children }: { result: null | "ok" | "ko"; children: ReactNode }) {
  return (
    <footer className={`lp-foot${result ? ` lp-foot--${result}` : ""}`}>
      <div className="lp-foot__inner">{children}</div>
    </footer>
  );
}

/** La pregunta en una tarjeta, con la mascota pequeña en la esquina (sin bocadillo de diálogo). */
export function QuestionBubble({ mascot, mood, children }: { mascot: MascotKind; mood: "think" | "cheer" | "sad"; children: ReactNode }) {
  return (
    <div className="lp-question">
      <div className="lp-qcard">{children}</div>
      <Mascot kind={mascot} mood={mood} size={44} className="lp-question__mascot" />
    </div>
  );
}

export function Confetti() {
  const bits = useMemo(
    () => Array.from({ length: 36 }, (_, i) => ({ i, left: Math.random() * 100, delay: Math.random() * 0.6, hue: Math.round(Math.random() * 360) })),
    []
  );
  return (
    <div className="confetti" aria-hidden>
      {bits.map((b) => (
        <span key={b.i} style={{ left: `${b.left}%`, animationDelay: `${b.delay}s`, background: `hsl(${b.hue} 85% 60%)` }} />
      ))}
    </div>
  );
}

/** Pantalla final: tarjeta de resumen (XP, precisión, tiempo en filas) y lo que añada la app. */
export function EndScreen({
  mascot,
  title,
  stats,
  note,
  children,
  actions,
  tx = spanish,
}: {
  mascot: MascotKind;
  title: string;
  stats?: { xp: number; accuracy: number; seconds: number } | null;
  note?: ReactNode;
  children?: ReactNode;
  actions: ReactNode;
  tx?: Tx;
}) {
  return (
    <div className="lp-end">
      <section className="lp-end__card">
        <header className="lp-end__head">
          <Mascot kind={mascot} mood={stats ? "cheer" : "happy"} size={56} />
          <h1 className="lp-end__title">{title}</h1>
        </header>
        {stats && (
          <dl className="lp-end__stats">
            <div>
              <dt>{tx("Precisión")}</dt>
              <dd>{stats.accuracy} %</dd>
            </div>
            <div>
              <dt>{tx("XP ganada")}</dt>
              <dd>+{stats.xp}</dd>
            </div>
            <div>
              <dt>{tx("Tiempo")}</dt>
              <dd>{fmtClock(stats.seconds)}</dd>
            </div>
          </dl>
        )}
        {note && <p className="lp-end__note">{note}</p>}
        {children}
        <div className="lp-end__actions">{actions}</div>
      </section>
    </div>
  );
}

/** Aviso de racha al primer estudio del día: una tarjeta tranquila con la semana, no una celebración a pantalla completa. */
export function StreakScreen({ game, weekdays, message, onContinue, tx = spanish }: { game: GameState; weekdays?: string[]; message: string; onContinue: () => void; tx?: Tx }) {
  return (
    <div className="lp-end">
      <section className="lp-end__card">
        <header className="lp-end__head">
          <span className="lp-end__badge" aria-hidden>
            {game.streak}
          </span>
          <h1 className="lp-end__title">
            {game.streak} {tx("día")}
            {game.streak === 1 ? "" : "s"} {tx("seguidos estudiando")}
          </h1>
        </header>
        <p className="muted">{message}</p>
        <WeekDots game={game} weekdays={weekdays} />
        <div className="lp-end__actions">
          <button type="button" className="lp-btn lp-btn--go" autoFocus onClick={onContinue}>
            {tx("Seguir")}
          </button>
        </div>
      </section>
    </div>
  );
}
