"""«Hoy» como centro de mando: plan del día, riesgo, carga semanal, examen, bandeja y Aprender."""
from datetime import timedelta

from app import clock


def setup(client):
    career = client.post("/api/careers", json={"name": "Grado"}).json()
    s = client.post("/api/subjects", json={"career_id": career["id"], "name": "Señales", "status": "enrolled", "weekly_hours": 7}).json()
    return career, s


def test_plan_starts_with_the_nearest_delivery(client):
    _, s = setup(client)
    tomorrow = (clock.today() + timedelta(days=1)).isoformat()
    client.post("/api/activities", json={"subject_id": s["id"], "name": "PEC 2", "kind": "pec", "due_date": tomorrow, "estimated_hours": 3})
    d = client.get("/api/dashboard").json()
    first = d["today_plan"][0]
    assert first["kind"] == "deliver" and "PEC 2" in first["title"] and "mañana" in first["detail"]
    assert d["week_load"][0]["hours"] >= 7
    assert any(w["deliveries"] == 1 for w in d["week_load"])


def test_failed_minimum_is_at_risk(client):
    _, s = setup(client)
    g = client.post("/api/groups", json={"subject_id": s["id"], "name": "Prácticas", "weight": 100, "min_grade": 5}).json()
    client.post("/api/activities", json={"subject_id": s["id"], "group_id": g["id"], "name": "P1", "grade": 3})
    risk = client.get("/api/dashboard").json()["at_risk"]
    assert risk and risk[0]["level"] == "crit" and risk[0]["name"] == "Señales"


def test_next_exam_and_inbox_and_learn(client):
    setup(client)
    day = (clock.today() + timedelta(days=5)).isoformat()
    client.post("/api/events", json={"title": "Examen final", "kind": "exam", "date": day})
    d = client.get("/api/dashboard").json()
    assert d["next_exam"]["title"] == "Examen final"
    assert d["inbox_pending"] == {"new": 0, "proposals": 0}
    assert d["learn"]["goal"] == 30 and d["learn"]["streak"] == 0


def test_empty_dashboard_does_not_break(client):
    d = client.get("/api/dashboard").json()
    assert d["today_plan"] == [] and d["at_risk"] == [] and len(d["week_load"]) == 4 and d["next_exam"] is None


def test_texts_follow_the_language_setting(client):
    _, s = setup(client)
    tomorrow = (clock.today() + timedelta(days=1)).isoformat()
    client.post("/api/activities", json={"subject_id": s["id"], "name": "Lab 2", "due_date": tomorrow})
    settings = client.get("/api/settings").json()
    client.put("/api/settings", json={**settings, "language": "en"})
    d = client.get("/api/dashboard").json()
    assert d["today_plan"][0]["title"] == "Work on “Lab 2”" and "due tomorrow" in d["today_plan"][0]["detail"]
    quests = client.get("/api/learn/game").json()["quests"]
    assert quests[0]["title"] == "Earn 30 XP"
    assert client.get("/api/learn/generator/status").json()["kinds"]["apuntes"] == "My notes"
