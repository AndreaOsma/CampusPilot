"""Capa de juego de Aprender: chispas, misiones diarias, insignias de unidad y días libres.

Sin vidas, a propósito: en una app de estudio, fallar no puede impedir seguir practicando.
La lógica es la de la librería compartida `learn_game` (copia de dev/lib/learn-game); aquí
solo se leen y guardan los datos en `LearnDay` / `LearnProfile`.

- **Chispas** (`gems` en la API): se ganan con las misiones diarias y las insignias de final
  de unidad; se canjean por días libres.
- **Misiones**: tres al día (XP de la meta, lecciones, y una que rota según el día).
- **Día libre** (`freeze` en la API): si un día no estudias y tienes uno guardado, ese día
  cuenta para la racha. Se gasta solo.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import clock, i18n, models
from .learn_game import quests as lg_quests
from .learn_game import rewards
from .learn_game import streak as lg_streak
from .learn_game.i18n import tr as lg_tr

PRICE_FREEZE = rewards.PRICE_FREEZE
MAX_FREEZES = rewards.MAX_FREEZES
CHEST_GEMS = rewards.BADGE_GEMS
PERFECT_BONUS_XP = rewards.PERFECT_BONUS_XP


def profile(db: Session) -> models.LearnProfile:
    p = db.get(models.LearnProfile, 1)
    if p is None:
        p = models.LearnProfile(id=1, gems=0, streak_freezes=0)
        db.add(p)
        db.flush()
    return p


def day(db: Session, d: Optional[date] = None) -> models.LearnDay:
    d = d or clock.today()
    row = db.get(models.LearnDay, d)
    if row is None:
        row = models.LearnDay(date=d, xp=0, lessons=0, perfect_lessons=0, best_combo=0, correct=0, claimed=[], frozen=False)
        db.add(row)
        db.flush()
    return row


def _active(db: Session):
    return db.query(models.LearnDay).filter((models.LearnDay.xp > 0) | (models.LearnDay.frozen.is_(True)))


def settle_streak(db: Session, today: Optional[date] = None) -> None:
    """Rellena con días libres los días perdidos desde el último día activo (si alcanzan)."""
    today = today or clock.today()
    p = profile(db)
    if p.last_settled == today:
        return
    last = _active(db).order_by(models.LearnDay.date.desc()).first()
    missing = lg_streak.days_to_freeze(today, last.date if last else None, p.streak_freezes)
    for d in missing:
        day(db, d).frozen = True
    p.streak_freezes -= len(missing)
    p.last_settled = today
    db.flush()


def streak(db: Session, today: Optional[date] = None) -> int:
    return lg_streak.streak(today or clock.today(), [r.date for r in _active(db)])


def week(db: Session, today: Optional[date] = None) -> list[dict]:
    today = today or clock.today()
    monday = today - timedelta(days=today.weekday())
    rows = db.query(models.LearnDay).filter(models.LearnDay.date.between(monday, monday + timedelta(days=6)))
    return lg_streak.week(today, {r.date: {"xp": r.xp, "frozen": r.frozen} for r in rows})


def _quest_defs(lg: str, goal_xp: int):
    fixed = [
        lg_quests.QuestDef("xp", i18n.tr(lg, "Gana {n} XP", n=goal_xp), "xp", goal_xp, 10),
        lg_quests.QuestDef("lessons", i18n.tr(lg, "Completa 2 lecciones"), "lessons", 2, 10),
    ]
    rotating = [
        lg_quests.QuestDef("combo", i18n.tr(lg, "Consigue 5 aciertos seguidos"), "combo", 5, 15),
        lg_quests.QuestDef("perfect", i18n.tr(lg, "Termina una lección sin fallos"), "perfect", 1, 15),
        lg_quests.QuestDef("correct", i18n.tr(lg, "Acierta 15 ejercicios"), "correct", 15, 15),
    ]
    return fixed, rotating


def quests(db: Session, goal_xp: int, today: Optional[date] = None) -> list[dict]:
    today = today or clock.today()
    d = db.get(models.LearnDay, today)
    counters = {"xp": d.xp, "lessons": d.lessons, "perfect": d.perfect_lessons, "combo": d.best_combo, "correct": d.correct} if d else {}
    fixed, rotating = _quest_defs(i18n.lang(db), goal_xp)
    return lg_quests.build(today, fixed, rotating, counters, set(d.claimed or []) if d else set())


def _error(db: Session, exc: ValueError, **kw) -> ValueError:
    return ValueError(lg_tr(i18n.lang(db), str(exc), **kw))


def claim_quest(db: Session, quest_id: str, goal_xp: int) -> int:
    try:
        q = lg_quests.claimable(quests(db, goal_xp), quest_id)
    except ValueError as exc:
        raise _error(db, exc)
    d = day(db)
    d.claimed = [*(d.claimed or []), quest_id]
    profile(db).gems += q["gems"]
    return q["gems"]


def open_chest(db: Session, unit: models.CourseUnit) -> int:
    done = bool(unit.lessons) and all(lesson.completed_at for lesson in unit.lessons)
    try:
        gems = rewards.badge(unit.chest_claimed, done)
    except ValueError as exc:
        raise _error(db, exc)
    unit.chest_claimed = True
    profile(db).gems += gems
    return gems


def buy(db: Session, item: str) -> dict:
    p = profile(db)
    if item != "freeze":
        raise ValueError("Ese artículo no existe")
    try:
        p.gems, p.streak_freezes = rewards.buy_freeze(p.gems, p.streak_freezes)
    except ValueError as exc:
        raise _error(db, exc, n=MAX_FREEZES)
    return {"gems": p.gems, "streak_freezes": p.streak_freezes}


def state(db: Session, goal_xp: int) -> dict:
    settle_streak(db)
    p = profile(db)
    today_row = db.get(models.LearnDay, clock.today())
    return {
        "gems": p.gems,
        "streak_freezes": p.streak_freezes,
        "streak": streak(db),
        "today_xp": today_row.xp if today_row else 0,
        "goal": goal_xp,
        "week": week(db),
        "quests": quests(db, goal_xp),
        "prices": {"freeze": PRICE_FREEZE},
        "max_freezes": MAX_FREEZES,
    }
