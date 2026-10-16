import copy
import json
from datetime import date, timedelta

from app import game, models
from app.database import SessionLocal

from .test_learn import COURSE, subject_id, upload
from .test_learn_v2 import fake_claude  # noqa: F401  (fixture)


def course_ids(client):
    course_id = client.get("/api/learn/courses").json()[0]["id"]
    return client.get(f"/api/learn/courses/{course_id}").json()


def test_path_is_linear_with_levels(client):
    upload(client, COURSE)
    c = course_ids(client)
    l1, l2 = c["units"][0]["lessons"]
    assert (l1["locked"], l2["locked"]) == (False, True) and l1["level"] == 0
    client.post(f"/api/learn/lessons/{l1['id']}/complete", json={"correct": 5, "total": 5})
    c = course_ids(client)
    l1, l2 = c["units"][0]["lessons"]
    assert l1["level"] == 1 and not l2["locked"]


def test_perfect_lesson_bonus_quests_and_claim(client):
    upload(client, COURSE)
    l1 = course_ids(client)["units"][0]["lessons"][0]
    r = client.post(f"/api/learn/lessons/{l1['id']}/complete", json={"correct": 4, "total": 4}).json()
    assert r["perfect"] is True and r["xp"] == 10 + game.PERFECT_BONUS_XP
    quests = {q["id"]: q for q in r["game"]["quests"]}
    assert quests["lessons"]["progress"] == 1 and not quests["lessons"]["done"]
    # La de XP: 15 de 30 → aún no; no se puede cobrar.
    assert client.post("/api/learn/quests/xp/claim").status_code == 409
    # Repetirla da 5 + 5 de bonus perfecto: 15 + 10 + 10 = 35 ≥ 30.
    client.post(f"/api/learn/lessons/{l1['id']}/complete", json={"correct": 4, "total": 4})
    client.post(f"/api/learn/lessons/{l1['id']}/complete", json={"correct": 4, "total": 4})
    st = client.get("/api/learn/game").json()
    assert {q["id"]: q for q in st["quests"]}["xp"]["done"]
    got = client.post("/api/learn/quests/xp/claim").json()
    assert got["gems"] == 10 and got["game"]["gems"] == 10
    assert client.post("/api/learn/quests/xp/claim").status_code == 409  # solo una vez


def test_chest_needs_whole_unit(client):
    upload(client, COURSE)
    unit = course_ids(client)["units"][0]
    assert client.post(f"/api/learn/units/{unit['id']}/chest").status_code == 409
    for lesson in unit["lessons"]:
        client.post(f"/api/learn/lessons/{lesson['id']}/complete", json={"correct": 1, "total": 2})
    r = client.post(f"/api/learn/units/{unit['id']}/chest").json()
    assert r["gems"] == game.CHEST_GEMS
    assert client.post(f"/api/learn/units/{unit['id']}/chest").status_code == 409


def test_shop_and_streak_freeze():
    today = date(2026, 10, 13)
    with SessionLocal() as db:
        for m in (models.LearnDay, models.LearnProfile):
            db.query(m).delete()
        p = game.profile(db)
        p.gems = 250
        assert game.buy(db, "freeze")["streak_freezes"] == 1
        assert game.buy(db, "freeze")["streak_freezes"] == 2
        try:
            game.buy(db, "freeze")
            raise AssertionError("no debería dejar comprar un tercero")
        except ValueError:
            pass
        # Estudié hace 3 días; ayer y anteayer no: los dos protectores salvan la racha.
        db.add(models.LearnDay(date=today - timedelta(days=3), xp=20))
        db.add(models.LearnDay(date=today - timedelta(days=4), xp=20))
        db.flush()
        game.settle_streak(db, today)
        assert game.profile(db).streak_freezes == 0
        assert game.streak(db, today) == 4
        db.rollback()


def test_streak_breaks_without_enough_freezes():
    today = date(2026, 10, 13)
    with SessionLocal() as db:
        for m in (models.LearnDay, models.LearnProfile):
            db.query(m).delete()
        game.profile(db).streak_freezes = 1
        db.add(models.LearnDay(date=today - timedelta(days=3), xp=20))
        db.flush()
        game.settle_streak(db, today)
        assert game.profile(db).streak_freezes == 1  # no alcanza: no se gasta
        assert game.streak(db, today) == 0
        db.rollback()


