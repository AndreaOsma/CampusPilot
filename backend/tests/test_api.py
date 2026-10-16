import io
import json
from datetime import date, timedelta

import pytest


def install_teleco(client):
    r = client.post("/api/packs/uoc-teleco/install")
    assert r.status_code == 200, r.text
    return r.json()["career_id"]


def subject_by_name(client, career_id, name):
    rows = client.get("/api/subjects", params={"career_id": career_id}).json()
    return next(s for s in rows if s["name"] == name)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_catalog_lists_teleco(client):
    packs = client.get("/api/packs").json()
    teleco = next(p for p in packs if p["slug"] == "uoc-teleco")
    assert teleco["in_catalog"] and teleco["installed_version"] is None
    assert teleco["ects_total"] == 240
    assert teleco["terms"][0]["label"] == "2026S1"


def test_install_creates_pending_subjects_and_is_idempotent(client):
    career_id = install_teleco(client)
    subjects = client.get("/api/subjects", params={"career_id": career_id}).json()
    assert len(subjects) == 46
    assert all(s["status"] == "pending" for s in subjects)
    mates = subject_by_name(client, career_id, "Matemáticas I")
    assert mates["ai_policy"] == "forbidden" and mates["eval_model"] == "ec_pf"
    assert subject_by_name(client, career_id, "Gestión de proyectos")["kind"] == "basica"
    assert subject_by_name(client, career_id, "Física I")["offered"] == "s1"
    groups = client.get("/api/groups", params={"subject_id": mates["id"]}).json()
    assert [(g["name"], g["weight"], g["role"]) for g in groups] == [("EC", 50, "ec"), ("PF", 50, "pf")]

    # Cambios del usuario sobreviven a una reinstalación.
    client.put(f"/api/subjects/{mates['id']}", json={**mates, "status": "enrolled", "notes": "mías"})
    assert install_teleco(client) == career_id
    again = subject_by_name(client, career_id, "Matemáticas I")
    assert again["status"] == "enrolled" and again["notes"] == "mías"
    assert len(client.get("/api/subjects", params={"career_id": career_id}).json()) == 46
    assert len(client.get("/api/groups", params={"subject_id": mates["id"]}).json()) == 2


def test_apply_term_enrolls_and_adds_calendar(client):
    career_id = install_teleco(client)
    r = client.post("/api/packs/uoc-teleco/terms/2026s1/apply")
    assert r.status_code == 200, r.text
    counts = r.json()
    assert counts["subjects"] == 2 and counts["activities"] == 19 and counts["procedures"] == 2

    fp = subject_by_name(client, career_id, "Fundamentos de programación")
    assert fp["status"] == "enrolled" and fp["term_id"] == counts["term_id"]
    acts = client.get("/api/activities", params={"subject_id": fp["id"]}).json()
    pec1 = next(a for a in acts if a["name"] == "PEC 1")
    assert pec1["due_date"] == "2026-10-07" and pec1["group_id"] is not None

    # Nota y "hecho" del usuario sobreviven a reaplicar el semestre.
    client.put(f"/api/activities/{pec1['id']}", json={**pec1, "grade": 8, "done": True})
    client.post("/api/packs/uoc-teleco/terms/2026s1/apply")
    pec1 = client.get(f"/api/activities/{pec1['id']}").json()
    assert pec1["grade"] == 8 and pec1["done"] is True
    assert len(client.get("/api/activities", params={"subject_id": fp["id"]}).json()) == len(acts)

    habits = client.get("/api/habits").json()
    assert habits[0]["weekdays"] == [6]


def test_agenda_heavy_week_and_windows(client):
    install_teleco(client)
    client.post("/api/packs/uoc-teleco/terms/2026s1/apply")
    data = client.get("/api/agenda", params={"start": "2026-11-02", "end": "2026-11-15"}).json()
    titles = [i["title"] for i in data["items"]]
    assert "PR 1" in titles and any(t.startswith("Vídeo R2") for t in titles)
    # Semana del 2 de noviembre: PR 1 de FP + ventana del vídeo R2 de Mates → ▲
    assert {"week": "2026-11-02", "subjects": ["Fundamentos de programación", "Matemáticas I"]} in data["heavy_weeks"]
    assert all(i["ai_forbidden"] for i in data["items"] if i["type"] in ("activity", "window"))


def test_agenda_range_is_limited(client):
    r = client.get("/api/agenda", params={"start": "2026-01-01", "end": "2030-01-01"})
    assert r.status_code == 422


def test_ics_feed_and_token(client):
    install_teleco(client)
    client.post("/api/packs/uoc-teleco/terms/2026s1/apply")
    body = client.get("/api/calendar.ics").text
    assert body.startswith("BEGIN:VCALENDAR") and "END:VCALENDAR" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    assert client.get("/ical/test-token-123.ics").status_code == 200
    assert client.get("/ical/wrong.ics").status_code == 404


