"""Ajustes, copia de seguridad completa (export/import JSON), importación desde la app iOS
antigua, avisos por ntfy y estado del feed iCal."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import Date, DateTime
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .. import clock, config, models, scheduler
from ..crud import require
from ..database import get_db
from .. import schemas
from ..schemas import SettingsModel
from ..settings_store import load_settings, save_settings

router = APIRouter(prefix="/api", tags=["settings"])

# v2: incluye learn_profile (chispas, días libres) y la restauración valida cada fila.
BUNDLE_VERSION = 2
COMPATIBLE_VERSIONS = (1, 2)
# Orden de inserción respetando claves foráneas (y el inverso para borrar).
BUNDLE_TABLES = [
    models.Setting,
    models.InstalledPack,
    models.Career,
    models.Term,
    models.Subject,
    models.EvalGroup,
    models.Activity,
    models.Event,
    models.Habit,
    models.HabitCheck,
    models.StudySession,
    models.ReviewCard,
    models.CalendarFeed,
    models.Material,
    models.Expense,
    models.Grant,
    models.Procedure,
    models.PathItem,
    models.Course,
    models.CourseUnit,
    models.Lesson,
    models.LessonStep,
    models.LearnDay,
    models.LearnProfile,
    models.InboxMessage,
]

# Las filas restauradas pasan por los mismos esquemas que la API (URLs, enums, rangos): una
# copia manipulada no puede colar un `javascript:` ni un estado inventado.
ROW_SCHEMAS = {
    models.Career: schemas.CareerIn,
    models.Term: schemas.TermIn,
    models.Subject: schemas.SubjectIn,
    models.EvalGroup: schemas.EvalGroupIn,
    models.Activity: schemas.ActivityIn,
    models.Event: schemas.EventIn,
    models.Habit: schemas.HabitIn,
    models.StudySession: schemas.SessionIn,
    models.Expense: schemas.ExpenseIn,
    models.Grant: schemas.GrantIn,
    models.Procedure: schemas.ProcedureIn,
    models.PathItem: schemas.PathItemIn,
}


def _validate_row(model, raw: dict) -> None:
    schema = ROW_SCHEMAS.get(model)
    if schema is not None:
        fields = schema.model_fields
        try:
            schema.model_validate({k: v for k, v in raw.items() if k in fields})
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(x) for x in first.get("loc", ()))
            raise HTTPException(status_code=422, detail=f"Copia no válida ({model.__tablename__} {raw.get('id')}: {where}): {first.get('msg')}")
    elif model is models.Lesson:
        try:
            schemas.check_url(raw.get("theory_url") or "")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Copia no válida (lessons {raw.get('id')}): {exc}")

# Estados de la app iOS (SwiftUI) → estados de aquí.
IOS_STATUS = {"Enrolled": "enrolled", "Convalidated": "convalidated", "Pending": "pending", "Completed": "passed"}


@router.get("/settings", response_model=SettingsModel)
def get_settings(db: Session = Depends(get_db)):
    return load_settings(db)


@router.put("/settings", response_model=SettingsModel)
def put_settings(payload: SettingsModel, db: Session = Depends(get_db)):
    return save_settings(db, payload)


def _row_to_dict(row) -> dict:
    out = {}
    for col in row.__table__.columns:
        value = getattr(row, col.name)
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        out[col.name] = value
    return out


def export_bundle(db: Session) -> dict:
    return {
        "app": "campus-pilot",
        "version": BUNDLE_VERSION,
        "exported_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "tables": {
            m.__tablename__: [
                _row_to_dict(r) for r in db.query(m).all() if not (m is models.Setting and r.key.startswith("_"))
            ]
            for m in BUNDLE_TABLES
        },
    }


def import_bundle_replace(db: Session, bundle: dict) -> None:
    if bundle.get("app") != "campus-pilot" or bundle.get("version") not in COMPATIBLE_VERSIONS:
        raise HTTPException(status_code=422, detail="El archivo no es una copia de Campus Pilot compatible")
    tables = bundle.get("tables")
    if not isinstance(tables, dict):
        raise HTTPException(status_code=422, detail="Copia sin tablas")
    try:
        for model in reversed(BUNDLE_TABLES):
            db.query(model).delete()
        for model in BUNDLE_TABLES:
            columns = {c.name: c for c in model.__table__.columns}
            for raw in tables.get(model.__tablename__, []):
                if not isinstance(raw, dict):
                    continue
                _validate_row(model, raw)
                values = {}
                for key, value in raw.items():
                    col = columns.get(key)
                    if col is None:
                        continue
                    if value is not None and isinstance(col.type, DateTime):
                        value = datetime.fromisoformat(value)
                    elif value is not None and isinstance(col.type, Date):
                        value = date.fromisoformat(value)
                    values[key] = value
                db.add(model(**values))
            db.flush()
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"No se pudo restaurar la copia: {exc.__class__.__name__}")


@router.get("/backup")
def download_backup(db: Session = Depends(get_db)):
    body = json.dumps(export_bundle(db), ensure_ascii=False, indent=1)
    stamp = clock.today().isoformat()
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="campus-pilot-{stamp}.json"'},
    )


async def _read_json(file: UploadFile) -> object:
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera los 20 MB")
    try:
        return json.loads(data)
    except ValueError:
        raise HTTPException(status_code=422, detail="JSON no válido")


@router.post("/backup/restore")
async def restore_backup(file: UploadFile = File(...), db: Session = Depends(get_db)):
    bundle = await _read_json(file)
    if not isinstance(bundle, dict):
        raise HTTPException(status_code=422, detail="El archivo no es una copia de Campus Pilot compatible")
    import_bundle_replace(db, bundle)
    return {"status": "ok"}


@router.post("/import/ios")
async def import_ios(career_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa el JSON que exporta la app iOS (lista de {name, credits, career, semester, status}).
    Las asignaturas que ya existen con el mismo nombre en la carrera solo actualizan su estado."""
    career = require(db, models.Career, career_id, "La carrera")
    rows = await _read_json(file)
    if not isinstance(rows, list):
        raise HTTPException(status_code=422, detail="Se esperaba la lista de asignaturas que exporta la app iOS")
    existing = {s.name.strip().lower(): s for s in db.query(models.Subject).filter_by(career_id=career.id)}
    added = updated = skipped = 0
    for row in rows[:1000]:
        if not isinstance(row, dict):
            skipped += 1
            continue
        name = str(row.get("name", "")).strip()[:200]
        try:
            credits = float(str(row.get("credits", "")).replace(",", "."))
        except ValueError:
            credits = 0
        if not name or not 0 < credits <= 60:
            skipped += 1
            continue
        status = IOS_STATUS.get(str(row.get("status", "")), "pending")
        subject = existing.get(name.lower())
        if subject is None:
            subject = models.Subject(career_id=career.id, name=name, ects=credits, status=status)
            db.add(subject)
            existing[name.lower()] = subject
            added += 1
        else:
            if subject.status == "pending":
                subject.status = status
            updated += 1
    db.commit()
    return {"added": added, "updated": updated, "skipped": skipped}


# ---------- Avisos ----------

@router.get("/notifications/status")
def notifications_status():
    return {"configured": scheduler.ntfy_configured(), "server": config.NTFY_URL or None}


@router.get("/notifications/preview")
def notifications_preview(db: Session = Depends(get_db)):
    return {"lines": scheduler.build_digest(db, clock.today())}


@router.post("/notifications/test")
def notifications_test(db: Session = Depends(get_db)):
    topic = load_settings(db).notifications.topic
    lines = scheduler.build_digest(db, clock.today()) or ["Todo en orden: nada pendiente hoy."]
    try:
        scheduler.send_ntfy(topic, "Campus Pilot · prueba", "\n".join(lines))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=502, detail="ntfy no respondió; revisa el topic y la conexión")
    return {"status": "sent", "topic": topic}


@router.get("/ical/status")
def ical_status():
    """Ruta del feed con token (si está configurado). Esta respuesta solo la ve quien ya pasó
    el SSO; el token sirve para que la app de calendario se suscriba sin él."""
    if not config.ICAL_TOKEN:
        return {"configured": False, "path": None}
    return {"configured": True, "path": f"/ical/{config.ICAL_TOKEN}.ics"}
