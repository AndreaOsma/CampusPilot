from app import generator, syllabus

from .test_learn import COURSE, subject_id, upload
from .test_learn_v2 import fake_claude  # noqa: F401 — fixture: IA "configurada"

PLAN = {
    "refusal": None,
    "summary": "Fundamentos de álgebra para ingeniería.",
    "objectives": [
        {"code": "O1", "kind": "conocimiento", "text": "Conocer el principio de inducción."},
        {"code": "O2", "kind": "habilidad", "text": "Operar con números complejos."},
        {"code": "O2", "kind": "habilidad", "text": "Duplicado: fuera."},
        {"code": "mal código!", "kind": "habilidad", "text": "Código inválido: fuera."},
    ],
    "modules": [
        {"ref": "m1", "title": "Los números", "topics": ["Inducción", "Complejos"], "objectives": ["O1", "O2", "O9"]},
        {"ref": "m2", "title": "Matrices", "topics": ["Determinantes"], "objectives": []},
    ],
    "resources": [{"title": "Los números (PDF)", "kind": "pdf"}],
    "eval_model": "ec_pf",
    "ec_pass": 5,
    "pf_min": 4,
    "groups": [{"name": "EC", "weight": 50, "min_grade": None, "role": "ec"}, {"name": "PF", "weight": 50, "min_grade": 4, "role": "pf"}],
    "activities": [
        {"name": "Cuestionario 1", "kind": "quiz", "group": "EC", "weight": 15, "window_start": "2026-09-23", "due_date": "2026-10-02", "evaluable": True},
        {"name": "Entrega R5", "kind": "pec", "group": "EC", "weight": 40, "window_start": "2026-12-10", "due_date": "2026-12-22", "evaluable": True},
    ],
    "ai_policy": "forbidden",
    "ai_policy_note": "Sin indicación, la IA no está permitida.",
}


def fake_plan(monkeypatch, payload=PLAN):
    monkeypatch.setattr(syllabus.ai, "complete_json", lambda *a, **k: (payload, 0.03))


def import_plan(client, sid):
    r = client.post(f"/api/subjects/{sid}/syllabus/import", files={"file": ("plan-docente.md", "# Plan docente\nCriterios de evaluación…", "text/markdown")})
    assert r.status_code == 202, r.text
    return client.get(f"/api/learn/jobs/{r.json()['id']}").json()


def test_parse_draft_cleans_codes():
    draft, warnings = syllabus.parse_draft(PLAN)
    plan = draft["plan"]
    assert [o["code"] for o in plan["objectives"]] == ["O1", "O2"]
    assert plan["modules"][0]["objectives"] == ["O1", "O2"]  # O9 no existe
    assert [w["level"] for w in warnings] == ["dropped"]  # el código inválido


def test_plan_import_review_and_apply(client, fake_claude, monkeypatch):
    fake_plan(monkeypatch)
    sid = subject_id(client)
    # Ya hay una actividad igual en la agenda: la revisión lo marca para no duplicarla.
    client.post("/api/activities", json={"subject_id": sid, "name": "Cuestionario 1", "kind": "quiz", "due_date": "2026-10-02"})
    job = import_plan(client, sid)
    assert job["status"] == "done", job["error"]
    assert job["mode"] == "plan" and job["plan_counts"] == {"objectives": 2, "modules": 2, "activities": 2}
    assert job["subject_state"]["existing"] == [True, False] and job["subject_state"]["has_groups"] is False

    r = client.post(f"/api/learn/jobs/{job['id']}/import", json={"use_eval": True, "activities": [1]})
    assert r.status_code == 200, r.text
    subject = next(s for s in client.get("/api/subjects").json() if s["id"] == sid)
    assert subject["eval_model"] == "ec_pf" and subject["eval_config"]["pf_min"] == 4
    assert subject["ai_policy"] == "forbidden"  # estaba sin indicar
    groups = client.get("/api/groups", params={"subject_id": sid}).json()
    assert {g["name"]: g["min_grade"] for g in groups} == {"EC": None, "PF": 4}
    acts = client.get("/api/activities", params={"subject_id": sid}).json()
    assert sorted(a["name"] for a in acts) == ["Cuestionario 1", "Entrega R5"]  # sin duplicar
    r5 = next(a for a in acts if a["name"] == "Entrega R5")
    assert r5["window_start"] == "2026-12-10" and r5["due_date"] == "2026-12-22" and r5["group_id"]

    plan = client.get(f"/api/subjects/{sid}/syllabus").json()
    assert plan["has_plan"] and [o["code"] for o in plan["objectives"]] == ["O1", "O2"]
    assert plan["modules"][0]["lessons"] == 0 and plan["source"] == "plan-docente.md"

    # Aplicarlo otra vez no duplica grupos ni actividades.
    client.post(f"/api/learn/jobs/{job['id']}/import", json={"use_eval": True, "activities": [1]})
    assert len(client.get("/api/activities", params={"subject_id": sid}).json()) == 2
    assert len(client.get("/api/groups", params={"subject_id": sid}).json()) == 2


