import copy
import random

from app.learn_game import mixed as lg_mixed

from .test_learn import COURSE, first_lesson, steps_of, subject_id, upload


def test_pick_alterna_asignaturas_y_no_repite():
    cands = [lg_mixed.Candidate(f"a{i}", "A") for i in range(20)] + [lg_mixed.Candidate(f"b{i}", "B") for i in range(3)]
    out = lg_mixed.pick(cands, 6, random.Random(1))
    assert len(out) == 6 and len({c.id for c in out}) == 6
    # Mientras queden de las dos, nunca la misma dos veces seguidas; y la pequeña no queda sepultada.
    assert [c.group for c in out] == ["A", "B", "A", "B", "A", "B"] or [c.group for c in out] == ["B", "A", "B", "A", "B", "A"]


def test_pick_da_mas_peso_a_lo_flojo():
    weak = lg_mixed.Candidate("weak", "A", correct=0, wrong=3, confident_wrong=2, due=True)
    strong = [lg_mixed.Candidate(f"s{i}", "A", correct=5) for i in range(9)]
    hits = sum(lg_mixed.pick([weak, *strong], 1, random.Random(seed))[0].id == "weak" for seed in range(400))
    assert hits > 400 / 10 * 3  # muy por encima del 10 % que tendría al azar puro
    assert lg_mixed.weight(strong[0]) == 1.0


def test_pick_tope_y_vacio():
    assert lg_mixed.pick([], 10) == []
    many = [lg_mixed.Candidate(i, i % 3) for i in range(100)]
    assert len(lg_mixed.pick(many, 1000)) == lg_mixed.MAX_N


def _course(slug, title):
    c = copy.deepcopy(COURSE)
    c["slug"], c["title"] = slug, title
    return c


def test_repaso_mixto_solo_lo_visto_y_de_varias_asignaturas(client):
    upload(client, _course("uno", "Curso uno"), subject_id(client, "Física"))
    upload(client, _course("dos", "Curso dos"), subject_id(client, "Redes"))
    # Nada visto todavía: no hay de dónde preguntar.
    assert client.get("/api/learn/mixed/groups").json() == []
    assert client.get("/api/learn/mixed").json()["steps"] == []

    courses = client.get("/api/learn/courses").json()
    for c in courses:
        detail = client.get(f"/api/learn/courses/{c['id']}").json()
        lesson_id = detail["units"][0]["lessons"][0]["id"]
        step = steps_of(client, lesson_id)["¿2+2?"]
        client.post(f"/api/learn/steps/{step['id']}/answer", json={"response": [0]})

    groups = client.get("/api/learn/mixed/groups").json()
    assert sorted(g["title"] for g in groups) == ["Física", "Redes"]
    assert all(g["count"] == 1 for g in groups)

    steps = client.get("/api/learn/mixed").json()["steps"]
    assert len(steps) == 2
    assert {s["course_title"] for s in steps} == {"Física", "Redes"}
    assert all(s["lesson_title"] == "Lección 1" and "correct" not in s for s in steps)

    only = client.get("/api/learn/mixed", params={"courses": str(groups[0]["id"])}).json()["steps"]
    assert [s["course_title"] for s in only] == [groups[0]["title"]]


def test_repaso_mixto_entra_la_leccion_terminada_entera(client):
    upload(client, COURSE)
    lesson_id = first_lesson(client)
    client.post(f"/api/learn/lessons/{lesson_id}/complete", json={"correct": 5, "total": 5})
    steps = client.get("/api/learn/mixed", params={"n": 30}).json()["steps"]
    assert len(steps) == 5  # las cinco preguntas de la lección 1 (sin la de teoría ni la lección 2)
    assert all(s["kind"] != "info" for s in steps)
