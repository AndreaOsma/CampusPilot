"""Suscripción al calendario del campus virtual (Ajustes → Calendario de la universidad).

Moodle, Canvas, Blackboard, Brightspace y casi cualquier campus exportan un enlace iCal con
entregas, cuestionarios y exámenes. La app lo descarga cada pocas horas y mete cada entrada
en la agenda: como **evento** (por defecto: no toca notas) o como **entrega** (actividad con
fecha, para que cuente en el expediente). La asignatura se deduce del código o del nombre que
aparezca en la entrada; si no, la que elijas para el enlace.

Cada fila importada lleva `pack_ref = "ical:<feed>:<hash del UID>"`: volver a sincronizar
actualiza título y fecha **sin tocar lo tuyo** (hecho, nota, apuntes), y lo que desaparece
del calendario se borra solo si aún no ha pasado.

Seguridad (el servidor descarga una URL que pone quien usa la app): solo http/https, nada de
IPs privadas, de loopback ni locales (salvo `CAMPUS_ALLOW_PRIVATE_FEEDS=1`, para un campus en
la propia red), redirecciones comprobadas una a una, 15 s y 2 MB como máximo.
"""
from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import re
import socket
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy.orm import Session

from . import clock, models

logger = logging.getLogger("campus.calendar")

MAX_BYTES = 2_000_000
TIMEOUT_S = 15
SYNC_EVERY = timedelta(hours=3)
PAST_DAYS, FUTURE_DAYS = 30, 400


# ---------- Descarga segura ----------

def normalize_url(url: str) -> str:
    url = url.strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    return url


def _private_allowed() -> bool:
    return os.getenv("CAMPUS_ALLOW_PRIVATE_FEEDS", "").strip() in ("1", "true", "yes")


def _check_host(url: str) -> None:
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("El enlace tiene que empezar por https:// (o webcal://)")
    if _private_allowed():
        return
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError(f"No se encuentra el servidor «{parts.hostname}»")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("Ese enlace apunta a una dirección privada o local: no se descarga")


def _check_peer(response: httpx.Response) -> None:
    """La IP a la que de verdad se conectó. _check_host resuelve antes, pero httpx vuelve a
    resolver al conectar: un DNS que cambie entre medias (DNS rebinding) colaría una IP interna."""
    if _private_allowed():
        return
    stream = response.extensions.get("network_stream")
    addr = stream.get_extra_info("server_addr") if stream is not None else None
    if not addr:
        raise ValueError("No se pudo comprobar a qué dirección se conectó: no se descarga")
    if not ipaddress.ip_address(addr[0]).is_global:
        raise ValueError("Ese enlace apunta a una dirección privada o local: no se descarga")


def fetch(url: str) -> str:
    """Descarga el calendario comprobando cada salto de redirección."""
    url = normalize_url(url)
    with httpx.Client(timeout=TIMEOUT_S, follow_redirects=False, headers={"User-Agent": "CampusPilot/1 (+calendario)"}) as client:
        for _ in range(4):
            _check_host(url)
            with client.stream("GET", url) as r:
                _check_peer(r)
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    url = urljoin(url, r.headers["location"])
                    continue
                if r.status_code != 200:
                    raise ValueError(f"El campus respondió {r.status_code}")
                data = b""
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > MAX_BYTES:
                        raise ValueError("El calendario supera 2 MB")
                text = data.decode("utf-8", errors="replace")
                if "BEGIN:VCALENDAR" not in text[:2000].upper():
                    raise ValueError("Eso no es un calendario iCal (no empieza por BEGIN:VCALENDAR)")
                return text
    raise ValueError("Demasiadas redirecciones")


# ---------- Lectura del iCal ----------

@dataclass
class Item:
    uid: str
    summary: str
    start: date
    start_time: Optional[str]
    end: Optional[date]
    end_time: Optional[str]
    description: str
    url: str
    categories: str


def _unescape(v: str) -> str:
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def _when(value: str, params: dict[str, str]) -> tuple[date, Optional[str]]:
    v = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", v):
        return datetime.strptime(v[:8], "%Y%m%d").date(), None
    dt = datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
    if v.endswith("Z"):
        dt = dt.replace(tzinfo=timezone.utc)
    elif params.get("TZID"):
        try:
            dt = dt.replace(tzinfo=ZoneInfo(params["TZID"].strip('"')))
        except (ZoneInfoNotFoundError, ValueError):
            dt = dt.replace(tzinfo=clock.TZ)
    else:
        dt = dt.replace(tzinfo=clock.TZ)
    local = dt.astimezone(clock.TZ)
    return local.date(), local.strftime("%H:%M")


