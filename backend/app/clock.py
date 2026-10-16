"""Fecha de "hoy" en la zona horaria de la instalación (CAMPUS_TZ), no la del contenedor (UTC).

Sin esto, entre medianoche y las 2 de la madrugada en Madrid la API y los avisos no estaban
de acuerdo en qué día era.
"""
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("CAMPUS_TZ", "Europe/Madrid"))


def today() -> date:
    return datetime.now(TZ).date()


def now() -> datetime:
    return datetime.now(TZ)
