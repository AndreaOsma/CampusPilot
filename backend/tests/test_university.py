"""Otras universidades: escala de notas, aprobado, créditos, calendario y módulos con sus reglas."""
import json
from pathlib import Path

import pytest

from app import generator, packs
from app.grades import ActivityData, EvalData, GroupData, evaluate

PACKS_DIR = Path(__file__).resolve().parents[2] / "packs"


def test_scale_20_with_pass_10():
    # Portugal/Francia: 0–20, aprobado 10. Una actividad de 14/20 y otra pendiente al 50 %.
    data = EvalData(groups=[GroupData(1, "Todo", 100)], activities=[ActivityData(1, 1, grade=14, max_grade=20), ActivityData(2, 1)],
                    scale=20, pass_grade=10)
    r = evaluate(data)
    assert r.current == pytest.approx(14) and r.needed == pytest.approx(6)
    done = evaluate(EvalData(groups=[GroupData(1, "Todo", 100)], activities=[ActivityData(1, 1, grade=9.5, max_grade=20)], scale=20, pass_grade=10))
    assert done.final == pytest.approx(9.5) and done.passed is False


def test_scale_100_activity_on_its_own_scale():
    # Una actividad sobre 10 en una carrera 0–100: se normaliza a la escala de la carrera.
    data = EvalData(groups=[GroupData(1, "Todo", 100)], activities=[ActivityData(1, 1, grade=7, max_grade=10)], scale=100, pass_grade=60)
    r = evaluate(data)
    assert r.final == pytest.approx(70) and r.passed is True


def test_career_config_scale_is_enforced(client):
    career = client.post("/api/careers", json={"name": "Licenciatura", "config": {"grade_max": 20, "pass_mark": 10, "credit_label": "créditos"}}).json()
    assert career["config"]["grade_max"] == 20 and career["config"]["term_system"] == "semesters"
    s = client.post("/api/subjects", json={"career_id": career["id"], "name": "Álgebra", "final_grade": 18,
                                           "eval_config": {"ec_pass": 10, "pf_min": 8, "no_show_grade": 6}})
    assert s.status_code == 201, s.text
    bad = client.post("/api/subjects", json={"career_id": career["id"], "name": "X", "final_grade": 25})
    assert bad.status_code == 422 and "20" in bad.json()["detail"]
    ev = client.get(f"/api/subjects/{s.json()['id']}/evaluation").json()
    assert ev["scale"] == 20 and ev["pass_mark"] == 10
    assert client.get(f"/api/subjects/{s.json()['id']}/evaluation", params={"target": 21}).status_code == 422
    assert client.post("/api/careers", json={"name": "Y", "config": {"grade_max": 10, "pass_mark": 11}}).status_code == 422


def test_default_config_and_requirements_validation(client):
    c = client.post("/api/careers", json={"name": "Grado"}).json()
    assert c["config"]["grade_max"] == 10 and c["config"]["pass_mark"] == 5 and c["config"]["credit_label"] == "ECTS"
    assert client.post("/api/careers", json={"name": "Z", "requirements": {"inventado": 10}}).status_code == 422


def test_planned_term_systems(client):
    c = client.post("/api/careers", json={"name": "Trimestres", "config": {"term_system": "trimesters"}}).json()
    ok = client.post("/api/subjects", json={"career_id": c["id"], "name": "A", "planned_term": "2026T2", "offered": "t2"})
    assert ok.status_code == 201, ok.text
    assert client.post("/api/subjects", json={"career_id": c["id"], "name": "B", "planned_term": "2026S3"}).status_code == 422


def test_uoc_pack_declares_its_rules(client):
    career_id = client.post("/api/packs/uoc-teleco/install").json()["career_id"]
    cfg = client.get(f"/api/careers/{career_id}").json()["config"]
    assert cfg["labels"]["activity_kinds"]["pec"] == "PEC" and cfg["labels"]["ec"] == "EC"
    exported = client.get(f"/api/careers/{career_id}/export-pack").json()
    assert exported["config"]["grade_max"] == 10


def test_pack_validate_and_schema(client):
    schema = client.get("/api/packs/schema").json()
    assert "config" in schema["properties"]
    raw = json.loads((PACKS_DIR / "uoc-teleco.json").read_text())
    ok = client.post("/api/packs/validate", files={"file": ("p.json", json.dumps(raw), "application/json")}).json()
    assert ok["ok"] is True and ok["summary"]["slug"] == "uoc-teleco"
    raw["subjects"][0]["groups"] = [{"ref": "g", "name": "G", "weight": 100, "min_grade": 15}]
    bad = client.post("/api/packs/validate", files={"file": ("p.json", json.dumps(raw), "application/json")}).json()
    assert bad["ok"] is False and "máxima" in bad["errors"][0]


def test_published_schema_is_up_to_date():
    published = json.loads((PACKS_DIR / "schema" / "pack.schema.json").read_text())
    assert published == json.loads(json.dumps(packs.Pack.model_json_schema())), "Regenera packs/schema/pack.schema.json (ver README)"


@pytest.mark.parametrize("name", ["Assignment 2.pdf", "midterm-solutions.md", "problem_set_3.txt", "Final_Exam_2025.pdf"])
def test_english_evaluable_names_are_blocked(name):
    with pytest.raises(ValueError):
        generator.check_material(name, "Chapter 1", "manual", None)


def test_english_evaluable_text_is_blocked():
    with pytest.raises(ValueError):
        generator.check_material("notes.md", "This assignment is graded. Submission deadline: Oct 14", "manual", None)


def test_career_letter_scale(client):
    letters = [{"label": "C+", "min": 5, "value": 6}, {"label": "A", "min": 9, "value": 9.5}, {"label": "B", "min": 7, "value": 8},
               {"label": "C-", "min": 3, "value": 4}, {"label": "D", "min": 0, "value": 1.5}]
    career = client.post("/api/careers", json={"name": "UOC", "config": {"letters": letters}}).json()
    assert [x["label"] for x in career["config"]["letters"]] == ["A", "B", "C+", "C-", "D"]  # de mayor a menor
    bad = [{"label": "A", "min": 9, "value": 9}, {"label": "A", "min": 0, "value": 1}]
    assert client.post("/api/careers", json={"name": "X", "config": {"letters": bad}}).status_code == 422
    assert client.post("/api/careers", json={"name": "X", "config": {"letters": [{"label": "A", "min": 5, "value": 6}]}}).status_code == 422
    assert client.post("/api/careers", json={"name": "X", "config": {"letters": [{"label": "A", "min": 0, "value": 12}]}}).status_code == 422
