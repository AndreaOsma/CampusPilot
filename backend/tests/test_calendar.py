import pytest

from app import calendar_feeds, clock

from .test_learn import subject_id

ICS = """BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//Moodle//EN\r
BEGIN:VEVENT\r
UID:1@moodle\r
SUMMARY:Cuestionario 3 (75.557) cierra\r
DTSTART:{d1}T215900Z\r
DTEND:{d1}T215900Z\r
CATEGORIES:75.557 Álgebra\r
URL:https://campus.example/mod/quiz/view.php?id=3\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:2@moodle\r
SUMMARY:Examen final de Matemáticas I\r
DTSTART;VALUE=DATE:{d2}\r
DTEND;VALUE=DATE:{d2b}\r
DESCRIPTION:Prueba con supervisión\\, en línea\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:3@moodle\r
SUMMARY:Algo de otra\r
 asignatura\r
DTSTART;TZID=Europe/Madrid:{d1}T100000\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:viejo@moodle\r
SUMMARY:Hace mucho\r
DTSTART;VALUE=DATE:20200101\r
END:VEVENT\r
END:VCALENDAR\r
"""


def ics(days1=5, days2=40):
    t = clock.today()
    f = lambda d: (t + __import__("datetime").timedelta(days=d)).strftime("%Y%m%d")
    return ICS.format(d1=f(days1), d2=f(days2), d2b=f(days2 + 1))


def test_parse_ics():
    items = calendar_feeds.parse(ics())
    assert [i.uid for i in items] == ["1@moodle", "2@moodle", "3@moodle", "viejo@moodle"]
    quiz, exam, other = items[0], items[1], items[2]
    assert quiz.start_time in ("22:59", "23:59") and quiz.categories == "75.557 Álgebra"  # UTC → hora local
    assert exam.start_time is None and exam.end is None and exam.description == "Prueba con supervisión, en línea"
    assert other.summary == "Algo de otraasignatura" and other.start_time == "10:00"  # línea plegada


@pytest.fixture()
def fake_fetch(monkeypatch):
    box = {"text": ics()}
    monkeypatch.setattr(calendar_feeds, "fetch", lambda url: box["text"])
    return box


def test_feed_events_and_resync(client, fake_fetch):
    sid = subject_id(client)  # «Matemáticas I»
    client.put(f"/api/subjects/{sid}", json={**next(s for s in client.get("/api/subjects").json() if s["id"] == sid), "code": "75.557", "status": "enrolled"})
    r = client.post("/api/calendar-feeds", json={"url": "webcal://campus.example/calendar/export.php?token=secreto"})
    assert r.status_code == 201, r.text
    feed = r.json()
    assert feed["counts"] == {"new": 3, "updated": 0, "removed": 0, "skipped": 0}
    assert "secreto" not in str(client.get("/api/calendar-feeds").json())  # el token no sale por la API
    events = [e for e in client.get("/api/events").json() if e.get("title") in ("Cuestionario 3 (75.557) cierra", "Examen final de Matemáticas I", "Algo de otraasignatura")]
    by = {e["title"]: e for e in events}
    assert by["Cuestionario 3 (75.557) cierra"]["subject_id"] == sid  # por código
    assert by["Examen final de Matemáticas I"]["subject_id"] == sid and by["Examen final de Matemáticas I"]["kind"] == "exam"  # por nombre
    assert by["Algo de otraasignatura"]["subject_id"] is None

    # Marco una como hecha; al resincronizar se respeta, y lo que desaparece se borra.
    ev = by["Examen final de Matemáticas I"]
    client.put(f"/api/events/{ev['id']}", json={**ev, "done": True})
    fake_fetch["text"] = ics().replace("UID:3@moodle", "UID:3b@moodle")
    counts = client.post(f"/api/calendar-feeds/{feed['id']}/sync").json()["counts"]
    assert counts["removed"] == 1 and counts["new"] == 1 and counts["updated"] == 2
    assert next(e for e in client.get("/api/events").json() if e["id"] == ev["id"])["done"] is True

    client.delete(f"/api/calendar-feeds/{feed['id']}")
    assert not [e for e in client.get("/api/events").json() if e["title"].startswith(("Cuestionario 3", "Examen final de Mat"))]


def test_feed_as_activities(client, fake_fetch):
    sid = subject_id(client)
    r = client.post("/api/calendar-feeds", json={"url": "https://campus.example/x.ics", "mode": "activities", "subject_id": sid})
    assert r.status_code == 201, r.text
    acts = client.get("/api/activities", params={"subject_id": sid}).json()
    kinds = {a["name"]: a["kind"] for a in acts}
    assert kinds["Cuestionario 3 (75.557) cierra"] == "quiz" and kinds["Examen final de Matemáticas I"] == "exam"


def test_feed_rejects_private_and_bad_urls(client, monkeypatch):
    monkeypatch.delenv("CAMPUS_ALLOW_PRIVATE_FEEDS", raising=False)
    for url in ("http://127.0.0.1/cal.ics", "http://localhost:4646/v1/jobs", "http://10.0.0.5/x", "file:///etc/passwd", "ftp://x/y"):
        r = client.post("/api/calendar-feeds", json={"url": url})
        assert r.status_code == 422, url
    assert client.get("/api/calendar-feeds").json() == []  # lo que falla al guardarlo no se queda


def test_fetch_checks_every_redirect(monkeypatch):
    monkeypatch.delenv("CAMPUS_ALLOW_PRIVATE_FEEDS", raising=False)
    calls = []

    def fake_check(url):
        calls.append(url)
        if "169.254" in url:
            raise ValueError("privada")

    class Stream:
        def get_extra_info(self, key):
            return ("93.184.215.14", 443) if key == "server_addr" else None

    class Resp:
        def __init__(self, status, headers=None, body=b""):
            self.status_code, self.headers, self.body = status, headers or {}, body
            self.extensions = {"network_stream": Stream()}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_bytes(self):
            yield self.body

    class Client:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            return Resp(302, {"location": "http://169.254.169.254/latest/meta-data"})

    monkeypatch.setattr(calendar_feeds, "_check_host", fake_check)
    monkeypatch.setattr(calendar_feeds.httpx, "Client", Client)
    with pytest.raises(ValueError):
        calendar_feeds.fetch("https://campus.example/cal.ics")
    assert calls == ["https://campus.example/cal.ics", "http://169.254.169.254/latest/meta-data"]



def test_fetch_rejects_rebinding_to_private_ip(monkeypatch):
    """El nombre resolvía a una IP pública al comprobarlo, pero la conexión acaba en una privada."""
    monkeypatch.delenv("CAMPUS_ALLOW_PRIVATE_FEEDS", raising=False)
    monkeypatch.setattr(calendar_feeds, "_check_host", lambda url: None)

    class Stream:
        def get_extra_info(self, key):
            return ("10.0.0.7", 443) if key == "server_addr" else None

    class Resp:
        status_code, headers = 200, {}
        extensions = {"network_stream": Stream()}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_bytes(self):
            yield b"BEGIN:VCALENDAR\nEND:VCALENDAR"

    class Client:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            return Resp()

    monkeypatch.setattr(calendar_feeds.httpx, "Client", Client)
    with pytest.raises(ValueError, match="privada"):
        calendar_feeds.fetch("https://rebind.example/cal.ics")