def test_evaluation_and_simulation(client):
    career_id = install_teleco(client)
    client.post("/api/packs/uoc-teleco/terms/2026s1/apply")
    fp = subject_by_name(client, career_id, "Fundamentos de programación")
    acts = client.get("/api/activities", params={"subject_id": fp["id"]}).json()
    for a in acts:
        if a["kind"] == "pec":
            client.put(f"/api/activities/{a['id']}", json={**a, "grade": 10})
    ev = client.get(f"/api/subjects/{fp['id']}/evaluation").json()
    assert ev["pending"] == 3 and ev["needed"] == 5.0  # el mínimo de la PR manda

    prs = {a["id"]: 6 for a in acts if a["kind"] == "pr"}
    sim = client.post(f"/api/subjects/{fp['id']}/simulate", json={"hypothetical": prs, "target": 5}).json()
    assert sim["final"] == pytest.approx(0.3 * 10 + 0.7 * 6) and sim["passed"] is True
    # La simulación no guarda nada.
    assert client.get(f"/api/subjects/{fp['id']}/evaluation").json()["pending"] == 3


def test_activity_group_must_belong_to_subject(client):
    career_id = install_teleco(client)
    fp = subject_by_name(client, career_id, "Fundamentos de programación")
    mates = subject_by_name(client, career_id, "Matemáticas I")
    mates_group = client.get("/api/groups", params={"subject_id": mates["id"]}).json()[0]
    r = client.post("/api/activities", json={"subject_id": fp["id"], "group_id": mates_group["id"], "name": "x"})
    assert r.status_code == 422


def test_url_schemes_are_validated(client):
    career_id = install_teleco(client)
    mates = subject_by_name(client, career_id, "Matemáticas I")
    bad = {**mates, "links": [{"label": "x", "url": "javascript:alert(1)"}]}
    assert client.put(f"/api/subjects/{mates['id']}", json=bad).status_code == 422
    ok = {**mates, "links": [{"label": "Apuntes", "url": "obsidian://open?vault=Ing_Teleco&file=x"}]}
    assert client.put(f"/api/subjects/{mates['id']}", json=ok).status_code == 200


def test_cards_import_and_review(client):
    md = (
        "# Preguntas de repaso — Números complejos\n\n> Solo preguntas.\n\n"
        "1. ¿Qué es $i$?\n2. ¿Cómo se calcula el conjugado?\n   ¿Y qué da $z \\bar z$?\n"
    )
    r = client.post("/api/cards/import", json={"markdown": md}).json()
    assert r == {"deck": "Números complejos", "found": 2, "added": 2}
    assert client.post("/api/cards/import", json={"markdown": md}).json()["added"] == 0
    due = client.get("/api/cards-due").json()
    assert len(due) == 2 and "¿Y qué da" in due[1]["question"]
    card = client.post(f"/api/cards/{due[0]['id']}/review", json={"knew": True}).json()
    assert card["box"] == 2 and card["due_on"] == (date.today() + timedelta(days=2)).isoformat()
    card = client.post(f"/api/cards/{due[0]['id']}/review", json={"knew": False}).json()
    assert card["box"] == 1 and card["lapses"] == 1
    # Crear a mano también funciona (caja 1, para hoy).
    new = client.post("/api/cards", json={"question": "¿Forma polar?"}).json()
    assert new["box"] == 1 and new["due_on"] == date.today().isoformat()


def test_study_sessions_and_stats(client):
    career_id = install_teleco(client)
    fp = subject_by_name(client, career_id, "Fundamentos de programación")
    client.put(f"/api/subjects/{fp['id']}", json={**fp, "status": "enrolled", "weekly_hours": 10})
    client.post("/api/sessions", json={"subject_id": fp["id"], "date": date.today().isoformat(), "minutes": 50, "kind": "focus"})
    stats = client.get("/api/study/stats").json()
    row = next(r for r in stats["by_subject"] if r["subject_id"] == fp["id"])
    assert row["minutes"] == 50 and row["expected_minutes"] == 10 * 60 * 4


def test_dashboard(client):
    install_teleco(client)
    client.post("/api/packs/uoc-teleco/terms/2026s1/apply")
    data = client.get("/api/dashboard").json()
    assert len(data["enrolled"]) == 2
    assert data["careers"][0]["ects_goal"] == 240


def test_career_summary_by_kind(client):
    career_id = install_teleco(client)
    fp = subject_by_name(client, career_id, "Fundamentos de programación")
    client.put(f"/api/subjects/{fp['id']}", json={**fp, "status": "passed", "final_grade": 8})
    s = client.get(f"/api/careers/{career_id}/summary").json()
    assert s["ects_done"] == 6 and s["average"] == 8
    assert s["by_kind"]["basica"]["done"] == 6 and s["requirements"]["basica"] == 84


def test_export_career_as_pack_roundtrip(client):
    career_id = install_teleco(client)
    client.post("/api/packs/uoc-teleco/terms/2026s1/apply")
    pack = client.get(f"/api/careers/{career_id}/export-pack").json()
    assert pack["format"] == "campus-pilot-pack" and len(pack["subjects"]) == 46
    dumped = json.dumps(pack)
    assert '"grade"' not in dumped and '"notes"' not in dumped
    pack["slug"] = "copia"
    r = client.post("/api/packs/upload", files={"file": ("copia.json", json.dumps(pack), "application/json")})
    assert r.status_code == 200, r.text
    assert any(p["slug"] == "copia" and not p["in_catalog"] for p in client.get("/api/packs").json())


