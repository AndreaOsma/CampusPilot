import { useEffect, useState } from "react";
import { api, type FeynmanPick, type FeynmanRating, type FeynmanResult } from "../api";
import { RichText } from "../lib/rich";
import { FormStatus, Loading, useSubmit } from "../ui";
import { t } from "../i18n";
import { Check, CircleCheck, CircleDashed, Icon, MessageCircle, Repeat, X } from "../vendor/icons";

const RATING_LABEL: Record<FeynmanRating, string> = { mastered: t("Lo dominas"), almost: t("Casi"), review: t("Repásalo") };
const RATING_ICON: Record<FeynmanRating, string> = { mastered: CircleCheck, almost: CircleDashed, review: Repeat };
const MIN_CHARS = 20;

/** Un concepto: se explica con palabras propias y la IA lo valora con el método Feynman. */
function ConceptForm({ item, onDone }: { item: FeynmanPick["concepts"][number]; onDone: () => void }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<FeynmanResult | null>(null);
  const { state, run } = useSubmit();
  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    const r = await run(() => api.learn.feynmanCheck(item.step_id, item.concept, text.trim()), t("Valorado"));
    if (r) setResult(r);
  };
  if (result) {
    const f = result.feedback;
    return (
      <div className="feynman__result" aria-live="polite">
        <p className={`feynman__rating feynman__rating--${result.rating}`}>
          <Icon svg={RATING_ICON[result.rating]} /> {RATING_LABEL[result.rating]}
        </p>
        <p>{f.summary}</p>
        <p className="small muted">
          <Icon svg={f.correct ? Check : X} /> {t("Correcta")} · <Icon svg={f.clear ? Check : X} /> {t("Clara y sin jerga")} · <Icon svg={f.examples ? Check : X} /> {t("Con ejemplos")}
        </p>
        {f.gaps.length > 0 && (
          <ul className="feynman__gaps">
            {f.gaps.map((g, i) => (
              <li key={i}>
                <strong>{g.point}</strong>
                <RichText text={g.theory} />
              </li>
            ))}
          </ul>
        )}
        {f.follow_up && <p className="small"><Icon svg={MessageCircle} /> {f.follow_up}</p>}
        <button type="button" className="btn btn--ghost btn--sm" onClick={onDone}>
          {t("Seguir")}
        </button>
      </div>
    );
  }
  return (
    <form onSubmit={send} className="feynman__form">
      <label htmlFor={`fy-${item.step_id}-${item.concept}`}>{t("Explica «{0}» con tus palabras, como si se lo contaras a alguien que no sabe nada del tema.", { 0: item.concept })}</label>
      <textarea
        id={`fy-${item.step_id}-${item.concept}`}
        rows={5}
        maxLength={4000}
        value={text}
        disabled={state.status === "loading"}
        onChange={(e) => setText(e.target.value)}
        placeholder={t("Escribe tu explicación…")}
      />
      <div className="feynman__actions">
        <button type="submit" className="btn" disabled={state.status === "loading" || text.trim().length < MIN_CHARS}>
          {state.status === "loading" ? t("Valorando…") : t("Comprobar mi explicación")}
        </button>
        <button type="button" className="btn btn--ghost" disabled={state.status === "loading"} onClick={onDone}>
          {t("Saltar")}
        </button>
      </div>
      {text.trim().length < MIN_CHARS && <p className="small muted">{t("Escribe al menos {0} caracteres.", { 0: MIN_CHARS })}</p>}
      {state.status === "error" && <FormStatus state={state} />}
    </form>
  );
}

/** Comprobador Feynman al acabar un repaso de teoría. No aparece si no procede (p. ej. material evaluable) y se puede saltar. */
export function FeynmanChecker({ stepIds, missedIds }: { stepIds: number[]; missedIds: number[] }) {
  const [pick, setPick] = useState<FeynmanPick | null>(null);
  const [failed, setFailed] = useState(false);
  const [index, setIndex] = useState(0);
  const [skipped, setSkipped] = useState(false);
  useEffect(() => {
    let cancelled = false;
    api.learn
      .feynmanPick(stepIds, missedIds)
      .then((p) => !cancelled && setPick(p))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (failed || skipped) return null;
  if (!pick) return <Loading />;
  const item = pick.concepts[index];
  if (!pick.available || !item) return null;
  return (
    <section className="feynman" aria-label={t("Comprobador Feynman")}>
      <h3>{t("Comprobador Feynman")}</h3>
      <p className="small muted">
        {t("Concepto {0} de {1}", { 0: index + 1, 1: pick.concepts.length })}
        {item.missed ? ` · ${t("lo has fallado")}` : ""}
      </p>
      <ConceptForm
        key={`${item.step_id}-${item.concept}`}
        item={item}
        onDone={() => (index + 1 < pick.concepts.length ? setIndex(index + 1) : setSkipped(true))}
      />
      <button type="button" className="btn btn--ghost btn--sm" onClick={() => setSkipped(true)}>
        {t("No ahora")}
      </button>
    </section>
  );
}
