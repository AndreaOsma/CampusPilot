import { useEffect, useState } from "react";
import { api, type CourseSummary, type GameState, type LessonSummary } from "../api";
import { GuideModal } from "../components/Guide";
import { Generator, Mastery } from "../components/LearnExtras";
import { SyllabusProgress } from "../components/Syllabus";
import { LibraryCard, TutorCard } from "../components/Library";
import { WeekPlanCard } from "../components/WeekPlan";
import { WEEKDAYS } from "../lib/format";
import { linkTo, type Navigate } from "../router";
import { GameBar, Mascot, PathView, play, Quests, Shop, StreakCard, type PathUnit } from "../vendor/learn-game";
import { useStore } from "../store";
import { Card, ConfirmDelete, Empty, ErrorBox, FormStatus, Loading, useLoad, useSubmit } from "../ui";
import { t } from "../i18n";

const QUEST_ICON: Record<string, string> = { xp: "⚡", lessons: "📗", combo: "🔥", perfect: "🎯", correct: "✅" };

function SubjectPicker({
  options,
  selectedId,
  onSelect,
}: {
  options: { label: string; items: { id: number; name: string; lessons: number }[] }[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const total = options.reduce((a, g) => a + g.items.length, 0);
  if (!total) return <span className="learn-bar__course">{t("Aprender")}</span>;
  return (
    <select className="learn-bar__course" aria-label={t("Asignatura")} value={selectedId ?? ""} onChange={(e) => onSelect(Number(e.target.value))}>
      {selectedId === null && <option value="">{t("Elige asignatura…")}</option>}
      {options
        .filter((g) => g.items.length)
        .map((g) => (
          <optgroup key={g.label} label={g.label}>
            {g.items.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
                {x.lessons ? t(" · {0} lecciones", { 0: x.lessons }) : ""}
              </option>
            ))}
          </optgroup>
        ))}
    </select>
  );
}

/** El curso en el formato del camino compartido. */
function toPath(course: CourseSummary): PathUnit[] {
  return (course.units ?? []).map((u) => ({
    id: u.id,
    title: u.title,
    done: u.done,
    badgeClaimed: u.chest_claimed,
    lessons: u.lessons.map((l: LessonSummary) => ({
      id: l.id,
      title: l.title,
      done: l.done,
      locked: l.locked,
      current: l.id === course.next_lesson_id,
      level: l.level,
      href: `/aprender/leccion/${l.id}`,
      detail:
        `${l.steps} ${t("ejercicios")}${l.done ? ` · nivel ${l.level}/5` : ""}` +
        (l.best_ratio !== null ? t(" · mejor {0} %", { 0: Math.round(l.best_ratio * 100) }) : ""),
    })),
  }));
}

