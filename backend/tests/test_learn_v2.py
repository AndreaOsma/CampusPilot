import copy
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

import pytest

from app import config, generator, learn, safe_math

from .test_learn import COURSE, first_lesson, subject_id, upload

PARAM_STEP = {
    "ref": "p",
    "kind": "param",
    "prompt": "Calcula $({z1})\\cdot({z2})$",
    "data": {
        "vars": {"a": {"min": -4, "max": 4}, "b": {"min": 1, "max": 4}, "c": {"min": -4, "max": 4}, "d": {"min": 1, "max": 4}},
        "show": {"z1": {"cx": ["a", "b"]}, "z2": {"cx": ["c", "d"]}},
        "answer": {"kind": "complex", "re": "a*c-b*d", "im": "a*d+b*c", "tolerance": 0.001},
    },
    "explanation": "Sale {result}.",
    "source": "Ej. 12",
    "concepts": ["Producto"],
}


def course_v2():
    c = copy.deepcopy(COURSE)
    steps = c["units"][0]["lessons"][0]["steps"]
    steps[1]["data"]["option_feedback"] = ["3 es 2+1, no 2+2", ""]
    steps[1]["hints"] = ["Cuenta con los dedos"]
    steps[1]["concepts"] = ["suma"]
    steps[1]["worked"] = "Ejemplo: 1+1=2"
    steps.append(copy.deepcopy(PARAM_STEP))
    return c


def test_safe_math_rejects_code():
    assert safe_math.evaluate("a*c-b*d", {"a": 1, "b": 2, "c": 3, "d": 4}) == -5
    assert abs(safe_math.evaluate("atan2(-5,-2) + 2*pi") - 4.332) < 1e-3
    for bad in ("__import__('os')", "a.__class__", "[1,2]", "9**9**9", "open('x')", "lambda: 1"):
        with pytest.raises(safe_math.MathError):
            safe_math.evaluate(bad, {"a": 1})


def test_param_validation_requires_some_variable(client):
    bad = course_v2()
    bad["units"][0]["lessons"][0]["steps"][-1]["prompt"] = "Calcula algo fijo"
    r = upload(client, bad)
    assert r.status_code == 422 and "variable" in r.json()["detail"]


def test_param_latex_braces_are_left_alone():
    texts = {"z1": "3 - 2i"}
    assert learn.render("$\\frac{z_1}{z_2}$ con $z_1={z1}$", texts) == "$\\frac{z_1}{z_2}$ con $z_1=3 - 2i$"


def test_param_instance_is_signed_and_checked(client):
    assert upload(client, course_v2()).status_code == 200
    lesson = client.get(f"/api/learn/lessons/{first_lesson(client)}").json()
    p = next(s for s in lesson["steps"] if s["kind"] == "param")
    assert "{z1}" not in p["prompt"] and p["answer_kind"] == "complex" and p["token"]
    # Reconstruimos la solución con los mismos números (el token está firmado, no cifrado).
    import base64

    values = json.loads(base64.urlsafe_b64decode(p["token"].rsplit(".", 1)[0]))["v"]
    re_ = values["a"] * values["c"] - values["b"] * values["d"]
    im_ = values["a"] * values["d"] + values["b"] * values["c"]
    ok = client.post(f"/api/learn/steps/{p['id']}/answer", json={"response": {"re": re_, "im": im_}, "token": p["token"]}).json()
    assert ok["correct"] and ok["explanation"].startswith("Sale ")
    # Manipular los números invalida la firma.
    tampered = base64.urlsafe_b64encode(json.dumps({"s": p["id"], "v": {**values, "a": values["a"] + 1}}).encode()).decode()
    r = client.post(f"/api/learn/steps/{p['id']}/answer", json={"response": {"re": 0, "im": 0}, "token": tampered + "." + p["token"].rsplit(".", 1)[1]})
    assert r.status_code == 422


