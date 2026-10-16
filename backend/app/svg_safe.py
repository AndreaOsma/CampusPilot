"""Figuras de la teoría: SVG escrito por la IA, saneado con lista blanca.

La IA configurada (Ajustes → Inteligencia artificial, o variable de entorno) no genera
imágenes, pero sí escribe SVG: diagramas, el plano complejo, diagramas de flujo… Funciona
igual con cualquier proveedor. Como el SVG viene de un modelo (y de cursos importados), se
reconstruye desde cero con solo lo permitido: formas, texto y marcadores; sin scripts,
eventos, enlaces, imágenes, `foreignObject`, estilos ni entidades. Además el frontend lo
pinta con `<img src="data:image/svg+xml…">`, donde un SVG no puede ejecutar nada ni cargar
recursos externos: dos barreras independientes.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

MAX_SVG_BYTES = 24_000
SVG_NS = "http://www.w3.org/2000/svg"

ELEMENTS = {"svg", "g", "path", "line", "circle", "ellipse", "rect", "polygon", "polyline", "text", "tspan", "defs", "marker", "title"}
ATTRIBUTES = {
    "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "dx", "dy",
    "d", "points", "transform", "fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap",
    "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity", "font-size", "font-family", "font-weight",
    "font-style", "text-anchor", "dominant-baseline", "marker-end", "marker-start", "marker-mid", "id",
    "refX", "refY", "markerWidth", "markerHeight", "orient", "markerUnits", "preserveAspectRatio",
}
_MARKER_REF = re.compile(r"^url\(#[A-Za-z][\w-]{0,40}\)$")
_ID = re.compile(r"^[A-Za-z][\w-]{0,40}$")
_SAFE_VALUE = re.compile(r"^[\w\s.,#%()+\-'\"/:;°]*$")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def sanitize(svg: str) -> str:
    """Devuelve el SVG reconstruido solo con lo permitido. ValueError si no es un SVG usable."""
    if not isinstance(svg, str) or not svg.strip():
        raise ValueError("figura vacía")
    if len(svg.encode("utf-8")) > MAX_SVG_BYTES:
        raise ValueError(f"figura demasiado grande (más de {MAX_SVG_BYTES // 1000} KB)")
    if re.search(r"<!(DOCTYPE|ENTITY)", svg, re.IGNORECASE):
        raise ValueError("la figura no puede declarar DOCTYPE ni entidades")
    try:
        root = ET.fromstring(svg.strip())
    except ET.ParseError as exc:
        raise ValueError(f"la figura no es XML válido ({exc})") from None
    if _local(root.tag) != "svg":
        raise ValueError("la figura tiene que ser un <svg>")

    def copy(src: ET.Element) -> ET.Element | None:
        tag = _local(src.tag)
        if tag not in ELEMENTS:
            return None
        out = ET.Element(tag)
        for key, value in src.attrib.items():
            name = _local(key)
            if name not in ATTRIBUTES or not isinstance(value, str) or len(value) > 4000:
                continue
            if name in ("marker-end", "marker-start", "marker-mid"):
                if _MARKER_REF.match(value.strip()):
                    out.set(name, value.strip())
                continue
            if name == "id":
                if _ID.match(value):
                    out.set(name, value)
                continue
            if "url(" in value.lower() or "javascript" in value.lower() or not _SAFE_VALUE.match(value):
                continue
            out.set(name, value)
        if src.text and tag in ("text", "tspan", "title"):
            out.text = src.text[:500]
        for child in src:
            c = copy(child)
            if c is not None:
                c.tail = None
                out.append(c)
            if child.tail and tag in ("text", "tspan") and child.tail.strip():
                (c if c is not None else out).tail = child.tail[:500]
        return out

    clean = copy(root)
    if clean is None or not clean.get("viewBox"):
        raise ValueError("la figura necesita viewBox (para escalar en el móvil)")
    clean.set("xmlns", SVG_NS)
    if not any(_local(e.tag) != "title" for e in clean.iter() if e is not clean):
        raise ValueError("la figura no dibuja nada")
    return ET.tostring(clean, encoding="unicode")


def clean_figure(raw: object) -> dict | None:
    """{svg, alt, caption} saneado, o None si no hay figura. ValueError si viene pero no vale."""
    if raw in (None, "", {}):
        return None
    if not isinstance(raw, dict):
        raise ValueError("«figure» tiene que ser un objeto {svg, alt, caption}")
    alt = str(raw.get("alt") or "").strip()[:300]
    if not alt:
        raise ValueError("la figura necesita «alt» (qué muestra, para lectores de pantalla)")
    return {"svg": sanitize(str(raw.get("svg") or "")), "alt": alt, "caption": str(raw.get("caption") or "").strip()[:300]}
