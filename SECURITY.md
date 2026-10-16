# Seguridad

Campus Pilot es una app autoalojada **de un solo usuario y sin autenticación propia**. El perímetro lo pones
tú: proxy con SSO (Authelia, Authentik, Cloudflare Access…) o VPN (Tailscale, WireGuard). No la expongas a
Internet sin algo delante: contiene datos personales (notas, gastos, becas, correos de la universidad).

- `deploy/docker-compose.yml` publica el puerto **solo en 127.0.0.1** por defecto (`CAMPUS_BIND`), sin root,
  sin capacidades y con el sistema de archivos de solo lectura salvo `/data` y `/tmp`.
- La versión de escritorio escucha solo en `127.0.0.1` y guarda los datos en la carpeta del usuario.

## Puntos de atención

- **Entradas validadas en el backend:** toda la API pasa por esquemas Pydantic con límites de longitud,
  rango y formato. Los enlaces solo admiten `https://`, `http://`, `obsidian://` y `mailto:`.
- **Cabeceras:** `nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` y, en las páginas, una
  CSP sin orígenes externos ni scripts en línea (`backend/app/security_headers.py`).
- **IA:** la clave del proveedor se guarda cifrada (Fernet) en `DATA_DIR/ai-key.enc`, fuera de la base de
  datos y de las copias; la API nunca la devuelve. Los modelos se llaman **sin herramientas**: el material,
  los correos y las preguntas entran como datos, y la salida se valida contra un esquema antes de guardar
  nada. Las barreras contra actividades evaluables están en el código, no solo en el prompt.
- **Figuras SVG de la teoría:** el SVG que escribe la IA (o que trae un curso importado) se reconstruye con
  lista blanca (formas, texto y flechas; sin scripts, eventos, enlaces, imágenes, `foreignObject`, estilos ni
  entidades) y se pinta como `<img>`, donde un SVG no puede ejecutar nada.
- **Calendario iCal del campus:** el servidor descarga la URL que pones, así que solo admite `http(s)` a
  direcciones públicas: comprueba la IP al resolver el nombre, en cada redirección y la del socket ya
  conectado (contra *DNS rebinding*), con 15 s y 2 MB como máximo. `CAMPUS_ALLOW_PRIVATE_FEEDS=1` lo
  permite para un campus en tu propia red. La API no devuelve el enlace entero (suele llevar un token).
- **Biblioteca de materiales:** los PDF se guardan con el id como nombre (nunca el del archivo subido) y se
  sirven con `nosniff`. Pasan las mismas comprobaciones que el generador.
- **Módulos de estudios y cursos subidos:** JSON validado entero (formato, versión, referencias cruzadas)
  antes de escribir nada, con tamaño máximo. No ejecutan código.
- **Fórmulas:** el texto lo pinta React (escapado); solo el HTML que genera KaTeX (`trust: false`) entra
  como HTML.
- **Restaurar copia:** sustituye todos los datos. Solo acepta copias de Campus Pilot con la versión de
  formato esperada, de 20 MB como máximo, y se aplica en una transacción (si falla, se deshace).
- **Rutas sin SSO:** el feed iCal (`/ical/<token>.ics`, desactivado sin `CAMPUS_ICAL_TOKEN`) y la bandeja
  (`/inbox/*`, solo con su token). Los tokens se comparan en tiempo constante; sin token, 404.
- **Credenciales de ntfy y de la bandeja:** por variable o por fichero montado en solo lectura. Nunca se
  guardan en la base de datos ni se envían al navegador.
- **Datos en el navegador:** la PWA guarda en caché las últimas respuestas de la API para abrir sin
  conexión; el temporizador y las preferencias de tema van en `localStorage`.

## Reportar un problema

Usa el aviso privado de vulnerabilidades de GitHub (*Security → Report a vulnerability* en el repositorio)
en vez de abrir un issue público.
