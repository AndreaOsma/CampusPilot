import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type AnswerResult, type CompleteResult, type GameState, type LessonFull, type PublicStep } from "../api";
import { GuideModal } from "../components/Guide";
import { InlineRich, RichText, TheoryFigure } from "../lib/rich";
import { useSpeech } from "../lib/speech";
import { WEEKDAYS } from "../lib/format";
import { ComboFlash, EndScreen, PlayerFoot, PlayerTop, play, QuestionBubble, StreakScreen, vibrate } from "../vendor/learn-game";
import { linkTo, type Navigate } from "../router";
import { useStore } from "../store";
import { ErrorBox, Loading } from "../ui";
import { t } from "../i18n";

export type PlayerMode =
  | { kind: "lesson"; lessonId: number }
  | { kind: "review" }
  | { kind: "practice"; courseId: number; concept: string; objective?: string }
  | { kind: "exam"; courseId: number };

type Queued = { step: PublicStep; firstTry: boolean };
type Draft = { choice: number[]; tf: boolean | null; num: string; re: string; im: string; order: string[]; match: (string | null)[] };
type ExamRow = { step: PublicStep; result: AnswerResult | null; skipped: boolean };

const emptyDraft = (step?: PublicStep): Draft => ({
  choice: [],
  tf: null,
  num: "",
  re: "",
  im: "",
  order: [],
  match: (step?.left ?? []).map(() => null),
});

const PRAISE = [t("¡Genial!"), t("¡Muy bien!"), t("¡Perfecto!"), t("¡Eso es!"), t("¡Bien hecho!"), t("¡Exacto!")];

function effectiveKind(step: PublicStep): PublicStep["kind"] {
  return step.kind === "param" ? (step.answer_kind === "complex" ? "complex" : "numeric") : step.kind;
}

function instruction(step: PublicStep): string {
  const k = effectiveKind(step);
  if (k === "choice") return step.prompt.includes("___") ? t("Completa la frase") : step.multiple ? t("Selecciona todas las correctas") : t("Selecciona la respuesta correcta");
  if (k === "truefalse") return t("¿Verdadero o falso?");
  if (k === "order") return t("Ordena los pasos");
  if (k === "match") return t("Empareja cada par");
  if (k === "complex") return t("Escribe el resultado como a + bi");
  if (k === "numeric") return t("Escribe el resultado");
  return step.kind === "info" ? t("📘 Teoría") : t("Lee con atención");
}

function responseOf(step: PublicStep, d: Draft): unknown {
  switch (effectiveKind(step)) {
    case "choice":
      return d.choice;
    case "truefalse":
      return d.tf;
    case "numeric":
      return d.num;
    case "complex":
      return { re: d.re, im: d.im };
    case "order":
      return d.order;
    case "match":
      return d.match;
    default:
      return null;
  }
}

function ready(step: PublicStep, d: Draft): boolean {
  switch (effectiveKind(step)) {
    case "choice":
      return d.choice.length > 0;
    case "truefalse":
      return d.tf !== null;
    case "numeric":
      return d.num.trim() !== "";
    case "complex":
      return d.re.trim() !== "" && d.im.trim() !== "";
    case "order":
      return d.order.length === (step.items ?? []).length;
    case "match":
      return d.match.every((m) => m !== null);
    default:
      return true;
  }
}

/** El enunciado; en frases con hueco, el hueco muestra la opción elegida. */
function Prompt({ step, draft }: { step: PublicStep; draft: Draft }) {
  if (step.kind === "choice" && step.prompt.includes("___")) {
    const chosen = draft.choice.length ? step.options?.[draft.choice[0]] : null;
    const [before, after] = step.prompt.split("___", 2);
    return (
      <p className="lp-prompt">
        <InlineRich text={before} />
        <span className={`lp-blank${chosen ? " is-filled" : ""}`}>{chosen ? <InlineRich text={chosen} /> : "      "}</span>
        <InlineRich text={after ?? ""} />
      </p>
    );
  }
  return <RichText text={step.prompt} className="lp-prompt" />;
}