def test_hints_feedback_confidence_and_worked(client):
    upload(client, course_v2())
    lesson_id = first_lesson(client)
    lesson = client.get(f"/api/learn/lessons/{lesson_id}").json()
    step = next(s for s in lesson["steps"] if s["prompt"] == "¿2+2?")
    assert step["hints"] == ["Cuenta con los dedos"] and step["worked"] == "Ejemplo: 1+1=2"
    wrong = client.post(f"/api/learn/steps/{step['id']}/answer", json={"response": [0], "confidence": "high"}).json()
    assert wrong["option_feedback"] == ["3 es 2+1, no 2+2"] and wrong["confident_wrong"] is True
    hinted = client.post(f"/api/learn/steps/{step['id']}/answer", json={"response": [1], "used_hint": True}).json()
    assert hinted["xp"] == learn.XP_RETRY
    assert client.get("/api/learn/stats").json()["confident_wrong"] == 1
    # El ejemplo resuelto se retira tras la primera vez.
    client.post(f"/api/learn/lessons/{lesson_id}/complete", json={"correct": 1, "total": 1})
    again = client.get(f"/api/learn/lessons/{lesson_id}").json()
    assert "worked" not in next(s for s in again["steps"] if s["prompt"] == "¿2+2?")


def test_concepts_practice_and_exam(client):
    upload(client, course_v2())
    course_id = client.get("/api/learn/courses").json()[0]["id"]
    lesson = client.get(f"/api/learn/lessons/{first_lesson(client)}").json()
    step = next(s for s in lesson["steps"] if s["prompt"] == "¿2+2?")
    client.post(f"/api/learn/steps/{step['id']}/answer", json={"response": [0]})
    concepts = client.get(f"/api/learn/courses/{course_id}/concepts").json()
    assert concepts[0]["concept"] == "suma" and concepts[0]["mastery"] == 0
    assert {c["concept"] for c in concepts} == {"suma", "producto"}
    practice = client.get(f"/api/learn/courses/{course_id}/practice", params={"concept": "suma"}).json()
    assert [s["id"] for s in practice["steps"]] == [step["id"]]
    exam = client.get(f"/api/learn/courses/{course_id}/exam", params={"n": 5}).json()
    assert len(exam["steps"]) == 5 and all(s["kind"] != "info" for s in exam["steps"])


# ---------- Generador ----------

