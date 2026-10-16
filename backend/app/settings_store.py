"""Lectura/escritura de la tabla clave-valor `settings`, validada con SettingsModel."""
from sqlalchemy.orm import Session

from . import models
from .schemas import SettingsModel


def load_settings(db: Session) -> SettingsModel:
    raw = {row.key: row.value for row in db.query(models.Setting).all()}
    return SettingsModel.model_validate({k: v for k, v in raw.items() if k in SettingsModel.model_fields})


def save_settings(db: Session, settings: SettingsModel) -> SettingsModel:
    for key, value in settings.model_dump(mode="json").items():
        row = db.get(models.Setting, key)
        if row is None:
            db.add(models.Setting(key=key, value=value))
        else:
            row.value = value
    db.commit()
    return settings
