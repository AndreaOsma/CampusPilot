# Campus Pilot

Tu carrera, tu semestre y tu estudio en un solo sitio, para **cualquier universidad**: expediente
con la nota que necesitas, agenda de entregas, lecciones con teoría generadas desde tus manuales,
tutor, plan semanal y bandeja de correos de la universidad.

- **Backend:** FastAPI (Python 3.12) + SQLAlchemy + Alembic + SQLite
- **Frontend:** Vite + React + TypeScript (PWA)
- **Sin login en la app:** en el ordenador todo es local; en un servidor, ponla detrás de tu proxy con login o de una VPN.
- **IA a tu elección:** Claude, Gemini, OpenRouter, Ollama (local y gratis) o cualquier API compatible con OpenAI. Opcional.
- **Código y releases:** [github.com/AndreaOsma/CampusPilot](https://github.com/AndreaOsma/CampusPilot)
- **Docker Hub:** [andreaosma/campuspilot](https://hub.docker.com/r/andreaosma/campuspilot)

Interfaz en **español** e **inglés**.

---

## 📥 Descarga rápida

| | Plataforma | |
|:---:|---|---|
| 🪟 | **Windows** | [**Descargar instalador**](https://github.com/AndreaOsma/CampusPilot/releases/latest) — `CampusPilotSetup-x.y.z.exe` |
| 🍎 | **macOS** | [**Descargar instalador**](https://github.com/AndreaOsma/CampusPilot/releases/latest) — `Campus Pilot-x.y.z.dmg` (Apple Silicon) |
| 🐳 | **Docker / self-host** | `docker run --rm -p 127.0.0.1:8080:8080 -v campus_data:/data andreaosma/campuspilot:latest` |

Detalle de cada camino (datos, actualizaciones, requisitos) más abajo ↓

---

## Elige cómo usarlo

| Camino | Para quién | Datos |
|--------|------------|-------|
| [🪟 Windows](#escritorio) | Uso diario en tu ordenador, sin servidor | SQLite en `%LOCALAPPDATA%\Campus Pilot\data` |
| [🍎 macOS](#escritorio) | Uso diario en tu ordenador, sin servidor | SQLite en `~/Library/Application Support/Campus Pilot/data` |
| [🐳 Docker / self-host](#self-hosted-docker) | Tenerla siempre encendida y abrirla desde el móvil (PWA) | SQLite en un volumen Docker |
| [🛠️ Desarrollo](#desarrollo) | Cambiar código | SQLite local |

---

<a id="escritorio"></a>
## 🪟🍎 Escritorio (Windows y macOS)

1. Descarga el instalador del [último release](https://github.com/AndreaOsma/CampusPilot/releases/latest) y ábrelo.
   En macOS, la primera vez: clic derecho → *Abrir* (la app no está firmada por Apple).
2. Se abre en su propia ventana; el servidor escucha solo en `127.0.0.1:17891` y solo hay una
   instancia a la vez.
3. Para las funciones con IA, elige proveedor en *Ajustes → Inteligencia artificial* (en el
   escritorio no hay Claude Code: usa una clave de Claude, Gemini u OpenRouter, o un servidor Ollama).

Tus datos quedan en tu carpeta de usuario (ver la tabla de arriba) y **no se borran al desinstalar**.
Para actualizar, instala la versión nueva encima. Copia de seguridad: *Ajustes → Descargar copia*.

---

<a id="self-hosted-docker"></a>
## 🐳 Self-hosted (Docker)

Una sola imagen (interfaz + API + SQLite) que escucha en el puerto **8080**.

```sh
git clone https://github.com/AndreaOsma/CampusPilot.git campus-pilot
cd campus-pilot/deploy
cp .env.example .env    # opcional: puerto, zona horaria, ntfy, token iCal…
docker compose up -d --build
```

Abre `http://127.0.0.1:8080/`. Por defecto solo escucha en este equipo: la app **no tiene login
propio**, así que para usarla desde fuera ponla detrás de un proxy con autenticación (Authelia,
Authentik, Cloudflare Access…) o de una VPN (Tailscale, WireGuard). Ver [SECURITY.md](SECURITY.md).

### Variables de entorno

Todas opcionales; Compose las lee de `deploy/.env` ([ejemplo](deploy/.env.example)).

| Variable | Para qué |
|---|---|
| `CAMPUS_NTFY_URL`, `CAMPUS_NTFY_TOKEN` / `CAMPUS_NTFY_AUTH_FILE` | Resumen diario por ntfy |
| `CAMPUS_PUBLIC_URL` | Enlace que abre la notificación |
| `CAMPUS_ICAL_TOKEN` / `CAMPUS_ICAL_TOKEN_FILE` | Feed `/ical/<token>.ics` para apps de calendario |
| `CAMPUS_BIND` | Interfaz donde escucha el puerto (por defecto `127.0.0.1`, solo este equipo; `0.0.0.0` solo con un proxy con login o una VPN delante) |
| `CAMPUS_HTTP_PORT` | Puerto en el host (por defecto `8080`) |
| `CAMPUS_TZ` | Zona horaria de los avisos (por defecto `Europe/Madrid`) |
| `CAMPUS_SECRET_KEY` | Clave Fernet para cifrar la clave de la IA (vacía = se genera en `/data/secret.key`) |
| `CAMPUS_ALLOW_PRIVATE_FEEDS` | `1` permite calendarios iCal en tu propia red |

Las de la IA, el calendario del campus y la bandeja se explican en sus apartados, más abajo.

### Copias de seguridad y actualizaciones

- *Ajustes → Descargar copia* descarga todo en un JSON, y *Restaurar…* lo recupera.
- Cada noche se escribe un snapshot consistente de SQLite en `/data/snapshots/`: haz copia de
  esa carpeta con tu herramienta habitual (restic, Borg, rsync…).
- Para actualizar: `git pull` y `docker compose up -d --build`. Las migraciones se aplican solas.

---

## Primera vez en la app

El primer arranque te guía en cuatro pasos:

1. **Tu universidad:** instala tu titulación del catálogo, sube su módulo (`.json`) o créala a mano.
   Si tienes el plan de estudios oficial, después puedes crearla entera desde él (*Módulos*).
2. **Sus reglas:** escala de notas y aprobado, nombre de los créditos, calendario y, si las usa, letras.
3. **IA (opcional):** el proveedor y su clave, con un botón para probar la conexión.
4. **Listo:** activa en *Módulos* solo lo que vayas a usar.

Después, en la ficha de cada asignatura, sube su **plan docente** (objetivos, temario, fechas) y
en *Aprender* tus manuales para generar las lecciones.

## Mapa de la app

| Sección | Qué hay |
|---------|---------|
| 🏠 **Hoy** | Lo que toca hoy: entregas, repaso, lección siguiente, horas de estudio |
| 🎓 **Expediente** | Carrera, asignaturas, notas, media, *¿qué nota necesito?*, plan de semestres |
| 🗓️ **Semestre** | Agenda de entregas y eventos, semanas cargadas, hábitos |
| 🎯 **Aprender** | Esta semana, camino de lecciones, tutor, generador, biblioteca, práctica y examen |
| 📥 **Bandeja** | Correos de la universidad clasificados, con fechas propuestas |
| 🧠 **Estudio** | Temporizador, horas reales frente a previstas, tarjetas de repaso |
| 💶 **Dinero y trámites** | Gastos, matrícula, becas y plazos |
| 🧭 **Trayectoria** | Cursos, certificaciones, proyectos e idiomas |
| 🧩 **Módulos** | Activar funciones, catálogo de titulaciones, crear la carrera desde el plan de estudios |
| ⚙️ **Ajustes** | Tema, idioma, IA, calendario del campus, avisos, copias |

---

## Qué hace

- **Expediente** (siempre activo): carreras, asignaturas, ECTS por tipo, media ponderada,
  menciones, grupos de evaluación con pesos y mínimos, y *¿qué nota necesito?* con simulación.
  Dos modelos de evaluación: suma ponderada con mínimos por grupo, y evaluación continua más
  prueba final con notas mínimas (habitual en la enseñanza a distancia).
- **Semestre**: agenda de entregas y ventanas (vídeos, exámenes…), semanas cargadas ▲,
  eventos, hábitos semanales, feed iCal, resumen diario por ntfy y **suscripción al calendario
  de tu campus virtual** (Moodle, Canvas…).
- **Plan docente**: subes el de cada asignatura y salen sus objetivos de aprendizaje, el temario,
  la evaluación y las fechas; Aprender trabaja con esos objetivos.
- **Estudio**: temporizador focus, horas reales frente a previstas y preguntas de repaso
  espaciado (importadas de Markdown, con fórmulas `$…$`; solo preguntas, sin respuestas).
- **Aprender**: lecciones cortas paso a paso con ejercicios que se corrigen al momento
  (opción múltiple, verdadero/falso, numérico con tolerancia, complejo `a + bi`, ordenar
  pasos y ejercicios con **números nuevos cada vez**), pistas graduales, explicación de cada
  opción incorrecta, ejemplos resueltos que se retiran, "¿lo tienes claro?" antes de
  comprobar, mapa de dominio por concepto con práctica dirigida, modo examen con tiempo,
  racha, meta diaria de XP y repaso espaciado de lo fallado. Cada lección empieza por su
  **teoría** (con figuras y lectura en voz alta), sacada de tus materiales por el
  **generador**; un **tutor** responde dudas citando tu biblioteca, *Esta semana* dice qué toca
  y los cursos se exportan a Anki.
- **Dinero y trámites**: gastos, matrícula estimada, becas con la media que piden y trámites
  con plazo.
- **Trayectoria**: cursos, certificaciones, proyectos, prácticas, idiomas y sus competencias.
- **Bandeja de la universidad**: los correos de tu universidad que reenvías desde tu buzón
  llegan a la app, clasificados por asignatura y tipo (anuncio, nota, foro, comprobación de
  autoría…), con un resumen y las fechas que traen como **propuestas** para la agenda (no
  entran solas). Aviso por ntfy, en prioridad alta si piden una comprobación de autoría.
- **Política de IA por asignatura**: si una asignatura la prohíbe en las evaluables, se ve en
  la ficha, en la agenda y en los avisos.

Cada función se activa o desactiva en **Módulos**: cada cual usa lo que le sirve. Funciona con
cualquier universidad (escala de notas, créditos, calendario, letras…: ver *Módulos de
estudios*) y en español o inglés. Se usa en Docker o como app de escritorio (Windows/macOS).

## Módulos de estudios

Lo específico de una titulación no está en el código: va en un JSON en `packs/` que se instala
desde la app (o se sube a mano). Trae el plan de estudios, las menciones, los ECTS exigidos por
tipo, las reglas de evaluación y la política de IA de cada asignatura y, opcionalmente, el
calendario de un semestre (actividades con fecha o ventana, eventos, hábitos y trámites).

- Instalar crea la carrera con todas las asignaturas en *pendiente*.
- *Aplicar un semestre* matricula sus asignaturas y añade su calendario.
- Reinstalar o reaplicar actualiza nombres y fechas **sin tocar lo tuyo** (notas, hechos,
  estados, apuntes): cada fila creada por un módulo lleva `pack_ref`.
- Desde el expediente puedes **exportar tu carrera como módulo** (sin notas ni nada personal)
  para que otra persona la instale.

El catálogo trae un módulo de ejemplo (`packs/uoc-teleco.json`: un grado de 240 ECTS con dos
menciones y el calendario de un semestre). Si el tuyo no está, créalo desde el plan de estudios
oficial de tu titulación en un par de minutos (abajo) o a mano.

### Crear un módulo para tu universidad

1. **Desde el plan de estudios** (lo más rápido): *Módulos → Crear tu carrera desde el plan de
   estudios*. Subes el plan oficial (PDF o la página guardada como HTML) y la IA de Ajustes lo
   pasa a módulo (`backend/app/degree_plan.py`): asignaturas, créditos, tipos, semestres,
   menciones y escala de notas. Lo revisas, se crea la carrera y puedes descargar el `.json`.
2. **A mano**: crea la carrera en la app, añade asignaturas y grupos, y *Expediente →
   Exportar como módulo de estudios*. O copia `packs/uoc-teleco.json` y edítalo.
3. Valídalo sin instalar: `curl -F file=@mi-modulo.json https://tu-app/api/packs/validate`
   (errores legibles, hasta 20).
4. Para que aparezca en el catálogo de tu instalación, déjalo en `packs/` (o en
   `CAMPUS_PACKS_DIR`). Si quieres compartirlo, abre un PR con él.

La app no da nada por supuesto de ninguna universidad ni país: cada módulo declara sus reglas
en `config` (opcional; sin él, 0–10 con aprobado 5, ECTS y dos semestres desde septiembre):

| Campo | Ejemplos |
|---|---|
| `grade_max`, `pass_mark` | `10`/`5` · `20`/`10` (Portugal, Francia) · `100`/`50` · `4`/`2` (GPA) |
| `credit_label` | `"ECTS"`, `"créditos"`, `"credits"` |
| `term_system` | `semesters`, `trimesters`, `quarters`, `annual` |
| `year_start_month` | `9` (septiembre) · `3` (hemisferio sur) |
| `letters` | escala con letras, de mayor a menor: `[{"label": "A", "min": 9, "value": 9.5}, …, {"label": "D", "min": 0, "value": 1.5}]` (la nota se ve con su letra y se puede apuntar con ella; `value` es lo que se guarda) |
| `labels` | cómo llamáis a los tipos de asignatura y de actividad, y a la EC/PF (p. ej. `"pec": "PEC"`) |

El esquema completo está en `packs/schema/pack.schema.json` (también en `GET /api/packs/schema`),
útil para el autocompletado del editor. Si cambias `Pack` en `backend/app/packs.py`, regenéralo
desde `backend/` (un test falla si se queda desfasado):

```sh
python -c "import json; from app import packs; print(json.dumps(packs.Pack.model_json_schema(), ensure_ascii=False, indent=1))" > ../packs/schema/pack.schema.json
```

## Calendario de la universidad

*Ajustes → Calendario de la universidad*: pegas el enlace iCal de tu campus virtual (Moodle,
Canvas, Blackboard, Brightspace…; `webcal://` también vale) y sus entregas y exámenes entran en
la agenda, como eventos o como entregas del expediente, y se actualizan cada 3 horas
(`backend/app/calendar_feeds.py`). La asignatura se reconoce por su código o su nombre; si no,
la que elijas. Resincronizar respeta lo tuyo (hecho, nota) y borra solo lo futuro que ya no
está. El servidor solo descarga de direcciones públicas (`CAMPUS_ALLOW_PRIVATE_FEEDS=1` para un
campus en tu propia red), comprobando cada redirección, y la API nunca devuelve el enlace
entero (suele llevar un token personal).

## Plan docente

En la ficha de cada asignatura, *Plan docente*: subes el que publica la universidad (PDF,
Markdown o HTML) y la IA lo pasa a datos (`backend/app/syllabus.py`):

- **Objetivos de aprendizaje** tal como los marca la universidad (generales, conocimientos,
  habilidades, competencias), con un código (`O1`, `O2`…).
- **Temario** por módulos, con los objetivos que trabaja cada uno, y **recursos**.
- **Evaluación** (modelo, grupos, pesos y mínimos) y **fechas** de las actividades.

Sale un borrador que revisas antes de aplicarlo. Los objetivos, el temario y los recursos se
guardan en la asignatura; la evaluación y cada fecha, solo si las marcas (las que ya están en
la agenda empiezan desmarcadas, para no duplicar). La política de IA solo se rellena si
estaba sin indicar: nunca se relaja.

Con plan docente, Aprender lo usa: el generador recibe los objetivos y el temario (y el módulo
del material, si lo eliges), cada paso guarda los objetivos que practica, hay **dominio por
objetivo** con práctica dirigida (`/aprender/practica/<curso>/objetivo/<código>`) y cada
módulo enseña cuántas lecciones tiene y cuántas llevas. La teoría para lecciones existentes
también les asigna objetivos y módulo.

## Cursos de Aprender

Un curso es un JSON privado (`format: "campus-pilot-course"`, validado por
`backend/app/learn.py`) que se importa desde *Aprender*: unidades → lecciones → pasos.
Cada paso evaluable **tiene que** llevar `source` (de qué parte del material sale). Cada
lección empieza por su **teoría** (pasos `info`: tarjetas que se leen antes de las preguntas,
con el apartado del manual donde ampliarla) y, aparte, tiene una *guía* propia que escribe
quien estudia o que enlaza a sus apuntes (`theory_url`, admite `obsidian://`). Reimportar
actualiza enunciados y soluciones sin perder la guía, el progreso ni la teoría añadida después.
Los cursos no se publican en `packs/`: el material del que salen suele ser de uso personal.

### Generador de lecciones

*Aprender → Generar lecciones*: subes material de una asignatura (PDF, `.md`/`.txt`: un
módulo del manual, tus apuntes, la transcripción de un vídeo resumen) y sale un **borrador**
que revisas antes de añadirlo a su curso. Por dentro llama a la IA configurada (ver abajo)
**sin herramientas** (no lee ficheros ni ejecuta nada: solo recibe el texto) con salida JSON
validada por esquema; cada paso se valida como un curso importado y las respuestas numéricas
se recalculan con un evaluador seguro (`backend/app/safe_math.py`).

Barreras en el código, no en el prompt: se rechaza material con pinta de enunciado de una
actividad evaluable (PEC, práctica, reto, cuestionario, examen; también *assignment*, *quiz*,
*exam*, *problem set*…), por nombre y por contenido; en asignaturas con la IA prohibida en las
evaluables solo se admite manual, apuntes o vídeo resumen; y todo paso necesita `source`,
también las tarjetas de teoría (el apartado del material que hay que leer para ampliarla).

Cada lección del borrador empieza con 1–3 tarjetas de teoría sacadas del material y sigue
con sus ejercicios. Una tarjeta puede llevar una **figura** (el plano complejo, un diagrama
de flujo…): la dibuja la misma IA como SVG, así que vale con cualquier proveedor. El servidor
la reconstruye con lista blanca (`backend/app/svg_safe.py`: solo formas, texto y flechas; sin
scripts, enlaces, imágenes ni estilos) y la app la pinta como `<img>`, donde un SVG no puede
ejecutar nada. Una figura que no pasa el saneado se descarta sin perder la tarjeta. En un curso
importado va en `data.figure` = `{svg, alt, caption}` de un paso `info`.

Para las lecciones que ya tienes: *Qué sale → Teoría para las lecciones que ya tengo*. Subes el manual y sale un borrador solo con tarjetas, que al añadirlo se ponen
delante de las preguntas de cada lección (refs `teoria-*`; repetirlo las sustituye y los
ejercicios no se tocan).

Cada curso es de **una asignatura**: lo generado o importado se suma al curso
de esa asignatura (reimportar la misma fuente reemplaza solo lo suyo).

### Esta semana

Con plan docente, *Aprender → Esta semana* (`backend/app/study_plan.py`, sin IA): reparte los
módulos del temario, en orden y según sus apartados, entre las semanas que van del inicio del
semestre a la última entrega evaluable, y enseña qué toca ahora, lo atrasado (módulos de
semanas pasadas sin terminar o sin material), las entregas de los próximos 14 días, los
objetivos más flojos de lo ya visto y el repaso pendiente, con las horas que llevas.

### Biblioteca y tutor

Lo que subes para generar se guarda en la **biblioteca** de la asignatura (*Aprender →
Biblioteca*, `backend/app/materials.py`): el texto en la base de datos y el PDF en
`DATA_DIR/materials/`. Se puede volver a generar desde ella sin subir nada, cada tarjeta de
teoría guarda de qué material y página sale y su «Amplíalo» abre el PDF ahí. El **tutor**
(*Pregunta tus dudas*, `backend/app/tutor.py`) responde solo con esos materiales, citando
material, página y apartado; si no está en ellos, lo dice. Con las mismas barreras del
generador: no trabaja nada que parezca una actividad evaluable y, en asignaturas con la IA
prohibida, solo explica teoría y ejemplos resueltos.

### Inteligencia artificial

*Ajustes → Inteligencia artificial*: cada instalación pone la suya. La usan el generador, el
tutor, el plan docente, la carrera desde el plan de estudios y la bandeja. La app también
escribe en el idioma elegido en Ajustes.

| Proveedor | Qué pide |
|---|---|
| Claude Code | token de `claude setup-token` (tu suscripción, **solo para tu propia instalación**: Anthropic no permite usar el inicio de sesión de claude.ai ni los límites de una suscripción en productos para terceros) |
| Claude · clave de API | clave de console.anthropic.com (salida JSON estructurada, SDK oficial) |
| Gemini · clave de API | clave de aistudio.google.com (tiene nivel gratuito con límites) |
| OpenRouter | clave de openrouter.ai; el modelo como `proveedor/modelo` (`openrouter/auto` elige uno) |
| Ollama | URL del servidor y modelo: local y gratis |
| Compatible con OpenAI | URL `/v1`, modelo y clave si la pide (OpenRouter, LM Studio, vLLM…) |

La clave se guarda **cifrada** en `DATA_DIR/ai-key.enc` (clave de cifrado en
`CAMPUS_SECRET_KEY` o `DATA_DIR/secret.key`), fuera de la base de datos y de los backups, y la
API nunca la devuelve. Sin nada configurado se usa lo que traiga el servidor:
`CAMPUS_CLAUDE_TOKEN_FILE` / `CLAUDE_CODE_OAUTH_TOKEN` (Claude Code) o `ANTHROPIC_API_KEY`.

## Bandeja de la universidad

Un filtro del buzón universitario reenvía los avisos a una dirección propia; Cloudflare
Email Routing los entrega a un Worker ([`inbox-worker/`](inbox-worker/README.md), con su guía
de despliegue) que los guarda en KV. La app **va a buscarlos** cada 5 minutos con un token: solo
hay tráfico de salida y nada de fuera entra en la red. Nada inicia sesión en la cuenta de
la universidad.

Cada correo se clasifica con la IA configurada (el modelo «para la bandeja»), sin
herramientas: el correo entra como datos,
la salida se valida contra un esquema y contra tus asignaturas, y las fechas quedan como
propuestas. Aceptar una crea un **evento**, nunca una actividad evaluable. No se responde
ni resuelve nada del contenido académico.

| Variable | Para qué |
|---|---|
| `CAMPUS_INBOX_PULL_URL`, `CAMPUS_INBOX_PULL_TOKEN` / `_FILE` | Worker del que recoger los correos |
| `CAMPUS_INBOX_EXPORT_TOKEN` / `_FILE` | `GET /inbox/export?since_id=N`: copia a un repositorio local |
| `CAMPUS_INBOX_TOKEN` / `_FILE` | `POST /inbox/ingest`: entrada directa (opcional) |

Si pones la app detrás de un proxy con login, deja fuera solo `/inbox/*` y `/ical/*`: llevan su
propio token y sin él responden 404.

---

<a id="desarrollo"></a>
## 🛠️ Desarrollo

Requisitos: Python 3.12 y Node 22.

```sh
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080

# Frontend (otra terminal, desde la raíz)
npm install
npm run dev        # http://localhost:5173, proxea /api al backend
```

### Validar y tests

```sh
cd backend && pytest          # API, evaluación, generador, calendario, seguridad
npm test                      # librerías del frontend (vitest)
npm run i18n:check            # todo texto de la interfaz tiene traducción al inglés
npm run build                 # comprueba los tipos y genera dist/
```

Si cambias los modelos: `cd backend && alembic revision --autogenerate -m "…"`.

### Construir el escritorio

En el sistema de destino (PyInstaller no cruza de uno a otro), con Python 3.11+ y Node 22:

```sh
npm ci && npm run build
mkdir -p backend/desktop && cp -r dist backend/desktop/static && cp -r packs backend/desktop/packs
cd backend
python -m venv .venv-desktop
.venv-desktop/bin/pip install -r requirements-desktop.txt   # en Windows: .venv-desktop\Scripts\pip
.venv-desktop/bin/pyinstaller --noconfirm campus-pilot-desktop.spec
```

Sale `backend/dist/Campus Pilot.app` (macOS) o la carpeta `backend/dist/Campus Pilot/`
(Windows), que `packaging/campus-pilot.iss` convierte en instalador con Inno Setup 6.

### Stack

| Capa | Tecnología |
|------|------------|
| API | FastAPI · SQLAlchemy 2 · Alembic · SQLite |
| Interfaz | React 18 · TypeScript · Vite · KaTeX |
| IA | Proveedor configurable (`backend/app/ai.py`), siempre sin herramientas y con salida validada por esquema |
| Escritorio | PyInstaller + pywebview · Inno Setup (Windows) · `.dmg` (macOS) |
| Tareas | Planificador dentro del proceso: resumen ntfy, calendario iCal, bandeja, copia nocturna |

## App iOS antigua

La carpeta `Campus Pilot/` (SwiftUI) es la versión anterior, solo iOS. Su exportación JSON se
importa desde *Expediente → Importar y compartir*.

---

## Licencia

**Código disponible** bajo [PolyForm Noncommercial 1.0.0](LICENSE): puedes usarla, estudiarla,
modificarla y compartirla con fines **no comerciales**. Para cualquier uso comercial, contacta
con la autora.

## Comunidad

| | |
|---|---|
| Seguridad | [SECURITY.md](SECURITY.md) — avisos privados por GitHub |
| Tu universidad | ¿Has creado el módulo de tu titulación? Abre un PR con él en `packs/` |

© 2026 [Andrea Osma Rafael](https://andreaosma.com)
