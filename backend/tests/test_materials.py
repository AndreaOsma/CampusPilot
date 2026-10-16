import io

import pytest
from pypdf import PdfWriter

from app import config, generator, materials, tutor

from .test_learn import subject_id
from .test_learn_v2 import fake_claude  # noqa: F401


def pdf_bytes() -> bytes:
    # PDF mínimo con texto (pypdf no crea texto; uno escrito a mano con una página y un Tj).
    content = b"BT /F1 12 Tf 72 720 Td (Numeros complejos: z = a + bi, modulo y argumento. Forma polar del afijo.) Tj ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, o in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % x for x in offsets))
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue()


def test_library_upload_file_and_delete(client, tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "FILES_DIR", tmp_path)
    sid = subject_id(client)
    r = client.post("/api/materials", files={"file": ("modulo1.pdf", pdf_bytes(), "application/pdf")}, data={"subject_id": str(sid), "module_ref": "m1"})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["has_file"] and m["pages"] == 1 and m["module_ref"] == "m1"
    f = client.get(f"/api/materials/{m['id']}/file")
    assert f.status_code == 200 and f.headers["content-type"] == "application/pdf" and f.content.startswith(b"%PDF")
    # Mismo nombre: se sustituye, no se duplica.
    client.post("/api/materials", files={"file": ("modulo1.pdf", pdf_bytes(), "application/pdf")}, data={"subject_id": str(sid)})
    assert len(client.get("/api/materials", params={"subject_id": sid}).json()) == 1
    # Las barreras del generador también aquí.
    bad = client.post("/api/materials", files={"file": ("pec2-enunciado.md", "Ejercicio 1", "text/markdown")}, data={"subject_id": str(sid)})
    assert bad.status_code == 422
    client.delete(f"/api/materials/{m['id']}")
    assert client.get("/api/materials", params={"subject_id": sid}).json() == [] and not (tmp_path / f"{m['id']}.pdf").exists()


def test_generate_from_library_cites_pages(client, fake_claude, tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "FILES_DIR", tmp_path)
    sid = subject_id(client)
    seen = {}

    def fake(r, instructions, schema, text, feature, timeout):
        seen["text"] = text
        return {"units": [{"ref": "u", "title": "Complejos", "lessons": [{"ref": "l", "title": "Polar", "steps": [
            {"ref": "t", "kind": "info", "prompt": "Forma polar", "source": "Módulo 1, 3.4", "explanation": "r y θ.", "data": {},
             "material": "modulo1.pdf", "page": 1},
            {"ref": "q", "kind": "truefalse", "prompt": "¿$|i| = 1$?", "source": "3.4", "explanation": "", "data": {"answer": True}},
        ]}]}]}, 0.0

    monkeypatch.setattr(generator.ai, "complete_json", fake)
    # Subir para generar lo guarda en la biblioteca…
    r = client.post("/api/learn/generate", files={"files": ("modulo1.pdf", pdf_bytes(), "application/pdf")}, data={"material_kind": "manual", "subject_id": str(sid)})
    job = client.get(f"/api/learn/jobs/{r.json()['id']}").json()
    mat = client.get("/api/materials", params={"subject_id": sid}).json()[0]
    card = job["draft"]["units"][0]["lessons"][0]["steps"][0]
    assert card["data"]["cite"] == {"material_id": mat["id"], "page": 1}
    course = client.post(f"/api/learn/jobs/{job['id']}/import", json={}).json()
    lesson_id = client.get(f"/api/learn/courses/{course['id']}").json()["units"][0]["lessons"][0]["id"]
    step = client.get(f"/api/learn/lessons/{lesson_id}").json()["steps"][0]
    assert step["cite"] == {"material_id": mat["id"], "page": 1}
    assert "cite" not in str(client.get(f"/api/learn/courses/{course['id']}/export").json())  # no viaja fuera
    # …y luego se puede generar desde la biblioteca sin volver a subirlo.
    r = client.post("/api/learn/generate", data={"material_kind": "manual", "subject_id": str(sid), "material_ids": [str(mat["id"])]})
    assert r.status_code == 202, r.text
    assert "Numeros complejos" in seen["text"] and "===== MATERIAL: modulo1.pdf =====" in seen["text"]
    other = client.post("/api/subjects", json={"career_id": client.get("/api/careers").json()[0]["id"], "name": "Otra"}).json()
    r = client.post("/api/learn/generate", data={"material_kind": "manual", "subject_id": str(other["id"]), "material_ids": [str(mat["id"])]})
    assert r.status_code == 422  # material de otra asignatura


def test_tutor_answers_from_material_and_refuses_evaluables(client, fake_claude, tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "FILES_DIR", tmp_path)
    sid = subject_id(client)
    assert client.post("/api/learn/tutor", json={"subject_id": sid, "question": "¿Qué es el módulo?"}).status_code == 422  # sin biblioteca
    client.post("/api/materials", files={"file": ("modulo1.pdf", pdf_bytes(), "application/pdf")}, data={"subject_id": str(sid)})
    seen = {}

    def fake(r, instructions, schema, text, feature, timeout):
        seen["i"], seen["t"] = instructions, text
        return {"answer": "El **módulo** es $|z|=\\sqrt{a^2+b^2}$.", "in_material": True,
                "citations": [{"material": "modulo1.pdf", "page": 1, "section": "3.4"}, {"material": "inventado.pdf", "page": 3, "section": "x"}]}, 0.0

    monkeypatch.setattr(tutor.ai, "complete_json", fake)
    r = client.post("/api/learn/tutor", json={"subject_id": sid, "question": "¿Qué es el módulo de un complejo?",
                                              "history": [{"role": "user", "text": "hola"}, {"role": "tutor", "text": "¡Hola!"}]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["citations"][0]["material_id"] and out["citations"][0]["has_file"] and out["citations"][1]["material_id"] is None
    assert "Numeros complejos" in seen["t"] and "Estudiante: hola" in seen["t"] and "4b." not in seen["i"]
    for q in ("Resuélveme la PEC 2", "¿Cuál es la respuesta del cuestionario 3?", "Enunciado de la actividad: calcula…"):
        assert client.post("/api/learn/tutor", json={"subject_id": sid, "question": q}).status_code == 422, q
    # Asignatura con la IA prohibida: regla extra en el prompt.
    s = next(x for x in client.get("/api/subjects").json() if x["id"] == sid)
    client.put(f"/api/subjects/{sid}", json={**s, "ai_policy": "forbidden"})
    client.post("/api/learn/tutor", json={"subject_id": sid, "question": "¿Qué es la forma polar?"})
    assert "4b." in seen["i"]