def parse(text: str) -> list[Item]:
    # Líneas plegadas (RFC 5545 §3.1): una línea que empieza por espacio o tab continúa la anterior.
    lines = re.sub(r"\r?\n[ \t]", "", text).splitlines()
    items: list[Item] = []
    cur: Optional[dict] = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            cur = {}
            continue
        if line == "END:VEVENT":
            if cur is not None and cur.get("DTSTART"):
                try:
                    start, st = _when(*cur["DTSTART"])
                    end, et = _when(*cur["DTEND"]) if cur.get("DTEND") else (None, None)
                except ValueError:
                    cur = None
                    continue
                if end is not None and st is None and end > start:
                    end -= timedelta(days=1)  # en un evento de día entero, DTEND es exclusivo
                summary = _unescape(cur.get("SUMMARY", ("", {}))[0]) or "(sin título)"
                uid = cur.get("UID", ("", {}))[0] or f"{summary}|{start}"
                items.append(Item(uid=uid, summary=summary[:200], start=start, start_time=st, end=end if end != start else None,
                                  end_time=et if et != st else None, description=_unescape(cur.get("DESCRIPTION", ("", {}))[0])[:2000],
                                  url=cur.get("URL", ("", {}))[0][:500], categories=_unescape(cur.get("CATEGORIES", ("", {}))[0])[:300]))
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        head, value = line.split(":", 1)
        name, *raw_params = head.split(";")
        params = dict(p.split("=", 1) for p in raw_params if "=" in p)
        cur[name.upper()] = (value, {k.upper(): v for k, v in params.items()})
    return items


# ---------- Volcado a la agenda ----------

def _norm(text: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^a-z0-9.]+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


def match_subject(item: Item, subjects: list[models.Subject]) -> Optional[models.Subject]:
    haystack = f" {_norm(item.categories)} {_norm(item.summary)} {_norm(item.description[:500])} "
    for s in subjects:
        if s.code and len(s.code) >= 3 and f" {_norm(s.code)} " in haystack:
            return s
    by_len = sorted(subjects, key=lambda s: -len(s.name))
    for s in by_len:
        name = _norm(s.name)
        if len(name) >= 4 and f" {name} " in haystack:
            return s
    return None


_EXAM = re.compile(r"\b(exam|examen|prueba final|final exam|midterm|parcial)\b", re.I)
_QUIZ = re.compile(r"\b(quiz|cuestionari|test)\w*", re.I)
_LAB = re.compile(r"\b(pr[aá]ctica|lab)\w*", re.I)


def _kind(summary: str, as_activity: bool) -> str:
    if _EXAM.search(summary):
        return "exam"
    if not as_activity:
        return "other"
    if _QUIZ.search(summary):
        return "quiz"
    if _LAB.search(summary):
        return "pr"
    return "pec"


def sync(db: Session, feed: models.CalendarFeed, text: Optional[str] = None) -> dict:
    """Descarga (o usa `text`) y vuelca el calendario. Devuelve contadores."""
    items = parse(text if text is not None else fetch(feed.url))
    today = clock.today()
    window = (today - timedelta(days=PAST_DAYS), today + timedelta(days=FUTURE_DAYS))
    subjects = db.query(models.Subject).filter(models.Subject.status.in_(("enrolled", "pending"))).all()
    default = db.get(models.Subject, feed.subject_id) if feed.subject_id else None
    prefix = f"ical:{feed.id}:"
    Model = models.Activity if feed.mode == "activities" else models.Event
    existing = {row.pack_ref: row for row in db.query(Model).filter(Model.pack_ref.like(f"{prefix}%"))}
    seen: set[str] = set()
    counts = {"new": 0, "updated": 0, "removed": 0, "skipped": 0}
    for it in items:
        if not window[0] <= it.start <= window[1]:
            continue
        subject = match_subject(it, subjects) or default
        if feed.mode == "activities" and subject is None:
            counts["skipped"] += 1  # una actividad tiene que ser de una asignatura
            continue
        ref = prefix + hashlib.sha1(it.uid.encode()).hexdigest()[:20]
        seen.add(ref)
        row = existing.get(ref)
        if row is None:
            row = Model(pack_ref=ref, notes="") if feed.mode != "activities" else Model(pack_ref=ref, subject_id=subject.id, notes="", evaluable=True)
            db.add(row)
            counts["new"] += 1
        else:
            counts["updated"] += 1
        if feed.mode == "activities":
            row.subject_id = subject.id
            row.name, row.kind = it.summary[:160], _kind(it.summary, True)
            row.due_date, row.due_time = it.start, it.start_time
            if not row.notes and it.url:
                row.notes = it.url
        else:
            row.subject_id = subject.id if subject else None
            row.title, row.kind = it.summary, _kind(it.summary, False)
            row.date, row.end_date, row.start_time, row.end_time = it.start, it.end, it.start_time, it.end_time
            row.url = it.url
    for ref, row in existing.items():
        when = row.due_date if feed.mode == "activities" else row.date
        if ref not in seen and when and when >= today:
            db.delete(row)
            counts["removed"] += 1
    feed.last_sync = datetime.now(timezone.utc).replace(tzinfo=None)
    feed.last_error = ""
    feed.items = len(seen)
    db.commit()
    return counts


def sync_due(db: Session) -> None:
    """Del planificador: sincroniza los enlaces que tocan; un fallo queda en el enlace, no tumba nada."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for feed in db.query(models.CalendarFeed).filter(models.CalendarFeed.enabled.is_(True)).all():
        if feed.last_sync and now - feed.last_sync < SYNC_EVERY:
            continue
        try:
            sync(db, feed)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            feed.last_error = str(exc)[:500]
            feed.last_sync = now
            db.commit()
            logger.warning("calendar feed %s failed: %s", feed.id, exc)
