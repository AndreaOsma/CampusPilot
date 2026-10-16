import copy
import json
from datetime import date, timedelta

from app import learn
from app.database import SessionLocal
from app import models

COURSE = {
    "format": "campus-pilot-course",
    "format_version": 1,
    "slug": "demo",
    "title": "Curso de prueba",
    "units": [
        {
            "ref": "u1",
            "title": "Unidad 1",
            "lessons": [
                {
                    "ref": "l1",
                    "title": "Lección 1",
                    "steps": [
                        {"ref": "intro", "kind": "info", "prompt": "Hola"},
                        {"ref": "c", "kind": "choice", "prompt": "¿2+2?", "data": {"options": ["3", "4"], "correct": [1]}, "source": "Ej. 1"},
                        {"ref": "t", "kind": "truefalse", "prompt": "¿$i^2=-1$?", "data": {"answer": True}, "source": "Ej. 2"},
                        {"ref": "n", "kind": "numeric", "prompt": "Ángulo", "data": {"answer": -2.0944, "tolerance": 0.01, "period": 6.283185307}, "source": "Ej. 3"},
                        {"ref": "z", "kind": "complex", "prompt": "z1+z2", "data": {"re": 4, "im": 2, "tolerance": 0.001}, "source": "Ej. 4", "explanation": "Suma por partes"},
                        {"ref": "o", "kind": "order", "prompt": "Ordena", "data": {"items": ["a", "b", "c"]}, "source": "Ej. 5"},
                    ],
                },
                {"ref": "l2", "title": "Lección 2", "steps": [{"ref": "x", "kind": "truefalse", "prompt": "¿Sí?", "data": {"answer": False}, "source": "Ej. 6"}]},
            ],
        }
    ],
}


def subject_id(client, name="Matemáticas I"):
    """La asignatura de los cursos de prueba (cada curso pertenece a una)."""
    for s in client.get("/api/subjects").json():
        if s["name"] == name:
            return s["id"]
    career = client.post("/api/careers", json={"name": "Grado de prueba"}).json()
    return client.post("/api/subjects", json={"career_id": career["id"], "name": name}).json()["id"]


def upload(client, course, subject=None):
    sid = subject if subject is not None else subject_id(client)
    return client.post("/api/learn/import", files={"file": ("c.json", json.dumps(course), "application/json")}, data={"subject_id": str(sid)})


def steps_of(client, lesson_id):
    return {s["prompt"]: s for s in client.get(f"/api/learn/lessons/{lesson_id}").json()["steps"]}


def first_lesson(client):
    course_id = client.get("/api/learn/courses").json()[0]["id"]
    return client.get(f"/api/learn/courses/{course_id}").json()["units"][0]["lessons"][0]["id"]


def test_import_requires_source_on_graded_steps(client):
    bad = copy.deepcopy(COURSE)
    bad["units"][0]["lessons"][0]["steps"][1]["source"] = ""
    r = upload(client, bad)
    assert r.status_code == 422 and "source" in r.json()["detail"]


def test_import_validates_step_data(client):
    bad = copy.deepcopy(COURSE)
    bad["units"][0]["lessons"][0]["steps"][1]["data"]["correct"] = [5]
    assert upload(client, bad).status_code == 422


def test_lesson_hides_solutions(client):
    assert upload(client, COURSE).status_code == 200
    lesson = client.get(f"/api/learn/lessons/{first_lesson(client)}").json()
    dumped = json.dumps(lesson["steps"])
    assert "correct" not in dumped and '"answer"' not in dumped and "Suma por partes" not in dumped
    order = next(s for s in lesson["steps"] if s["kind"] == "order")
    assert sorted(order["items"]) == ["a", "b", "c"] and order["items"] != ["a", "b", "c"]


def test_answers_are_checked_server_side(client):
    upload(client, COURSE)
    st = steps_of(client, first_lesson(client))
    ans = lambda sid, resp: client.post(f"/api/learn/steps/{sid}/answer", json={"response": resp}).json()
    assert ans(st["¿2+2?"]["id"], [1])["correct"]
    assert not ans(st["¿2+2?"]["id"], [0])["correct"]
    assert ans(st["¿$i^2=-1$?"]["id"], True)["correct"]
    # 4π/3 es el mismo ángulo que −2π/3: con period se acepta.
    assert ans(st["Ángulo"]["id"], "4,18879")["correct"]
    assert not ans(st["Ángulo"]["id"], "2.0944")["correct"]
    res = ans(st["z1+z2"]["id"], {"re": "4", "im": "2"})
    assert res["correct"] and res["explanation"] == "Suma por partes" and res["solution"] == "4 + 2i"
    assert not ans(st["z1+z2"]["id"], {"re": "4", "im": "-2"})["correct"]
    assert ans(st["Ordena"]["id"], ["a", "b", "c"])["correct"]
    assert not ans(st["Ordena"]["id"], ["b", "a", "c"])["correct"]


def test_wrong_answers_go_to_review_and_xp_accumulates(client):
    upload(client, COURSE)
    st = steps_of(client, first_lesson(client))
    sid = st["¿2+2?"]["id"]
    assert client.post(f"/api/learn/steps/{sid}/answer", json={"response": [0]}).json()["xp"] == 0
    assert client.post(f"/api/learn/steps/{sid}/answer", json={"response": [1], "first_try": False}).json()["xp"] == learn.XP_RETRY
    stats = client.get("/api/learn/stats").json()
    assert stats["today_xp"] == learn.XP_RETRY and stats["streak"] == 1
    # El fallo entra en repaso mañana, no hoy.
    assert client.get("/api/learn/review").json()["steps"] == []
    with SessionLocal() as db:
        step = db.get(models.LessonStep, sid)
        step.due_on = date.today()
        db.commit()
    review = client.get("/api/learn/review").json()["steps"]
    assert [s["id"] for s in review] == [sid]


