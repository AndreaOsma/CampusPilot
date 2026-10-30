import copy
from datetime import timedelta

from app import feynman, models
from app.database import SessionLocal

from .test_learn import COURSE, subject_id, upload
from .test_learn_v2 import fake_claude  # noqa: F401


def course(title="Lección 1"):
    c = copy.deepcopy(COURSE)
    lesson = c["units"][0]["lessons"][0]
    lesson["title"] = title
    lesson["steps"][0] = {"ref": "intro", "kind": "info", "prompt": "La unidad imaginaria cumple $i^2=-1$.", "concepts": ["unidad imaginaria"]}
    lesson["steps"][1]["concepts"] = ["suma"]
    lesson["steps"][2]["concepts"] = ["unidad imaginaria"]
    return c


def session(client):
    cid = client.get("/api/learn/courses").json()[0]["id"]
    lid = client.get(f"/api/learn/courses/{cid}").json()["units"][0]["lessons"][0]["id"]
    steps = client.get(f"/api/learn/lessons/{lid}").json()["steps"]
    return cid, {s["prompt"]: s["id"] for s in steps}


def fake_ai(monkeypatch, rating="almost", seen=None):
    def fake(r, instructions, schema, text, feature, timeout):
        if seen is not None:
            seen["i"], seen["t"] = instructions, text
        return {"rating": rating, "correct": True, "clear": False, "examples": False, "summary": "Casi.",
                "gaps": [{"point": "Falta el ejemplo", "theory": "i^2=-1"}], "follow_up": "¿Cuánto es i^3?"}, 0.0

    monkeypatch.setattr(feynman.ai, "complete_json", fake)
    monkeypatch.setattr(feynman.generator, "status", lambda db: {"enabled": True, "reason": ""}, raising=False)


def test_pick_prioritises_missed_and_hides_for_evaluables(client):
    assert upload(client, course()).status_code == 200
    cid, ids = session(client)
    suma, imag = ids["¿2+2?"], ids["¿$i^2=-1$?"]
    r = client.post("/api/learn/feynman/pick", json={"step_ids": [suma, imag], "missed_ids": [imag]}).json()
    assert r["available"] and [c["concept"] for c in r["concepts"]] == ["unidad imaginaria", "suma"]  # el fallado, primero
    assert r["concepts"][0]["missed"] and r["concepts"][0]["last_rating"] is None
    assert client.post("/api/learn/feynman/pick", json={"step_ids": [], "missed_ids": []}).json()["available"] is False
    client.delete(f"/api/learn/courses/{cid}")
    assert upload(client, course("Cuestionario 2")).status_code == 200
    cid, ids = session(client)
    r = client.post("/api/learn/feynman/pick", json={"step_ids": [ids["¿2+2?"]], "missed_ids": []}).json()
    assert r == {"available": False, "reason": "evaluable", "concepts": []}


def test_check_saves_attempt_and_history(client, monkeypatch):
    upload(client, course())
    cid, ids = session(client)
    seen = {}
    fake_ai(monkeypatch, "almost", seen)
    body = {"step_id": ids["¿$i^2=-1$?"], "concept": "unidad imaginaria", "explanation": "Es un número que al cuadrado da menos uno."}
    r = client.post("/api/learn/feynman/check", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["rating"] == "almost" and out["feedback"]["gaps"][0]["point"] == "Falta el ejemplo" and out["feedback"]["follow_up"]
    assert "La unidad imaginaria cumple" in seen["t"] and "no crees ejercicios" in seen["i"] and "6b." not in seen["i"]
    hist = client.get(f"/api/learn/courses/{cid}/feynman").json()
    assert hist[0]["concept"] == "unidad imaginaria" and hist[0]["last_rating"] == "almost" and len(hist[0]["attempts"]) == 1
    pick = client.post("/api/learn/feynman/pick", json={"step_ids": [ids["¿$i^2=-1$?"]], "missed_ids": []}).json()
    assert pick["concepts"][0]["last_rating"] == "almost"
    # Validación de la entrada y concepto ajeno a la pregunta.
    assert client.post("/api/learn/feynman/check", json={**body, "explanation": "corto"}).status_code == 422
    assert client.post("/api/learn/feynman/check", json={**body, "concept": "otra cosa"}).status_code == 422
    assert client.post("/api/learn/feynman/check", json={**body, "step_id": 99999}).status_code == 404


def test_check_refuses_evaluable_material(client, monkeypatch):
    upload(client, course("PEC 1"))
    _, ids = session(client)
    fake_ai(monkeypatch)
    r = client.post("/api/learn/feynman/check", json={"step_id": ids["¿$i^2=-1$?"], "concept": "unidad imaginaria",
                                                       "explanation": "Es un número que al cuadrado da menos uno."})
    assert r.status_code == 422 and "evaluable" in r.json()["detail"]


def test_forbidden_policy_adds_rule(client, monkeypatch):
    upload(client, course())
    _, ids = session(client)
    sid = subject_id(client)
    s = next(x for x in client.get("/api/subjects").json() if x["id"] == sid)
    client.put(f"/api/subjects/{sid}", json={**s, "ai_policy": "forbidden"})
    seen = {}
    fake_ai(monkeypatch, "mastered", seen)
    client.post("/api/learn/feynman/check", json={"step_id": ids["¿$i^2=-1$?"], "concept": "unidad imaginaria",
                                                   "explanation": "Es un número que al cuadrado da menos uno."})
    assert "6b." in seen["i"]


def test_weak_concepts_return_to_review_without_touching_results(client, monkeypatch):
    upload(client, course())
    cid, ids = session(client)
    assert client.get("/api/learn/review").json()["steps"] == []
    fake_ai(monkeypatch, "review")
    client.post("/api/learn/feynman/check", json={"step_id": ids["¿$i^2=-1$?"], "concept": "unidad imaginaria",
                                                   "explanation": "Es un número que al cuadrado da menos uno."})
    assert client.get("/api/learn/review").json()["steps"] == []  # aún no toca (mañana)
    with SessionLocal() as db:
        row = db.query(models.ConceptCheck).one()
        row.created_at -= timedelta(days=2)
        db.commit()
    steps = client.get("/api/learn/review").json()["steps"]
    assert [s["prompt"] for s in steps if s["kind"] != "info"] == ["¿$i^2=-1$?"]
    with SessionLocal() as db:
        step = db.get(models.LessonStep, ids["¿$i^2=-1$?"])
        assert (step.box, step.correct, step.wrong) == (0, 0, 0)