FAKE_OUTPUT = {
    "refusal": None,
    "units": [
        {
            "ref": "u1",
            "title": "Complejos",
            "lessons": [
                {
                    "ref": "l1",
                    "title": "Suma",
                    "steps": [
                        {"ref": "ok", "kind": "complex", "prompt": "$(3+4i)+(1-2i)$", "source": "3.3.1, ejemplo", "explanation": "4+2i",
                         "data": {"re": 4, "im": 2, "tolerance": 0.001, "verify_re": "3+1", "verify_im": "4-2"}, "concepts": ["suma"]},
                        {"ref": "mal", "kind": "numeric", "prompt": "$2+2$", "source": "3.3.1", "explanation": "",
                         "data": {"answer": 5, "tolerance": 0, "verify": "2+2"}},
                        {"ref": "sin-fuente", "kind": "truefalse", "prompt": "¿Sí?", "source": "", "explanation": "", "data": {"answer": True}},
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture()
def fake_claude(monkeypatch):
    tmp = Path(tempfile.mkdtemp(prefix="fake-claude-"))
    script = tmp / "claude"
    out = tmp / "out.json"
    out.write_text(json.dumps({"type": "result", "is_error": False, "structured_output": FAKE_OUTPUT, "total_cost_usd": 0.12}))
    script.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stdin.read()\nargs=sys.argv\nassert '--tools' in args and args[args.index('--tools')+1] == ''\n"
        f"print(open({str(out)!r}).read())\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(config, "CLAUDE_BIN", str(script))
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "test-token")
    return script


def test_generator_disabled_without_credentials(client, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert client.get("/api/learn/generator/status").json()["enabled"] is False
    r = client.post("/api/learn/generate", files={"files": ("m.md", "# Tema", "text/markdown")}, data={"material_kind": "manual", "subject_id": str(subject_id(client))})
    assert r.status_code == 503


def test_generator_blocks_evaluable_material(client, fake_claude):
    md = ("pec2-enunciado.md", "Ejercicio 1", "text/markdown")
    r = client.post("/api/learn/generate", files={"files": md}, data={"material_kind": "manual", "subject_id": str(subject_id(client))})
    assert r.status_code == 422 and "evaluable" in r.json()["detail"]
    text = ("modulo.md", "# Enunciado de la actividad\nFecha límite de entrega: 14 oct", "text/markdown")
    assert client.post("/api/learn/generate", files={"files": text}, data={"material_kind": "manual", "subject_id": str(subject_id(client))}).status_code == 422


def test_generator_forbidden_subject_only_safe_kinds(client, fake_claude):
    career = client.post("/api/careers", json={"name": "G"}).json()
    subj = client.post("/api/subjects", json={"career_id": career["id"], "name": "FP", "ai_policy": "forbidden"}).json()
    r = client.post("/api/learn/generate", files={"files": ("x.md", "# Tema", "text/markdown")},
                    data={"material_kind": "otro", "subject_id": str(subj["id"])})
    assert r.status_code == 422 and "prohíbe" in r.json()["detail"]


def test_generator_end_to_end(client, fake_claude):
    r = client.post("/api/learn/generate", files={"files": ("modulo1.md", "# 3.3.1 Suma\nEjemplo...", "text/markdown")},
                    data={"material_kind": "manual", "title": "Complejos", "subject_id": str(subject_id(client))})
    assert r.status_code == 202, r.text
    job = client.get(f"/api/learn/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    steps = job["draft"]["units"][0]["lessons"][0]["steps"]
    assert [s["ref"] for s in steps] == ["ok", "mal"]  # sin fuente → descartado
    assert "flag" in steps[1] and job["review"] == 1 and job["dropped"] == 1 and job["cost_usd"] == 0.12
    imported = client.post(f"/api/learn/jobs/{job['id']}/import", json={"exclude": ["u1/l1/mal"]}).json()
    assert imported["lessons_total"] == 1
    lesson = client.get(f"/api/learn/courses/{imported['id']}").json()["units"][0]["lessons"][0]
    assert lesson["steps"] == 1
    # Añadir el mismo borrador a un curso existente no duplica unidades.
    again = client.post(f"/api/learn/jobs/{job['id']}/import", json={}).json()
    assert again["lessons_total"] == 1


def test_clean_draft_flags_wrong_angle_with_period():
    payload = {"units": [{"ref": "u", "title": "U", "lessons": [{"ref": "l", "title": "L", "steps": [
        {"ref": "a", "kind": "numeric", "prompt": "arg", "source": "s", "explanation": "",
         "data": {"answer": -2.0944, "tolerance": 0.01, "period": 6.283185307, "verify": "4*pi/3"}},
    ]}]}]}
    draft, warnings = generator.clean_draft(payload)
    assert warnings == [] and "flag" not in draft["units"][0]["lessons"][0]["steps"][0]


# ---------- Teoría antes de las preguntas ----------

def test_clean_draft_puts_theory_first_and_needs_source():
    payload = {"units": [{"ref": "u", "title": "U", "lessons": [{"ref": "l", "title": "L", "steps": [
        {"ref": "q", "kind": "truefalse", "prompt": "¿Sí?", "source": "1.1", "explanation": "", "data": {"answer": True}},
        {"ref": "t", "kind": "info", "prompt": "Qué es", "source": "1.1", "explanation": "Así.", "data": {}},
        {"ref": "t2", "kind": "info", "prompt": "Sin fuente", "source": "", "explanation": "x", "data": {}},
    ]}]}]}
    draft, warnings = generator.clean_draft(payload)
    assert [s["ref"] for s in draft["units"][0]["lessons"][0]["steps"]] == ["t", "q"]
    assert [w["step"] for w in warnings] == ["t2"] and warnings[0]["level"] == "dropped"


def test_theory_for_existing_lessons(client, fake_claude, monkeypatch):
    upload(client, COURSE)
    course_id = client.get("/api/learn/courses").json()[0]["id"]
    lesson_id = client.get(f"/api/learn/courses/{course_id}").json()["units"][0]["lessons"][1]["id"]  # sin teoría
    seen = {}

    def fake_complete(r, instructions, schema, text, feature, timeout):
        seen["text"] = text
        return {"refusal": None, "lessons": [
            {"lesson": f"L{lesson_id}", "cards": [
                {"title": "La suma", "body": "- Se juntan cantidades.", "source": "Módulo 1, 2.1"},
                {"title": "Sin fuente", "body": "x", "source": ""},
            ]},
            {"lesson": "L99999", "cards": [{"title": "Otra", "body": "y", "source": "z"}]},  # no existe → se ignora
        ]}, 0.05

    monkeypatch.setattr(generator.ai, "complete_json", fake_complete)
    r = client.post("/api/learn/generate", files={"files": ("modulo1.md", "# 2.1 Suma", "text/markdown")},
                    data={"material_kind": "manual", "subject_id": str(subject_id(client)), "mode": "theory"})
    assert r.status_code == 202, r.text
    job = client.get(f"/api/learn/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    assert job["mode"] == "theory" and job["steps"] == 1 and job["dropped"] == 1
    assert f"[L{lesson_id}]" in seen["text"] and "¿2+2?" in seen["text"] and "Hola" not in seen["text"]

    before = client.get(f"/api/learn/lessons/{lesson_id}").json()["steps"]
    client.post(f"/api/learn/jobs/{job['id']}/import", json={})
    steps = client.get(f"/api/learn/lessons/{lesson_id}").json()["steps"]
    assert steps[0]["kind"] == "info" and steps[0]["prompt"] == "La suma" and steps[0]["explanation"].startswith("- Se juntan")
    assert [s["id"] for s in steps[1:]] == [s["id"] for s in before]  # las preguntas, intactas y detrás

    # Volver a añadirla sustituye la teoría en vez de duplicarla.
    client.post(f"/api/learn/jobs/{job['id']}/import", json={})
    assert sum(s["kind"] == "info" for s in client.get(f"/api/learn/lessons/{lesson_id}").json()["steps"]) == 1

    # Reimportar el curso original (sin teoría propia) no se la lleva por delante.
    upload(client, COURSE)
    steps = client.get(f"/api/learn/lessons/{lesson_id}").json()["steps"]
    assert steps[0]["prompt"] == "La suma"


def test_theory_needs_existing_lessons(client, fake_claude):
    career = client.post("/api/careers", json={"name": "G"}).json()
    subj = client.post("/api/subjects", json={"career_id": career["id"], "name": "Vacía"}).json()
    r = client.post("/api/learn/generate", files={"files": ("m.md", "# Tema", "text/markdown")},
                    data={"material_kind": "manual", "subject_id": str(subj["id"]), "mode": "theory"})
    assert r.status_code == 422 and "no tiene lecciones" in r.json()["detail"]


# ---------- Figuras de la teoría (SVG saneado) ----------

from app import svg_safe  # noqa: E402

GOOD_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 240" onload="alert(1)">'
            '<defs><marker id="flecha" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z"/></marker></defs>'
            '<script>alert(1)</script><foreignObject><div>x</div></foreignObject>'
            '<a href="javascript:alert(1)"><circle cx="1" cy="1" r="1"/></a><image href="https://evil.example/x.png"/>'
            '<line x1="20" y1="200" x2="200" y2="40" stroke="#2563eb" marker-end="url(#flecha)" style="fill:url(https://evil.example)"/>'
            '<text x="210" y="40" font-size="14" fill="url(https://evil.example)">z = 3 + 4i</text></svg>')


def test_svg_sanitizer_keeps_shapes_and_strips_the_rest():
    out = svg_safe.sanitize(GOOD_SVG)
    for bad in ("script", "onload", "foreignObject", "href", "evil", "style", "<a", "image"):
        assert bad not in out, bad
    assert 'marker-end="url(#flecha)"' in out and "z = 3 + 4i" in out and 'viewBox="0 0 360 240"' in out
    assert svg_safe.sanitize(out) == out  # idempotente: reimportar no lo cambia


def test_svg_sanitizer_rejects_unusable():
    for bad in ("<div/>", "<svg viewBox='0 0 1 1'><script/></svg>", "<svg><circle r='1'/></svg>", "no xml",
                '<!DOCTYPE svg [<!ENTITY a "b">]><svg viewBox="0 0 1 1"><text>&a;</text></svg>', "<svg viewBox='0 0 1 1'>" + "<g/>" * 20000 + "</svg>"):
        with pytest.raises(ValueError):
            svg_safe.sanitize(bad)
    with pytest.raises(ValueError):
        svg_safe.clean_figure({"svg": GOOD_SVG})  # sin alt


def test_theory_card_figure_survives_or_is_dropped_alone():
    payload = {"units": [{"ref": "u", "title": "U", "lessons": [{"ref": "l", "title": "L", "steps": [
        {"ref": "t", "kind": "info", "prompt": "Plano complejo", "source": "3.2", "explanation": "x", "data": {},
         "figure": {"svg": GOOD_SVG, "alt": "El punto 3+4i en el plano", "caption": "Afijo"}},
        {"ref": "t2", "kind": "info", "prompt": "Otra", "source": "3.3", "explanation": "y", "data": {}, "figure": {"svg": "<div/>", "alt": "x"}},
        {"ref": "q", "kind": "truefalse", "prompt": "¿Sí?", "source": "3.1", "explanation": "", "data": {"answer": True}, "figure": {"svg": GOOD_SVG, "alt": "a"}},
    ]}]}]}
    draft, warnings = generator.clean_draft(payload)
    steps = draft["units"][0]["lessons"][0]["steps"]
    assert [s["ref"] for s in steps] == ["t", "t2", "q"]  # ninguna tarjeta se pierde por su figura
    assert "script" not in steps[0]["data"]["figure"]["svg"] and steps[0]["data"]["figure"]["alt"].startswith("El punto")
    assert "figure" not in steps[1]["data"] and "figure" not in steps[2]["data"]
    assert [w["level"] for w in warnings] == ["figure"]


def test_imported_figure_is_sanitized_and_served(client):
    course = copy.deepcopy(COURSE)
    course["units"][0]["lessons"][0]["steps"][0]["data"] = {"figure": {"svg": GOOD_SVG, "alt": "Un vector"}}
    assert upload(client, course).status_code == 200
    intro = client.get(f"/api/learn/lessons/{first_lesson(client)}").json()["steps"][0]
    assert intro["kind"] == "info" and intro["figure"]["alt"] == "Un vector" and "script" not in intro["figure"]["svg"]


def test_ai_writes_in_the_app_language(client, fake_claude, monkeypatch):
    seen = {}

    def fake(r, instructions, schema, text, feature, timeout):
        seen["i"] = instructions
        return {"units": []}, 0.0

    monkeypatch.setattr(generator.ai, "complete_json", fake)
    sid = str(subject_id(client))
    files = {"files": ("m.md", "# Tema", "text/markdown")}
    client.post("/api/learn/generate", files=files, data={"material_kind": "manual", "subject_id": sid})
    assert "Idioma: español" in seen["i"] and "{LANG}" not in seen["i"]
    settings = client.get("/api/settings").json()
    assert client.put("/api/settings", json={**settings, "language": "en"}).status_code == 200
    client.post("/api/learn/generate", files=files, data={"material_kind": "manual", "subject_id": sid})
    assert "Idioma: English" in seen["i"]
    client.put("/api/settings", json={**settings, "language": "es"})


def test_anki_export(client):
    upload(client, COURSE)
    course_id = client.get("/api/learn/courses").json()[0]["id"]
    r = client.get(f"/api/learn/courses/{course_id}/anki")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().split("\n")
    assert lines[:3] == ["#separator:tab", "#html:true", "#deck:Campus Pilot::Matemáticas I"]
    cards = [line.split("\t") for line in lines if not line.startswith("#")]
    assert all(len(c) == 3 for c in cards)
    choice = next(c for c in cards if c[0].startswith("¿2+2?"))
    assert "B) 4" in choice[1] and "📖 Ej. 1" in choice[1]
    assert any("\\(i^2=-1\\)" in c[0] for c in cards)  # $…$ → MathJax de Anki
    missed = client.get(f"/api/learn/courses/{course_id}/anki", params={"only_missed": True}).text
    assert len([x for x in missed.split("\n") if x and not x.startswith("#")]) == 0