def test_complete_lesson_and_progress(client):
    upload(client, COURSE)
    lesson_id = first_lesson(client)
    r = client.post(f"/api/learn/lessons/{lesson_id}/complete", json={"correct": 4, "total": 5}).json()
    assert r["xp"] == learn.XP_LESSON
    course = client.get("/api/learn/courses").json()[0]
    assert course["lessons_done"] == 1 and course["lessons_total"] == 2
    assert client.get(f"/api/learn/lessons/{lesson_id}").json()["next_lesson_id"] == course["next_lesson_id"]


def test_reimport_keeps_theory_and_progress(client):
    upload(client, COURSE)
    lesson_id = first_lesson(client)
    client.put(f"/api/learn/lessons/{lesson_id}/theory", json={"theory": "Mi resumen", "theory_url": ""})
    client.post(f"/api/learn/lessons/{lesson_id}/complete", json={"correct": 1, "total": 1})
    changed = copy.deepcopy(COURSE)
    changed["units"][0]["lessons"][0]["steps"][1]["prompt"] = "¿Cuánto es 2+2?"
    assert upload(client, changed).status_code == 200
    lesson = client.get(f"/api/learn/lessons/{lesson_id}").json()
    assert lesson["theory"] == "Mi resumen" and lesson["done"] is True
    assert any(s["prompt"] == "¿Cuánto es 2+2?" for s in lesson["steps"])


def test_theory_url_scheme_validated(client):
    upload(client, COURSE)
    lesson_id = first_lesson(client)
    r = client.put(f"/api/learn/lessons/{lesson_id}/theory", json={"theory": "", "theory_url": "javascript:alert(1)"})
    assert r.status_code == 422


def test_export_has_no_theory_or_progress(client):
    upload(client, COURSE)
    lesson_id = first_lesson(client)
    client.put(f"/api/learn/lessons/{lesson_id}/theory", json={"theory": "Mi resumen privado", "theory_url": ""})
    course_id = client.get("/api/learn/courses").json()[0]["id"]
    exported = client.get(f"/api/learn/courses/{course_id}/export").json()
    assert "Mi resumen privado" not in json.dumps(exported)
    assert learn.CourseIn.model_validate(exported)


def test_streak_counts_consecutive_days():
    today = date(2026, 10, 11)
    with SessionLocal() as db:
        db.query(models.LearnDay).delete()
        for n in (1, 2, 3, 5):
            db.add(models.LearnDay(date=today - timedelta(days=n), xp=10))
        db.commit()
        assert learn.streak(db, today) == 3  # ayer, anteayer y el anterior; hoy aún no cuenta en contra
        db.add(models.LearnDay(date=today, xp=5))
        db.commit()
        assert learn.streak(db, today) == 4
        db.query(models.LearnDay).delete()
        db.commit()


def test_one_course_per_subject_sources_merge(client):
    sid = subject_id(client)
    assert upload(client, COURSE).status_code == 200
    other = copy.deepcopy(COURSE)
    other["slug"] = "otra-fuente"
    other["units"][0]["title"] = "Unidad de otra fuente"
    assert upload(client, other).status_code == 200
    courses = client.get("/api/learn/courses").json()
    assert len(courses) == 1 and courses[0]["subject_id"] == sid and courses[0]["title"] == "Matemáticas I"
    units = client.get(f"/api/learn/courses/{courses[0]['id']}").json()["units"]
    assert [u["title"] for u in units] == ["Unidad 1", "Unidad de otra fuente"]
    # Reimportar una fuente solo cambia lo suyo y conserva su sitio.
    again = copy.deepcopy(COURSE)
    again["units"][0]["title"] = "Unidad 1 (v2)"
    upload(client, again)
    units = client.get(f"/api/learn/courses/{courses[0]['id']}").json()["units"]
    assert [u["title"] for u in units] == ["Unidad 1 (v2)", "Unidad de otra fuente"]
    # La exportación conserva las fuentes: reimportarla no duplica nada.
    exported = client.get(f"/api/learn/courses/{courses[0]['id']}/export").json()
    assert exported["subject_name"] == "Matemáticas I"
    client.post("/api/learn/import", files={"file": ("c.json", json.dumps(exported), "application/json")})
    assert len(client.get(f"/api/learn/courses/{courses[0]['id']}").json()["units"]) == 2


def test_import_without_subject_is_rejected(client):
    r = client.post("/api/learn/import", files={"file": ("c.json", json.dumps(COURSE), "application/json")})
    assert r.status_code == 422 and "asignatura" in r.json()["detail"]
    assert client.get("/api/learn/courses").json() == []


def test_loose_course_is_merged_into_subject_course(client):
    sid = subject_id(client)
    upload(client, COURSE)
    with SessionLocal() as db:  # un curso antiguo sin asignatura, como los de antes
        loose = models.Course(slug="viejo", title="Viejo", description="", source_note="")
        db.add(loose)
        db.flush()
        db.add(models.CourseUnit(course_id=loose.id, ref="u9", source="viejo", title="Unidad vieja"))
        db.commit()
        loose_id = loose.id
    merged = client.put(f"/api/learn/courses/{loose_id}/subject", json={"subject_id": sid}).json()
    courses = client.get("/api/learn/courses").json()
    assert [c["id"] for c in courses] == [merged["id"]]
    units = client.get(f"/api/learn/courses/{merged['id']}").json()["units"]
    assert [u["title"] for u in units] == ["Unidad 1", "Unidad vieja"]
