"""Cabeceras de seguridad en todas las respuestas (ASGI puro, sin tocar el cuerpo).

La CSP solo va en las páginas HTML: la app no carga nada de fuera ni tiene scripts en línea.
`style-src 'unsafe-inline'` hace falta por los estilos en línea de React y de KaTeX, e
`img-src data:` por las figuras SVG de la teoría (van como <img src="data:…">). No se pone en
el PDF de la biblioteca: el visor de PDF del navegador puede romperse con `object-src 'none'`.
"""
from __future__ import annotations

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
COMMON = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
]


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                headers += [(k, v) for k, v in COMMON if k not in present]
                ctype = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                if ctype.startswith(b"text/html") and b"content-security-policy" not in present:
                    headers.append((b"content-security-policy", CSP.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
