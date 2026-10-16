from app import degree_plan

from .test_learn_v2 import fake_claude  # noqa: F401

PLAN = {
    "refusal": None,
    "institution": "Universidade do Porto",
    "degree": "Licenciatura em Engenharia Informática",
    "description": "Plano de estudos.",
    "credits_total": 180,
    "credit_label": "ECTS",
    "grade_max": 20,
    "pass_mark": 10,
    "term_system": "semesters",
    "year_start_month": 9,
    "requirements": {"obligatoria": 150, "optativa": 30, "inventado": 5},
    "tracks": [{"id": "Redes", "name": "Redes e Sistemas"}],
    "subjects": [
        {"code": "L.EIC001", "name": "Álgebra Linear", "credits": 6, "kind": "basica", "plan_semester": 1, "track": None},
        {"code": "L.EIC001", "name": "Álgebra Linear (repetida por el modelo)", "credits": 6, "kind": "basica", "plan_semester": 1},
        {"code": "L.EIC030", "name": "Redes Avançadas", "credits": 6, "kind": "mencion", "plan_semester": 5, "track": "redes"},
        {"code": "X", "name": "", "credits": 6, "kind": "optativa"},
        {"code": "L.EIC099", "name": "Créditos imposibles", "credits": 900, "kind": "otra"},
    ],
}


def test_build_pack_validates_and_cleans():
    pack, warnings = degree_plan.build_pack(PLAN)
    assert pack["slug"] == "universidade-do-porto-licenciatura-em-engenharia-informatica"
    assert pack["config"]["grade_max"] == 20 and pack["requirements"] == {"obligatoria": 150.0, "optativa": 30.0}
    refs = [s["ref"] for s in pack["subjects"]]
    assert refs == ["l-eic001", "l-eic001-2", "l-eic030"]  # sin nombre y con créditos imposibles: fuera
    assert pack["subjects"][2]["track"] == "redes" and len(warnings) == 2


def test_career_from_plan_end_to_end(client, fake_claude, monkeypatch):
    monkeypatch.setattr(degree_plan.ai, "complete_json", lambda *a, **k: (PLAN, 0.2))
    r = client.post("/api/packs/from-plan", files={"file": ("plano.html", "<h1>Plano de estudos</h1>", "text/html")})
    assert r.status_code == 202, r.text
    job = client.get(f"/api/learn/jobs/{r.json()['id']}").json()
    assert job["status"] == "done" and job["mode"] == "career" and job["steps"] == 3
    res = client.post(f"/api/learn/jobs/{job['id']}/import", json={}).json()
    career = next(c for c in client.get("/api/careers").json() if c["id"] == res["career_id"])
    assert career["name"] == "Licenciatura em Engenharia Informática" and career["config"]["pass_mark"] == 10 and career["ects_goal"] == 180
    subjects = [s for s in client.get("/api/subjects").json() if s["career_id"] == career["id"]]
    assert len(subjects) == 3 and all(s["status"] == "pending" for s in subjects)