def test_match_kind(client):
    c = copy.deepcopy(COURSE)
    c["units"][0]["lessons"][0]["steps"].append(
        {"ref": "m", "kind": "match", "prompt": "Empareja", "source": "Ej. 7",
         "data": {"pairs": [["$i^2$", "$-1$"], ["$\\bar z$", "conjugado"], ["$|z|$", "módulo"]]}}
    )
    assert upload(client, c).status_code == 200
    lesson_id = course_ids(client)["units"][0]["lessons"][0]["id"]
    step = next(s for s in client.get(f"/api/learn/lessons/{lesson_id}").json()["steps"] if s["kind"] == "match")
    assert step["left"] == ["$i^2$", "$\\bar z$", "$|z|$"] and sorted(step["right"]) == sorted(["$-1$", "conjugado", "módulo"])
    ok = client.post(f"/api/learn/steps/{step['id']}/answer", json={"response": ["$-1$", "conjugado", "módulo"], "combo": 6}).json()
    assert ok["correct"]
    assert client.post(f"/api/learn/steps/{step['id']}/answer", json={"response": ["conjugado", "$-1$", "módulo"]}).json()["correct"] is False
    assert {q["id"]: q for q in client.get("/api/learn/game").json()["quests"]}.get("combo", {"progress": 5})["progress"] == 5
    bad = copy.deepcopy(c)
    bad["units"][0]["lessons"][0]["steps"][-1]["data"]["pairs"] = [["a", "b"], ["c", "d"]]
    assert upload(client, bad).status_code == 422


def _pdf(pages: list[str]) -> bytes:
    """PDF mínimo con una línea de texto por página (Helvetica), sin dependencias."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        objs.append(f"<< /Length {len(content)} >>\nstream\n{content.decode()}\nendstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {len(objs)} 0 R /Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(len(objs))
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def test_pdf_material_is_extracted_with_pages(client, fake_claude):  # noqa: F811
    pdf = _pdf(["Tema 3. La suma de complejos se hace parte a parte, como en el ejemplo 1.", "Ejemplo 2: el producto usa i al cuadrado igual a menos uno."])
    r = client.post("/api/learn/generate", files={"files": ("modulo3.pdf", pdf, "application/pdf")}, data={"material_kind": "manual", "subject_id": str(subject_id(client))})
    assert r.status_code == 202, r.text
    from app import generator

    text = generator.pdf_to_text(pdf, "x.pdf")
    assert "<!-- página 1 -->" in text and "<!-- página 2 -->" in text and "producto" in text


def test_scanned_or_fake_pdf_rejected(client, fake_claude):  # noqa: F811
    blank = _pdf(["", ""])
    r = client.post("/api/learn/generate", files={"files": ("escaneado.pdf", blank, "application/pdf")}, data={"material_kind": "manual", "subject_id": str(subject_id(client))})
    assert r.status_code == 422 and "escaneado" in r.json()["detail"]
    r = client.post("/api/learn/generate", files={"files": ("falso.pdf", b"hola", "application/pdf")}, data={"material_kind": "manual", "subject_id": str(subject_id(client))})
    assert r.status_code == 422 and "no es un PDF" in r.json()["detail"]
    r = client.post("/api/learn/generate", files={"files": ("x.docx", b"PK..", "application/octet-stream")}, data={"material_kind": "manual", "subject_id": str(subject_id(client))})
    assert r.status_code == 422


def test_personal_planned_term(client):
    r = client.post("/api/packs/uoc-teleco/install").json()
    subj = next(s for s in client.get("/api/subjects", params={"career_id": r["career_id"]}).json() if s["name"] == "Física I")
    assert client.put(f"/api/subjects/{subj['id']}", json={**subj, "planned_term": "2027S2"}).status_code == 200
    assert client.put(f"/api/subjects/{subj['id']}", json={**subj, "planned_term": "otoño"}).status_code == 422
    client.post("/api/packs/uoc-teleco/install")  # reinstalar no toca el plan personal
    again = client.get(f"/api/subjects/{subj['id']}").json()
    assert again["planned_term"] == "2027S2"
    exported = json.dumps(client.get(f"/api/careers/{r['career_id']}/export-pack").json())
    assert "2027S2" not in exported