def test_plan_never_relaxes_ai_policy(client, fake_claude, monkeypatch):
    fake_plan(monkeypatch, {**PLAN, "ai_policy": "allowed"})
    career = client.post("/api/careers", json={"name": "G"}).json()
    subj = client.post("/api/subjects", json={"career_id": career["id"], "name": "FP", "ai_policy": "forbidden"}).json()
    job = import_plan(client, subj["id"])
    client.post(f"/api/learn/jobs/{job['id']}/import", json={})
    subject = next(s for s in client.get("/api/subjects").json() if s["id"] == subj["id"])
    assert subject["ai_policy"] == "forbidden" and subject["eval_model"] == "weighted"  # sin use_eval no se toca


def test_objectives_flow_into_lessons(client, fake_claude, monkeypatch):
    fake_plan(monkeypatch)
    sid = subject_id(client)
    job = import_plan(client, sid)
    client.post(f"/api/learn/jobs/{job['id']}/import", json={})

    seen = {}
    lessons_out = {"refusal": None, "units": [{"ref": "u1", "title": "Complejos", "lessons": [{"ref": "l1", "title": "Suma", "steps": [
        {"ref": "t", "kind": "info", "prompt": "Suma", "source": "M1 3.3", "explanation": "Parte a parte.", "data": {}, "objectives": ["O2"]},
        {"ref": "q", "kind": "truefalse", "prompt": "¿$i^2=-1$?", "source": "M1 3.1", "explanation": "", "data": {"answer": True},
         "objectives": ["O2", "O7"]},
    ]}]}]}

    def fake_gen(r, instructions, schema, text, feature, timeout):
        seen["text"] = text
        return lessons_out, 0.1

    monkeypatch.setattr(generator.ai, "complete_json", fake_gen)
    r = client.post("/api/learn/generate", files={"files": ("modulo1.md", "# 3.3 Suma", "text/markdown")},
                    data={"material_kind": "manual", "subject_id": str(sid), "module_ref": "m1"})
    job = client.get(f"/api/learn/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    assert "O2 (habilidad): Operar con números complejos." in seen["text"] and "módulo «Los números»" in seen["text"]
    step = job["draft"]["units"][0]["lessons"][0]["steps"][1]
    assert step["objectives"] == ["O2"]  # O7 no está en el plan
    course = client.post(f"/api/learn/jobs/{job['id']}/import", json={}).json()

    plan = client.get(f"/api/subjects/{sid}/syllabus").json()
    m1 = next(m for m in plan["modules"] if m["ref"] == "m1")
    assert m1["lessons"] == 1
    o2 = next(o for o in plan["objectives"] if o["code"] == "O2")
    assert o2["steps"] == 1 and o2["mastery"] is None
    practice = client.get(f"/api/learn/courses/{course['id']}/practice", params={"objective": "O2"}).json()
    assert len(practice["steps"]) == 1 and practice["title"].startswith("Objetivo O2")
    exported = client.get(f"/api/learn/courses/{course['id']}/export").json()
    assert exported["units"][0]["module"] == "m1" and exported["units"][0]["lessons"][0]["steps"][1]["objectives"] == ["O2"]


def test_theory_tags_existing_lessons(client, fake_claude, monkeypatch):
    fake_plan(monkeypatch)
    sid = subject_id(client)
    client.post(f"/api/learn/jobs/{import_plan(client, sid)['id']}/import", json={})
    upload(client, COURSE)
    course_id = client.get("/api/learn/courses").json()[0]["id"]
    lesson_id = client.get(f"/api/learn/courses/{course_id}").json()["units"][0]["lessons"][1]["id"]
    monkeypatch.setattr(generator.ai, "complete_json", lambda *a, **k: ({"lessons": [
        {"lesson": f"L{lesson_id}", "objectives": ["O1", "O9"], "module": "m1",
         "cards": [{"title": "Inducción", "body": "Paso base y paso inductivo.", "source": "M1 2"}]},
    ]}, 0.01))
    r = client.post("/api/learn/generate", files={"files": ("modulo1.md", "# 2 Inducción", "text/markdown")},
                    data={"material_kind": "manual", "subject_id": str(sid), "mode": "theory"})
    job = client.get(f"/api/learn/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    client.post(f"/api/learn/jobs/{job['id']}/import", json={})
    plan = client.get(f"/api/subjects/{sid}/syllabus").json()
    assert next(o for o in plan["objectives"] if o["code"] == "O1")["steps"] == 1  # el ejercicio de la lección
    assert next(m for m in plan["modules"] if m["ref"] == "m1")["lessons"] == 2  # la unidad entera pasa al módulo
