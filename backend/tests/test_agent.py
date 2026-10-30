"""API para asistentes (ágora): solo logística."""
from datetime import timedelta

import pytest

from app import clock, models
from app.database import SessionLocal

TOKEN = "c" * 40
H = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def on(client, monkeypatch):
    monkeypatch.setenv("CAMPUS_AGENT_TOKEN", TOKEN)
    today = clock.today()
    with SessionLocal() as db:
        career = models.Career(name="Grado")
        db.add(career)
        db.flush()
        subj = models.Subject(career_id=career.id, code="RED", name="Redes", ects=6, status="enrolled")
        db.add(subj)
        db.flush()
        db.add(models.Activity(subject_id=subj.id, name="PEC1", due_date=today + timedelta(days=3), evaluable=True))
        db.add(models.Habit(title="Repasar 20 min", weekdays=[0, 1, 2, 3, 4, 5, 6], active=True))
        db.commit()
    return client


def call(c, tool, args=None):
    return c.post(f"/agent/v1/call/{tool}", json=args or {}, headers=H)


def test_closed_without_token(client, monkeypatch):
    monkeypatch.delenv("CAMPUS_AGENT_TOKEN", raising=False)
    assert client.get("/agent/v1/manifest", headers=H).status_code == 404


def test_logistics_only(on):
    names = {t["name"] for t in on.get("/agent/v1/manifest", headers=H).json()["tools"]}
    assert not any(w in n for n in names for w in ("leccion", "material", "teoria", "enunciado"))
    pend = call(on, "entregas_pendientes").json()["result"]
    assert pend[0]["actividad"] == "PEC1" and pend[0]["asignatura"] == "Redes"
    assert any(i["title"].startswith("PEC1") or "PEC1" in i["title"] for i in call(on, "agenda").json()["result"])
    pv = on.post("/agent/v1/validate/registrar_estudio", json={"minutos": 45, "asignatura": "red", "fecha": "2026-10-30"}, headers=H).json()
    assert pv["preview"] == "Apuntar 45 min de estudio el 30/10 en Redes"
    assert on.post("/agent/v1/validate/marcar_habito", json={"habito": "repasar", "fecha": "2026-10-30"}, headers=H).json()["preview"].endswith("como hecho el 30/10")
    assert call(on, "registrar_estudio", {"minutos": 45, "asignatura": "red"}).json()["result"]["asignatura"] == "Redes"
    assert call(on, "horas_de_estudio").json()["result"]["por_asignatura"] == {"Redes": 45}
    assert call(on, "marcar_habito", {"habito": "repasar"}).json()["result"]["hecho"]
    assert len(call(on, "habitos").json()["result"][0]["hechos_esta_semana"]) == 1
    pv = on.post("/agent/v1/validate/marcar_entregada", json={"actividad_id": pend[0]["id"]}, headers=H).json()
    assert pv["preview"] == "Marcar como entregada «PEC1» (Redes)"
    assert call(on, "marcar_entregada", {"actividad_id": pend[0]["id"]}).status_code == 200
    assert call(on, "entregas_pendientes").json()["result"] == []
    assert call(on, "registrar_estudio", {"minutos": 10, "asignatura": "Astrofísica"}).status_code == 404

def test_avisos(on):
    with SessionLocal() as db:
        subj = db.query(models.Subject).filter_by(code="RED").one()
        db.add(models.Activity(subject_id=subj.id, name="Test final", due_date=clock.today() + timedelta(days=1), evaluable=True))
        db.commit()
    av = call(on, "avisos").json()["result"]
    assert [a["texto"] for a in av] == ["«Test final» (Redes) se entrega en 1 día(s) ({:%d/%m})".format(clock.today() + timedelta(days=1))]


def _course(db, subj, steps):
    course = models.Course(slug=f"c-{subj.code.lower()}", subject_id=subj.id, title=subj.name)
    db.add(course)
    db.flush()
    unit = models.CourseUnit(course_id=course.id, ref="u1", title="Unidad 1")
    db.add(unit)
    db.flush()
    lesson = models.Lesson(unit_id=unit.id, ref="l1", title="Lección 1")
    db.add(lesson)
    db.flush()
    for i, (kind, prompt, data) in enumerate(steps):
        db.add(models.LessonStep(lesson_id=lesson.id, ref=f"s{i}", position=i, kind=kind, prompt=prompt, data=data,
                                 explanation="Porque sí", source="Módulo 1, autoevaluación 1"))


def test_repaso_solo_asignaturas_que_permiten_ia(on):
    with SessionLocal() as db:
        red = db.query(models.Subject).filter_by(code="RED").one()
        red.ai_policy = "allowed"
        mat = models.Subject(career_id=red.career_id, code="MAT", name="Matemáticas", ects=6, status="enrolled", ai_policy="forbidden")
        unk = models.Subject(career_id=red.career_id, code="SEG", name="Seguridad", ects=6, status="enrolled")  # unknown
        db.add_all([mat, unk])
        db.flush()
        _course(db, red, [("choice", "¿Capa de IP?", {"options": ["Enlace", "Red"], "correct": [1]}),
                          ("truefalse", "TCP es fiable", {"answer": True}),
                          ("info", "Teoría", {})])
        _course(db, mat, [("truefalse", "1+1=2", {"answer": True})])
        _course(db, unk, [("truefalse", "AES es simétrico", {"answer": True})])
        db.commit()
    res = call(on, "repaso", {"n": 10}).json()["result"]["preguntas"]
    assert {q["asignatura"] for q in res} == {"Redes"} and len(res) == 2
    ip = next(q for q in res if q["pregunta"] == "¿Capa de IP?")
    assert ip["solucion"] == "Red" and ip["opciones"] == ["Enlace", "Red"] and ip["fuente"]
    assert call(on, "repaso", {"asignatura": "Matemáticas"}).status_code == 403
    assert call(on, "repaso", {"asignatura": "Seguridad"}).status_code == 403