def test_upload_rejects_invalid_pack(client):
    bad = {"format": "campus-pilot-pack", "format_version": 1, "slug": "x", "name": "x",
           "subjects": [{"ref": "a", "name": "A", "ects": 6}],
           "terms": [{"ref": "t", "label": "T", "start_date": "2026-09-01", "subjects": ["nope"]}]}
    r = client.post("/api/packs/upload", files={"file": ("x.json", json.dumps(bad), "application/json")})
    assert r.status_code == 422 and "desconocida" in r.json()["detail"]


def test_uninstall_keeps_or_deletes_career(client):
    career_id = install_teleco(client)
    assert client.delete("/api/packs/uoc-teleco").status_code == 204
    assert client.get(f"/api/careers/{career_id}").status_code == 200
    install_teleco(client)
    client.delete("/api/packs/uoc-teleco", params={"delete_career": True})
    assert client.get(f"/api/careers/{career_id}").status_code == 404


def test_backup_roundtrip(client):
    install_teleco(client)
    client.post("/api/packs/uoc-teleco/terms/2026s1/apply")
    client.post("/api/path", json={"title": "CCNA", "kind": "certification", "skills": ["Redes", "redes", "BGP"]})
    backup = client.get("/api/backup").content
    client.delete("/api/packs/uoc-teleco", params={"delete_career": True})
    r = client.post("/api/backup/restore", files={"file": ("b.json", io.BytesIO(backup), "application/json")})
    assert r.status_code == 200, r.text
    assert len(client.get("/api/subjects").json()) == 46
    item = client.get("/api/path").json()[0]
    assert item["skills"] == ["Redes", "BGP"]


def test_import_from_ios_app(client):
    career = client.post("/api/careers", json={"name": "Mi grado"}).json()
    rows = [
        {"name": "Física I", "credits": "6", "career": "x", "semester": "", "status": "Completed"},
        {"name": "Física I", "credits": "6", "career": "x", "semester": "", "status": "Completed"},
        {"name": "", "credits": "6"},
    ]
    r = client.post(
        "/api/import/ios",
        data={"career_id": str(career["id"])},
        files={"file": ("ios.json", json.dumps(rows), "application/json")},
    ).json()
    assert r == {"added": 1, "updated": 1, "skipped": 1}
    assert client.get("/api/subjects").json()[0]["status"] == "passed"


def test_settings_validation(client):
    s = client.get("/api/settings").json()
    assert s["modules"]["trayectoria"] is True
    s["notifications"]["topic"] = "mal topic!"
    assert client.put("/api/settings", json=s).status_code == 422


def test_money(client):
    install_teleco(client)
    counts = client.post("/api/packs/uoc-teleco/terms/2026s1/apply").json()
    s = client.get("/api/settings").json()
    client.put("/api/settings", json={**s, "default_price_per_credit": 20})
    est = client.get(f"/api/terms/{counts['term_id']}/tuition-estimate").json()
    assert est["total"] == 240
    client.post("/api/expenses", json={"date": "2026-09-10", "category": "tuition", "amount": 250, "term_id": counts["term_id"]})
    client.post("/api/grants", json={"name": "Beca MEC", "status": "granted", "amount": 300, "min_average": 5})
    summary = client.get("/api/money/summary").json()
    assert summary["total"] == 250 and summary["grants_total"] == 300 and summary["by_term"] == {"2026S1": 250}


def test_restore_rejects_hostile_rows_and_keeps_learn_profile(client):
    client.post("/api/careers", json={"name": "Grado"})
    from app import game
    from app.database import SessionLocal
    with SessionLocal() as db:
        game.profile(db).gems = 42
        db.commit()
    bundle = client.get("/api/backup").json()
    assert bundle["version"] == 2 and bundle["tables"]["learn_profile"][0]["gems"] == 42
    evil = json.loads(json.dumps(bundle))
    evil["tables"]["path_items"] = [{"id": 1, "kind": "course", "title": "x", "status": "planned", "url": "javascript:alert(1)", "skills": [], "notes": "", "organization": ""}]
    r = client.post("/api/backup/restore", files={"file": ("b.json", json.dumps(evil), "application/json")})
    assert r.status_code == 422 and "path_items" in r.json()["detail"]
    evil = json.loads(json.dumps(bundle))
    evil["tables"]["subjects"] = [{"id": 1, "career_id": bundle["tables"]["careers"][0]["id"], "name": "S", "status": "hackeada"}]
    assert client.post("/api/backup/restore", files={"file": ("b.json", json.dumps(evil), "application/json")}).status_code == 422
    # Nada se ha tocado y una copia buena (también v1) se restaura.
    assert [c["name"] for c in client.get("/api/careers").json()] == ["Grado"]
    v1 = json.loads(json.dumps(bundle))
    v1["version"] = 1
    assert client.post("/api/backup/restore", files={"file": ("b.json", json.dumps(v1), "application/json")}).status_code == 200
