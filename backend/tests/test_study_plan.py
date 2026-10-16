from datetime import date, timedelta

from app import models, study_plan
from app.database import SessionLocal

from .test_learn import COURSE, subject_id, upload

MONDAY = date(2026, 10, 12)


def test_allocate_spreads_modules_in_order():
    mods = [{"ref": "m1", "topics": ["a", "b"]}, {"ref": "m2", "topics": ["c"]}, {"ref": "m3", "topics": ["d"]}]
    weeks = study_plan.allocate(mods, 8)
    assert weeks[0] == ["m1"] and weeks[-1] == ["m3"] and sum(1 for w in weeks if "m1" in w) == 4
    flat = [r for w in weeks for r in w]
    assert flat.index("m2") > flat.index("m1") and all(w for w in weeks)
    two = study_plan.allocate(mods, 2)
    assert two[0] == ["m1"] and two[1] == ["m2", "m3"]
    assert study_plan.allocate([], 3) == [[], [], []]


def test_study_plan_this_week_behind_and_deadlines(client):
    sid = subject_id(client)
    upload(client, COURSE)  # unidad u1 con 2 lecciones
    with SessionLocal() as db:
        subject = db.get(models.Subject, sid)
        subject.syllabus = {"objectives": [{"code": "O1", "kind": "habilidad", "text": "Sumar"}],
                            "modules": [{"ref": "m1", "title": "Los números", "topics": ["x"], "objectives": ["O1"]},
                                        {"ref": "m2", "title": "Matrices", "topics": ["y"], "objectives": []},
                                        {"ref": "m3", "title": "Sistemas", "topics": ["z"], "objectives": []}]}
        course = db.query(models.Course).filter_by(subject_id=sid).first()
        course.units[0].module_ref = "m1"
        db.add(models.Term(career_id=subject.career_id, label="S1", start_date=MONDAY - timedelta(weeks=2)))
        db.flush()
        subject.term_id = db.query(models.Term).order_by(models.Term.id.desc()).first().id
        db.add(models.Activity(subject_id=sid, name="Entrega final", kind="pec", due_date=MONDAY + timedelta(weeks=3, days=2)))
        db.add(models.Activity(subject_id=sid, name="Cuestionario", kind="quiz", due_date=MONDAY + timedelta(days=4)))
        db.commit()
        out = study_plan.build(db, db.get(models.Subject, sid), today=MONDAY + timedelta(days=1))
    assert len(out["weeks"]) == 6 and out["current_week"] == 2
    assert [m["ref"] for m in out["this_week"]] == ["m2"]
    assert [b["ref"] for b in out["behind"]] == ["m1"] and out["behind"][0]["next_lesson_id"]
    assert [d["name"] for d in out["deadlines"]] == ["Cuestionario"] and out["deadlines"][0]["days"] == 3
    r = client.get(f"/api/subjects/{sid}/study-plan")
    assert r.status_code == 200 and r.json()["has_plan"]