export function Learn({ navigate }: { navigate: Navigate }) {
  const { settings } = useStore();
  const sounds = settings?.learn_sounds !== false;
  const { subjects } = useStore();
  const courses = useLoad(() => api.learn.courses());
  const gameQ = useLoad(() => api.learn.game());
  const [subjectId, setSubjectId] = useState<number | null>(() => {
    try {
      return Number(localStorage.getItem("campus-learn-subject")) || null;
    } catch {
      return null;
    }
  });
  const list = courses.data ?? [];
  const loose = list.filter((x) => x.subject_id === null);
  const bySubject = new Map(list.filter((x) => x.subject_id !== null).map((x) => [x.subject_id as number, x]));
  // Un curso por asignatura: primero las que ya tienen lecciones, luego las que cursas, luego el resto pendiente.
  const options = [
    { label: t("Con lecciones"), items: subjects.filter((x) => bySubject.has(x.id)) },
    { label: t("Cursando"), items: subjects.filter((x) => !bySubject.has(x.id) && x.status === "enrolled") },
    { label: t("Pendientes"), items: subjects.filter((x) => !bySubject.has(x.id) && (x.status === "pending" || x.status === "failed")) },
  ].map((g) => ({ label: g.label, items: g.items.map((x) => ({ id: x.id, name: x.name, lessons: bySubject.get(x.id)?.lessons_total ?? 0 })) }));
  const known = options.some((g) => g.items.some((x) => x.id === subjectId));
  const selectedSubjectId = known ? subjectId : (options[0].items[0] ?? options[1].items[0])?.id ?? null;
  const selectedSubject = subjects.find((x) => x.id === selectedSubjectId) ?? null;
  const selectedId = selectedSubjectId !== null ? bySubject.get(selectedSubjectId)?.id ?? null : null;
  const course = useLoad(() => (selectedId ? api.learn.course(selectedId) : Promise.resolve(null)), [selectedId]);
  const [guide, setGuide] = useState<number | null>(null);
  const [reward, setReward] = useState<string | null>(null);
  const importState = useSubmit();
  const game = gameQ.data;

  useEffect(() => {
    if (!selectedSubjectId) return;
    try {
      localStorage.setItem("campus-learn-subject", String(selectedSubjectId));
    } catch {
      /* ignorar */
    }
  }, [selectedSubjectId]);

  useEffect(() => {
    if (!reward) return;
    const t = window.setTimeout(() => setReward(null), 2600);
    return () => window.clearTimeout(t);
  }, [reward]);

  const claim = async (id: string) => {
    const r = await api.learn.claimQuest(id).catch(() => null);
    if (r) {
      play("chest", sounds);
      gameQ.setData(r.game);
      setReward(`+${r.gems} ✨`);
    }
  };
  const chest = async (unitId: number) => {
    const r = await api.learn.openChest(unitId).catch(() => null);
    if (r) {
      play("chest", sounds);
      gameQ.setData(r.game);
      setReward(t("🎓 ¡Insignia de unidad! +{0} ✨", { 0: r.gems }));
      void course.reload();
    }
  };
  const buy = async () => {
    const g = await api.learn.buy("freeze").catch(() => null);
    if (g) {
      play("chest", sounds);
      gameQ.setData(g);
      setReward(t("🌴 Día libre guardado"));
    }
  };
  const onImport = async (file: File | undefined) => {
    if (!file || !selectedSubjectId) return;
    const res = await importState.run(() => api.learn.importCourse(file, selectedSubjectId), t("Lecciones añadidas al curso"));
    if (res) {
      void courses.reload();
      void course.reload();
    }
  };
  const assign = async (courseId: number, sid: number) => {
    const res = await importState.run(() => api.learn.setCourseSubject(courseId, sid), t("Curso asignado"));
    if (res) {
      setSubjectId(sid);
      void courses.reload();
    }
  };

  const c = course.data;

  return (
    <div className="page learn-page">
      <GameBar game={game ?? null} tx={t}>
        <SubjectPicker options={options} selectedId={selectedSubjectId} onSelect={setSubjectId} />
      </GameBar>
      {reward && (
        <div className="toast toast--reward" role="status">
          {reward}
        </div>
      )}

      {courses.loading ? (
        <Loading />
      ) : courses.error ? (
        <ErrorBox message={courses.error} onRetry={courses.reload} />
      ) : null}

      {loose.map((x) => (
        <Card key={x.id} title={t("Curso sin asignatura · {0}", { 0: x.title })}>
          <p className="muted small">{t("Cada curso pertenece a una asignatura. Elige la suya y sus lecciones (con tu progreso) pasan a su curso.")}</p>
          <select aria-label={t("Asignatura para {0}", { 0: x.title })} defaultValue="" onChange={(e) => e.target.value && void assign(x.id, Number(e.target.value))}>
            <option value="">{t("Elige asignatura…")}</option>
            {subjects.map((sub) => (
              <option key={sub.id} value={sub.id}>
                {sub.name}
              </option>
            ))}
          </select>
        </Card>
      ))}

      {!courses.loading && !courses.error && !selectedId && (
        <Card>
          <div className="learn-empty">
            <Mascot kind="pilo" mood="think" size={110} />
            <Empty icon="" title={selectedSubject ? t("Aún no hay lecciones de {0}", { 0: selectedSubject.name }) : t("Elige una asignatura")}>
              {selectedSubject
                ? t("Sube material de esta asignatura (más abajo) y saldrán sus lecciones.")
                : subjects.length
                  ? t("Elige arriba la asignatura que quieres estudiar.")
                  : t("Crea tu carrera o instala tu universidad en Módulos para empezar.")}
            </Empty>
          </div>
        </Card>
      )}

      <div className="learn-layout">
        <div className="learn-main">
          {selectedSubjectId && <WeekPlanCard subjectId={selectedSubjectId} navigate={navigate} />}
          {c && (
            <>
              <div className="learn-hello">
                <Mascot kind="pilo" mood={c.next_lesson_id ? "happy" : "cheer"} size={64} />
                <p>
                  {c.next_lesson_id ? t("¡Vamos con la siguiente!") : t("¡Curso completado! Repasa para subir de nivel.")}
                  <span className="muted small">
                    {" "}
                    · {c.lessons_done}/{c.lessons_total} {t("lecciones")}
                  </span>
                </p>
              </div>
              <PathView
                units={toPath(c)}
                tx={t}
                onGo={(l, e) => linkTo(navigate, { name: "lesson", id: Number(l.id) })(e)}
                onBadge={(id) => void chest(Number(id))}
                extra={(l) => {
                  const has = c.units?.flatMap((u) => u.lessons).find((x) => x.id === l.id)?.has_theory;
                  return (
                    <button type="button" className="btn btn--ghost btn--sm dpop__guide" onClick={() => setGuide(Number(l.id))}>
                      {t("📘 Guía")}
                      {has ? "" : t(" (vacía)")}
                    </button>
                  );
                }}
              />
            </>
          )}
        </div>

        <aside className="learn-side">
          {game && <StreakCard game={game} weekdays={WEEKDAYS} tx={t} />}
          {game && <Quests game={game} icons={QUEST_ICON} tx={t} onClaim={(id) => void claim(id)} />}
          {c && (
            <Card title={t("Practicar")}>
              <div className="practice-grid">
                <a className="practice-btn" href="/aprender/repaso" onClick={linkTo(navigate, { name: "review" })}>
                  <span aria-hidden>🔁</span> {t("Repasar fallos")}
                </a>
                <a className="practice-btn" href={`/aprender/practica/${c.id}`} onClick={linkTo(navigate, { name: "practice", courseId: c.id, concept: "" })}>
                  <span aria-hidden>🎯</span> {t("Lo más flojo")}
                </a>
                <a className="practice-btn" href={`/aprender/examen/${c.id}`} onClick={linkTo(navigate, { name: "exam", courseId: c.id })}>
                  <span aria-hidden>📝</span> {t("Examen")}
                </a>
              </div>
            </Card>
          )}
          {selectedSubjectId && <SyllabusProgress subjectId={selectedSubjectId} navigate={navigate} />}
          {game && <Shop game={game} tx={t} onBuy={() => void buy()} />}
          {c && <Mastery courseId={c.id} navigate={navigate} />}
        </aside>
      </div>

      {selectedSubjectId && <TutorCard key={selectedSubjectId} subjectId={selectedSubjectId} />}

      <Generator navigate={navigate} subjectId={selectedSubjectId} />

      {selectedSubject && <LibraryCard subjectId={selectedSubject.id} forbidden={selectedSubject.ai_policy === "forbidden"} />}

      {selectedSubject && (
        <Card title={t("Curso de {0}", { 0: selectedSubject.name })} className="detail-only">
          <div className="form-actions">
            {c && (
              <>
                <a className="btn btn--ghost btn--sm" href={api.learn.exportUrl(c.id)} download={`${c.slug}.json`}>
                  {t("⬇ Exportar")}
                </a>
                <a className="btn btn--ghost btn--sm" href={api.learn.ankiUrl(c.id)} download>
                  {t("⬇ Anki")}
                </a>
                <a className="btn btn--ghost btn--sm" href={api.learn.ankiUrl(c.id, true)} download>
                  {t("⬇ Anki (solo fallos)")}
                </a>
                <ConfirmDelete label={t("Borrar sus lecciones y progreso")} onConfirm={() => void api.learn.removeCourse(c.id).then(() => courses.reload())} />
              </>
            )}
            <label className="btn btn--ghost btn--sm file-btn">
              {t("⬆ Añadir lecciones (.json)")}
              <input type="file" accept="application/json,.json" className="sr-only" onChange={(e) => void onImport(e.target.files?.[0])} />
            </label>
          </div>
          <FormStatus state={importState.state} />
        </Card>
      )}

      <GuideModal lessonId={guide} onClose={() => setGuide(null)} />
    </div>
  );
}
