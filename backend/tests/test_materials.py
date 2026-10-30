import io

import pytest
from pypdf import PdfWriter

from app import config, generator, materials, models, tutor
from app.database import SessionLocal

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


def test_video_with_transcript_is_a_resource_and_streams(client, tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "FILES_DIR", tmp_path)
    sid = subject_id(client)
    video = b"\x00\x00\x00\x18ftypmp42" + b"x" * 5000
    transcript = "<!-- página 1 -->\nEn este vídeo hablaremos de las matrices y de los sistemas de ecuaciones lineales."
    r = client.post("/api/materials/video", data={"subject_id": str(sid), "module_ref": "Unidad 2"},
                    files={"video": ("Ecuaciones lineales.mp4", video, "video/mp4"),
                           "transcript": ("ecuaciones-lineales-transcripcion.md", transcript.encode(), "text/markdown")})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["kind"] == "video" and m["file_mime"] == "video/mp4" and m["module_ref"] == "Unidad 2" and m["chars"] > 50
    assert not list(tmp_path.glob(".subida-*")), "no quedan temporales"
    full = client.get(f"/api/materials/{m['id']}/file")
    assert full.status_code == 200 and full.headers["content-type"] == "video/mp4" and full.content == video
    part = client.get(f"/api/materials/{m['id']}/file", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100  # saltar a cualquier minuto
    # La transcripción es lo que lee la IA; el vídeo no entra en el prompt.
    with SessionLocal() as db:
        assert "matrices" in materials.as_part(db.get(models.Material, m["id"]))
    assert client.delete(f"/api/materials/{m['id']}").status_code == 204
    assert not list(tmp_path.iterdir())


def test_video_rejects_other_formats_and_evaluables(client, tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "FILES_DIR", tmp_path)
    sid = subject_id(client)
    bad = client.post("/api/materials/video", data={"subject_id": str(sid)}, files={"video": ("notas.pdf", b"%PDF", "application/pdf")})
    assert bad.status_code == 422
    pec = client.post("/api/materials/video", data={"subject_id": str(sid)}, files={"video": ("PEC 2 resuelta.mp4", b"x" * 10, "video/mp4")})
    assert pec.status_code == 422
    assert not list(tmp_path.iterdir())


def pdf_with_images() -> bytes:
    """Seis páginas con texto: dos imágenes de contenido (p1, p2), un «logo» igual en p3–p5 y un icono pequeño en p6."""
    from PIL import Image
    from pypdf import PdfReader

    imgs = [Image.new("RGB", (400, 300), c) for c in ("red", "blue")]
    logo = Image.new("RGB", (400, 300), "green")
    imgs += [logo, logo, logo, Image.new("RGB", (100, 80), "black")]
    buf = io.BytesIO()
    imgs[0].save(buf, "PDF", save_all=True, append_images=imgs[1:])
    text = PdfReader(io.BytesIO(pdf_bytes())).pages[0]
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(buf.getvalue())).pages:
        writer.add_page(page).merge_page(text)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_theory_uses_manual_images(client, fake_claude, tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    monkeypatch.setattr(materials, "FILES_DIR", tmp_path)
    sid = subject_id(client)
    seen = {}

    def fake(r, instructions, schema, text, feature, timeout):
        seen["text"], seen["instructions"] = text, instructions
        card = {"kind": "info", "source": "3.4", "explanation": "r y θ.", "data": {}, "material": "modulo1.pdf"}
        return {"units": [{"ref": "u", "title": "Complejos", "lessons": [{"ref": "l", "title": "Polar", "steps": [
            {**card, "ref": "a", "prompt": "Con imagen", "page": 2, "image": {"ref": "p2-1", "alt": "El plano complejo", "caption": "Figura"}},
            {**card, "ref": "b", "prompt": "Imagen de otra página", "page": 5, "image": {"ref": "p1-1", "alt": "x"}},
            {**card, "ref": "c", "prompt": "Imagen que no existe", "page": 3, "image": {"ref": "p3-1", "alt": "x"}},
            {"ref": "q", "kind": "truefalse", "prompt": "¿$|i| = 1$?", "source": "3.4", "explanation": "", "data": {"answer": True}},
        ]}]}]}, 0.0

    monkeypatch.setattr(generator.ai, "complete_json", fake)
    r = client.post("/api/learn/generate", files={"files": ("modulo1.pdf", pdf_with_images(), "application/pdf")}, data={"material_kind": "manual", "subject_id": str(sid)})
    assert r.status_code == 202, r.text
    # Solo las imágenes de contenido: ni el logo repetido ni el icono pequeño.
    assert "[imagen p1-1" in seen["text"] and "[imagen p2-1" in seen["text"]
    assert "p3-1" not in seen["text"] and "p6-1" not in seen["text"]
    assert "Imágenes del manual" in seen["instructions"]
    job = client.get(f"/api/learn/jobs/{r.json()['id']}").json()
    mat = client.get("/api/materials", params={"subject_id": sid}).json()[0]
    cards = {s["ref"]: s for s in job["draft"]["units"][0]["lessons"][0]["steps"]}
    assert cards["a"]["data"]["image"] == {"material_id": mat["id"], "ref": "p2-1", "alt": "El plano complejo", "caption": "Figura"}
    assert "image" not in cards["b"]["data"] and "image" not in cards["c"]["data"]
    assert sum(w["level"] == "figure" for w in job["warnings"]) == 2
    img = client.get(f"/api/materials/{mat['id']}/images/p2-1")
    # Pillow mete las imágenes RGB en el PDF como JPEG: se sirven tal cual, como JPEG.
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and img.content.startswith(b"\xff\xd8")
    for bad in ("p3-1", "..%2Fx", "p2-1.png"):
        assert client.get(f"/api/materials/{mat['id']}/images/{bad}").status_code == 404
    course = client.post(f"/api/learn/jobs/{job['id']}/import", json={}).json()
    lesson_id = client.get(f"/api/learn/courses/{course['id']}").json()["units"][0]["lessons"][0]["id"]
    step = client.get(f"/api/learn/lessons/{lesson_id}").json()["steps"][0]
    assert step["image"]["ref"] == "p2-1"
    assert "p2-1" not in str(client.get(f"/api/learn/courses/{course['id']}/export").json())  # no viaja fuera
    # Borrar el material se lleva sus imágenes, y la tarjeta deja de enseñarla.
    assert client.delete(f"/api/materials/{mat['id']}").status_code == 204
    assert not materials.images_dir(mat["id"]).exists()
    assert "image" not in client.get(f"/api/learn/lessons/{lesson_id}").json()["steps"][0]


def test_split_material_cuts_between_pages_and_repeats_header():
    text = "===== MATERIAL: m.pdf =====\n" + "".join(f"<!-- página {n} -->\n" + "x" * 100 + "\n" for n in range(1, 7))
    parts = generator.split_material(text, 300)
    assert len(parts) > 1 and all(p.startswith("===== MATERIAL: m.pdf =====\n") for p in parts)
    pages = [n for p in parts for n in __import__("re").findall(r"<!-- página (\d+) -->", p)]
    assert pages == [str(n) for n in range(1, 7)]  # ninguna página se pierde ni se repite
    assert generator.split_material("corto", 300) == ["corto"]


def test_long_material_is_generated_in_parts(client, fake_claude, tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "FILES_DIR", tmp_path)
    monkeypatch.setattr(config, "GENERATOR_CHUNK_CHARS", 250)
    sid = subject_id(client)
    calls = []

    def fake(r, instructions, schema, text, feature, timeout):
        calls.append(text)
        if len(calls) == 2:
            raise RuntimeError("se cayó la IA")  # un trozo que falla no tira los demás
        n = len(calls)
        return {"units": [{"ref": "u", "title": f"Parte {n}", "lessons": [{"ref": "l", "title": "L", "steps": [
            {"ref": "q", "kind": "truefalse", "prompt": f"¿Parte {n}?", "source": "1", "explanation": "", "data": {"answer": True}},
        ]}]}]}, 0.01

    monkeypatch.setattr(generator.ai, "complete_json", fake)
    md = "".join(f"<!-- página {n} -->\nTexto de la página {n}. " + "y" * 80 + "\n" for n in range(1, 8))
    r = client.post("/api/learn/generate", files={"files": ("modulo.md", md, "text/markdown")}, data={"material_kind": "manual", "subject_id": str(sid)})
    assert r.status_code == 202, r.text
    job = client.get(f"/api/learn/jobs/{r.json()['id']}").json()
    assert len(calls) > 2 and all("===== MATERIAL: modulo.md =====" in c for c in calls)
    assert job["status"] == "done"
    refs = [u["ref"] for u in job["draft"]["units"]]
    assert len(refs) == len(calls) - 1 and len(set(refs)) == len(refs)  # sin la parte caída, sin refs repetidos
    assert any("Parte 2 de" in w["message"] for w in job["warnings"])