function StepInput({ step, draft, setDraft, locked }: { step: PublicStep; draft: Draft; setDraft: (d: Draft) => void; locked: boolean }) {
  const kind = effectiveKind(step);
  const [leftPick, setLeftPick] = useState<number | null>(0);

  if (kind === "choice")
    return (
      <div className="lp-choices" role={step.multiple ? "group" : "radiogroup"} aria-label={t("Opciones")}>
        {(step.options ?? []).map((opt, i) => {
          const on = draft.choice.includes(i);
          return (
            <button key={i} type="button" disabled={locked} role={step.multiple ? "checkbox" : "radio"} aria-checked={on}
              className={`lp-tile${on ? " is-on" : ""}`}
              onClick={() => {
                play("tap");
                setDraft({ ...draft, choice: step.multiple ? (on ? draft.choice.filter((x) => x !== i) : [...draft.choice, i]) : [i] });
              }}>
              <span className="lp-tile__key" aria-hidden>
                {i + 1}
              </span>
              <span className="lp-tile__text">
                <InlineRich text={opt} />
              </span>
            </button>
          );
        })}
      </div>
    );
  if (kind === "truefalse")
    return (
      <div className="lp-choices lp-choices--two" role="radiogroup" aria-label={t("Verdadero o falso")}>
        {[true, false].map((v, i) => (
          <button key={String(v)} type="button" disabled={locked} role="radio" aria-checked={draft.tf === v}
            className={`lp-tile lp-tile--center${draft.tf === v ? " is-on" : ""}`}
            onClick={() => {
              play("tap");
              setDraft({ ...draft, tf: v });
            }}>
            <span className="lp-tile__key" aria-hidden>
              {i + 1}
            </span>
            {v ? t("Verdadero") : t("Falso")}
          </button>
        ))}
      </div>
    );
  if (kind === "numeric")
    return (
      <label className="lp-answer">
        <span className="sr-only">{t("Tu respuesta")}</span>
        <input inputMode="decimal" autoFocus disabled={locked} aria-label={t("Tu respuesta")} placeholder={t("Tu respuesta")} value={draft.num} onChange={(e) => setDraft({ ...draft, num: e.target.value })} />
        {step.unit && <span className="lp-answer__unit">{step.unit}</span>}
      </label>
    );
  if (kind === "complex")
    return (
      <div className="lp-complex">
        <label className="lp-answer">
          <span className="sr-only">{t("Parte real")}</span>
          <input inputMode="decimal" autoFocus disabled={locked} aria-label={t("Parte real (a)")} placeholder="a" value={draft.re} onChange={(e) => setDraft({ ...draft, re: e.target.value })} />
        </label>
        <span aria-hidden>+</span>
        <label className="lp-answer">
          <span className="sr-only">{t("Parte imaginaria")}</span>
          <input inputMode="decimal" disabled={locked} aria-label={t("Parte imaginaria (b)")} placeholder="b" value={draft.im} onChange={(e) => setDraft({ ...draft, im: e.target.value })} />
        </label>
        <span aria-hidden className="lp-complex__i">
          i
        </span>
      </div>
    );
  if (kind === "order") {
    const bank = (step.items ?? []).filter((it) => !draft.order.includes(it));
    return (
      <div className="lp-order">
        <ol className="lp-order__line" aria-label={t("Tu orden")}>
          {draft.order.length === 0 && <li className="lp-order__placeholder muted small">{t("Toca los pasos en orden")}</li>}
          {draft.order.map((it, i) => (
            <li key={it}>
              <button type="button" className="lp-chip is-placed" disabled={locked} aria-label={t("Quitar «{0}»", { 0: it })}
                onClick={() => setDraft({ ...draft, order: draft.order.filter((x) => x !== it) })}>
                <span className="lp-chip__n">{i + 1}</span>
                <InlineRich text={it} />
              </button>
            </li>
          ))}
        </ol>
        <div className="lp-order__bank" aria-label={t("Pasos disponibles")}>
          {bank.map((it) => (
            <button key={it} type="button" className="lp-chip" disabled={locked}
              onClick={() => {
                play("tap");
                setDraft({ ...draft, order: [...draft.order, it] });
              }}>
              <InlineRich text={it} />
            </button>
          ))}
        </div>
      </div>
    );
  }
  if (kind === "match") {
    const used = new Set(draft.match.filter((m): m is string => m !== null));
    return (
      <div className="lp-match">
        <div className="lp-match__col" aria-label={t("Columna izquierda")}>
          {(step.left ?? []).map((l, i) => (
            <button key={l} type="button" disabled={locked}
              className={`lp-tile lp-tile--small${leftPick === i ? " is-on" : ""}${draft.match[i] ? " is-paired" : ""}`}
              aria-pressed={leftPick === i}
              onClick={() => {
                play("tap");
                if (draft.match[i]) {
                  const next = [...draft.match];
                  next[i] = null;
                  setDraft({ ...draft, match: next });
                  setLeftPick(i);
                } else setLeftPick(leftPick === i ? null : i);
              }}>
              <InlineRich text={l} />
              {draft.match[i] && (
                <span className="lp-match__pair">
                  → <InlineRich text={draft.match[i]!} />
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="lp-match__col" aria-label={t("Columna derecha")}>
          {(step.right ?? []).map((r) => (
            <button key={r} type="button" disabled={locked || used.has(r) || leftPick === null}
              className={`lp-tile lp-tile--small${used.has(r) ? " is-used" : ""}`}
              onClick={() => {
                if (leftPick === null) return;
                play("tap");
                const next = [...draft.match];
                next[leftPick] = r;
                setDraft({ ...draft, match: next });
                const free = next.findIndex((m) => m === null);
                setLeftPick(free === -1 ? null : free);
              }}>
              <InlineRich text={r} />
            </button>
          ))}
        </div>
        <p className="muted small lp-match__help">{t("Toca un elemento de la izquierda y luego su pareja.")}</p>
      </div>
    );
  }
  return (
    <>
      {step.explanation && <RichText text={step.explanation} className="lp-info" />}
      {step.figure && <TheoryFigure figure={step.figure} />}
    </>
  );
}

/** «Escuchar» en las tarjetas de teoría (voz del sistema; si no hay, no se enseña). */
function ReadAloud({ text }: { text: string }) {
  const { supported, speaking, speak, stop } = useSpeech();
  if (!supported) return null;
  return (
    <button type="button" className="btn btn--ghost btn--sm lp-read" aria-pressed={speaking} onClick={() => (speaking ? stop() : speak(text))}>
      {speaking ? t("⏹ Parar") : t("🔊 Escuchar")}
    </button>
  );
}

export function LessonPlayer({ navigate, mode }: { navigate: Navigate; mode: PlayerMode }) {
  const { settings } = useStore();
  const [sounds, setSounds] = useState(settings?.learn_sounds !== false);
  const [lesson, setLesson] = useState<LessonFull | null>(null);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"loading" | "steps" | "done" | "streak">("loading");
  const [queue, setQueue] = useState<Queued[]>([]);
  const [total, setTotal] = useState(0);
  const [doneCount, setDoneCount] = useState(0);
  const [firstTryOk, setFirstTryOk] = useState(0);
  const [xp, setXp] = useState(0);
  const [combo, setCombo] = useState(0);
  const [comboFlash, setComboFlash] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft());
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [hintsShown, setHintsShown] = useState(0);
  const [confidence, setConfidence] = useState<"high" | "low" | null>(null);
  const [workedSeen, setWorkedSeen] = useState(false);
  const [showWhy, setShowWhy] = useState(false);
  const [examRows, setExamRows] = useState<ExamRow[]>([]);
  const [deadline, setDeadline] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [completion, setCompletion] = useState<CompleteResult | null>(null);
  const [gameAfter, setGameAfter] = useState<GameState | null>(null);
  const [guideOpen, setGuideOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef(Date.now());
  // ¿Ya había XP hoy antes de esta sesión? Si no, al acabar se celebra la racha.
  const hadXpToday = useRef<boolean | null>(null);
  const isExam = mode.kind === "exam";
  const modeKey = JSON.stringify(mode);

  function resetStepUi(next?: PublicStep) {
    setResult(null);
    setHintsShown(0);
    setConfidence(null);
    setWorkedSeen(false);
    setShowWhy(false);
    setDraft(emptyDraft(next));
  }

  useEffect(() => {
    let cancelled = false;
    setPhase("loading");
    setError(null);
    void api.learn
      .game()
      .then((g) => (hadXpToday.current = g.today_xp > 0))
      .catch(() => undefined);
    const load: Promise<{ steps: PublicStep[]; lesson: LessonFull | null; title: string; minutes?: number }> =
      mode.kind === "lesson"
        ? api.learn.lesson(mode.lessonId).then((l) => ({ steps: l.steps, lesson: l, title: l.title }))
        : mode.kind === "review"
          ? api.learn.review().then((r) => ({ steps: r.steps, lesson: null, title: t("Repaso de fallos") }))
          : mode.kind === "practice"
            ? api.learn.practice(mode.courseId, mode.concept, mode.objective).then((r) => ({ steps: r.steps, lesson: null, title: r.title }))
            : api.learn.exam(mode.courseId).then((r) => ({ steps: r.steps, lesson: null, title: r.title, minutes: r.minutes }));
    load
      .then(({ steps, lesson: l, title: t, minutes }) => {
        if (cancelled) return;
        setLesson(l);
        setTitle(t);
        const q = steps.map((step) => ({ step, firstTry: true }));
        setQueue(q);
        setTotal(steps.filter((x) => x.kind !== "info").length);
        setDoneCount(0);
        setFirstTryOk(0);
        setXp(0);
        setCombo(0);
        setExamRows([]);
        setCompletion(null);
        setGameAfter(null);
        setDeadline(minutes ? Date.now() + minutes * 60_000 : null);
        startedAt.current = Date.now();
        resetStepUi(q[0]?.step);
        setPhase(q.length ? "steps" : "done");
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modeKey]);

  useEffect(() => {
    if (!deadline || phase !== "steps") return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [deadline, phase]);

  useEffect(() => {
    if (comboFlash === null) return;
    const t = window.setTimeout(() => setComboFlash(null), 1600);
    return () => window.clearTimeout(t);
  }, [comboFlash]);

  const current = queue[0];
  const remainingSec = deadline ? Math.max(0, Math.round((deadline - now) / 1000)) : null;

  const finish = useCallback(async () => {
    play("complete", sounds);
    vibrate([30, 40, 30]);
    setElapsed(Math.round((Date.now() - startedAt.current) / 1000));
    setPhase("done");
    if (lesson) {
      const r = await api.learn.complete(lesson.id, firstTryOk, total, Math.round((Date.now() - startedAt.current) / 1000)).catch(() => null);
      if (r) {
        setXp((x) => x + r.xp);
        setCompletion(r);
        setGameAfter(r.game);
      }
    } else {
      const g = await api.learn.game().catch(() => null);
      if (g) setGameAfter(g);
    }
  }, [lesson, firstTryOk, total, sounds]);

  useEffect(() => {
    if (isExam && remainingSec === 0 && phase === "steps") {
      setExamRows((rows) => [...rows, ...queue.map((q) => ({ step: q.step, result: null, skipped: true }))]);
      setQueue([]);
      void finish();
    }
  }, [isExam, remainingSec, phase, queue, finish]);

  const advance = (correct: boolean) => {
    const [head, ...rest] = queue;
    // Lo fallado vuelve al final una vez (no en examen ni en el repaso de fallos).
    const retry = !correct && head && !isExam && mode.kind !== "review" && head.firstTry;
    const next = retry ? [...rest, { step: head.step, firstTry: false }] : rest;
    if ((correct || !retry) && head && head.step.kind !== "info") setDoneCount((n) => n + 1);
    setQueue(next);
    resetStepUi(next[0]?.step);
    if (!next.length) void finish();
  };

  const submit = async (skip = false) => {
    if (!current || checking) return;
    if (current.step.kind === "info") {
      advance(true);
      return;
    }
    setChecking(true);
    try {
      const r = await api.learn.answer(current.step.id, skip ? null : responseOf(current.step, draft), {
        firstTry: current.firstTry,
        token: current.step.token,
        confidence,
        usedHint: hintsShown > 0,
        combo: combo + 1,
      });
      setXp((x) => x + r.xp);
      if (r.correct) {
        const c = combo + 1;
        setCombo(c);
        if (current.firstTry) setFirstTryOk((n) => n + 1);
        if (!isExam) {
          if (c === 3 || (c >= 5 && c % 5 === 0)) {
            setComboFlash(c);
            play("combo", sounds);
          } else play("correct", sounds);
          vibrate(25);
        }
      } else {
        setCombo(0);
        if (!isExam) {
          play("wrong", sounds);
          vibrate([60, 40, 60]);
        }
      }
      if (isExam) {
        setExamRows((rows) => [...rows, { step: current.step, result: r, skipped: skip }]);
        advance(true);
      } else setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  };

  // Teclado: Enter = comprobar/continuar; 1–9 = elegir opción.
  useEffect(() => {
    if (phase !== "steps" || !current) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === "Enter" && !e.shiftKey && tag !== "TEXTAREA" && tag !== "BUTTON") {
        e.preventDefault();
        if (result) advance(result.correct);
        else if (ready(current.step, draft)) void submit();
        return;
      }
      if (result || tag === "INPUT" || tag === "TEXTAREA") return;
      const n = Number(e.key);
      const k = effectiveKind(current.step);
      if (n >= 1 && k === "choice" && n <= (current.step.options?.length ?? 0)) setDraft({ ...draft, choice: [n - 1] });
      if (n >= 1 && n <= 2 && k === "truefalse") setDraft({ ...draft, tf: n === 1 });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const progress = total ? doneCount / total : phase === "done" ? 1 : 0;

  if (error) return <ErrorBox message={error} />;
  if (phase === "loading") return <Loading />;

  const showWorked = phase === "steps" && current?.step.worked && !workedSeen && !result;
  const accuracy = total ? Math.round(((isExam ? examRows.filter((r) => r.result?.correct).length : firstTryOk) / total) * 100) : 100;
  const praise = PRAISE[(doneCount + xp) % PRAISE.length];
  const celebrateStreak = Boolean(gameAfter && hadXpToday.current === false && gameAfter.today_xp > 0 && gameAfter.streak > 0);

  return (
    <div className={`lp${result ? (result.correct ? " is-ok" : " is-ko") : ""}`}>
      {phase === "steps" && current && (
        <>
          <PlayerTop
            exitHref="/aprender"
            onExit={linkTo(navigate, { name: "learn" })}
            progress={progress}
            hot={combo >= 3}
            xp={xp}
            remainingSec={remainingSec}
            sounds={sounds}
            onToggleSounds={() => setSounds((v) => !v)}
            tx={t}
          >
            {lesson && (
              <button type="button" className="lp-icon" aria-label={t("Guía de la lección")} onClick={() => setGuideOpen(true)}>
                📘
              </button>
            )}
          </PlayerTop>
          <p className="lp-title muted small">{title}</p>

          <ComboFlash n={comboFlash} tx={t} />

          <main className="lp-body">
            {showWorked ? (
              <section className="lp-card">
                <p className="lp-kicker">{t("Ejemplo resuelto")}</p>
                <RichText text={current.step.worked!} className="lp-info" />
                {current.step.source && <p className="lp-source">📖 {current.step.source}</p>}
              </section>
            ) : (
              <section className="lp-card">
                {!current.firstTry && <p className="lp-kicker lp-kicker--again">{t("Otra vez: este se te resistió")}</p>}
                {mode.kind !== "lesson" && current.step.lesson_title && <p className="lp-kicker">{current.step.lesson_title}</p>}
                <h1 className="lp-instruction">{instruction(current.step)}</h1>
                {current.step.kind === "info" && <ReadAloud key={current.step.id} text={`${current.step.prompt}. ${current.step.explanation ?? ""}`} />}
                <QuestionBubble mascot="pilo" mood={result ? (result.correct ? "cheer" : "sad") : "think"}>
                  <Prompt step={current.step} draft={draft} />
                </QuestionBubble>
                <StepInput key={current.step.id + (current.firstTry ? "a" : "b")} step={current.step} draft={draft} setDraft={setDraft} locked={!!result || checking} />
                {!result && !isExam && (current.step.hints ?? []).length > 0 && (
                  <div className="lp-hints">
                    {(current.step.hints ?? []).slice(0, hintsShown).map((h, i) => (
                      <p key={i} className="hint">
                        💡 <InlineRich text={h} />
                      </p>
                    ))}
                    {hintsShown < (current.step.hints ?? []).length && (
                      <button type="button" className="btn btn--ghost btn--sm" onClick={() => setHintsShown((n) => n + 1)}>
                        💡 {hintsShown ? t("Otra pista") : t("Pista")}
                      </button>
                    )}
                  </div>
                )}
                {/* En la teoría, la fuente es lo que hay que ir a leer: siempre a la vista. */}
                {current.step.source && (
                  <p className={`lp-source${current.step.kind === "info" ? "" : " detail-only"}`}>
                    📖{" "}
                    {current.step.kind === "info" && current.step.cite ? (
                      <a href={api.materials.fileUrl(current.step.cite.material_id, current.step.cite.page)} target="_blank" rel="noreferrer">
                        {t("Amplíalo en el manual: {0}", { 0: current.step.source })}
                      </a>
                    ) : current.step.kind === "info" ? (
                      t("Amplíalo en el manual: {0}", { 0: current.step.source })
                    ) : (
                      current.step.source
                    )}
                  </p>
                )}
              </section>
            )}
          </main>

          <PlayerFoot result={result ? (result.correct ? "ok" : "ko") : null}>
              {showWorked ? (
                <>
                  <span />
                  <button type="button" className="lp-btn lp-btn--go" autoFocus onClick={() => setWorkedSeen(true)}>
                    {t("Ahora tú")}
                  </button>
                </>
              ) : result ? (
                <>
                  <div className="lp-verdict" role="status" aria-live="polite">
                    <p className="lp-verdict__title">
                      <span aria-hidden>{result.correct ? "✔" : "✖"}</span>{" "}
                      {result.correct ? praise : result.confident_wrong ? t("Lo tenías claro… pero no") : t("Respuesta correcta:")}
                    </p>
                    {!result.correct && result.solution && (
                      <p className="lp-verdict__solution">
                        <InlineRich text={result.solution} />
                      </p>
                    )}
                    {result.option_feedback.map((f, i) => (
                      <p key={i} className="lp-verdict__fb">
                        <InlineRich text={f} />
                      </p>
                    ))}
                    {(result.explanation || result.source) && (
                      <button type="button" className="lp-why" aria-expanded={showWhy} onClick={() => setShowWhy((v) => !v)}>
                        {showWhy ? t("Ocultar explicación") : t("¿Por qué?")}
                      </button>
                    )}
                    {showWhy && (
                      <div className="lp-verdict__expl">
                        {result.explanation && <RichText text={result.explanation} />}
                        {result.source && <p className="small">📖 {result.source}</p>}
                      </div>
                    )}
                  </div>
                  <button type="button" className={`lp-btn ${result.correct ? "lp-btn--go" : "lp-btn--bad"}`} autoFocus onClick={() => advance(result.correct)}>
                    {t("Seguir")}
                  </button>
                </>
              ) : (
                <>
                  <div className="lp-foot__left">
                    {current.step.kind !== "info" && (
                      <button type="button" className="lp-btn lp-btn--ghost" disabled={checking} onClick={() => void submit(true)}>
                        {t("Saltar")}
                      </button>
                    )}
                    {current.step.kind !== "info" && !isExam && (
                      <span className="lp-conf" role="group" aria-label={t("¿Lo tienes claro?")}>
                        <button type="button" aria-pressed={confidence === "high"} className={confidence === "high" ? "is-on" : ""} title={t("Lo tengo claro")}
                          onClick={() => setConfidence(confidence === "high" ? null : "high")}>
                          😎
                        </button>
                        <button type="button" aria-pressed={confidence === "low"} className={confidence === "low" ? "is-on" : ""} title={t("Tengo dudas")}
                          onClick={() => setConfidence(confidence === "low" ? null : "low")}>
                          🤔
                        </button>
                      </span>
                    )}
                  </div>
                  <button type="button" className="lp-btn lp-btn--go" disabled={checking || !ready(current.step, draft)} onClick={() => void submit()}>
                    {current.step.kind === "info" ? t("Seguir") : checking ? "…" : isExam ? t("Responder") : t("Comprobar")}
                  </button>
                </>
              )}
          </PlayerFoot>
        </>
      )}

      {phase === "done" && (
        <EndScreen
          mascot="pilo"
          tx={t}
          title={
            isExam
              ? t("¡Examen terminado!")
              : mode.kind === "lesson"
                ? completion?.perfect
                  ? t("¡Lección perfecta!")
                  : t("¡Lección completada!")
                : total
                  ? t("¡Práctica completada!")
                  : t("Nada que repasar hoy")
          }
          stats={total > 0 ? { xp, accuracy, seconds: elapsed } : null}
          note={completion?.chest_available ? t("🏅 ¡Unidad terminada! Recoge su insignia en el camino.") : null}
          actions={
            <>
            <button type="button" className="lp-btn lp-btn--go" autoFocus onClick={() => (celebrateStreak ? setPhase("streak") : navigate({ name: "learn" }))}>
              {t("Seguir")}
            </button>
            {lesson?.next_lesson_id && !celebrateStreak && (
              <a className="lp-btn lp-btn--ghost" href={`/aprender/leccion/${lesson.next_lesson_id}`} onClick={linkTo(navigate, { name: "lesson", id: lesson.next_lesson_id })}>
                {t("Siguiente lección")}
              </a>
            )}
            </>
          }
        >
          {isExam && examRows.length > 0 && (
            <ol className="exam-results">
              {examRows.map((r, i) => (
                <li key={i} className={r.result?.correct ? "is-ok" : "is-ko"}>
                  <div className="exam-results__q">
                    <span aria-hidden>{r.result?.correct ? "✓" : r.skipped ? "—" : "✗"}</span> <RichText text={r.step.prompt} />
                  </div>
                  {!r.result?.correct && r.result?.solution && (
                    <div className="small">
                      {t("Solución:")} <strong><InlineRich text={r.result.solution} /></strong>
                    </div>
                  )}
                </li>
              ))}
            </ol>
          )}
        </EndScreen>
      )}

      {phase === "streak" && gameAfter && (
        <StreakScreen game={gameAfter} weekdays={WEEKDAYS} tx={t} message={t("¡Has estudiado hoy! Vuelve mañana para que siga creciendo.")}
          onContinue={() => navigate({ name: "learn" })} />
      )}

      {lesson && <GuideModal lessonId={guideOpen ? lesson.id : null} onClose={() => setGuideOpen(false)} />}
    </div>
  );
}
