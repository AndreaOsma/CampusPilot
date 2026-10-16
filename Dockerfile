# Campus Pilot — imagen única: frontend (Vite) + API (FastAPI) + SQLite, puerto 8080.
#
#   docker build -t campus-pilot .
#   docker run -p 8080:8080 -v campus_data:/data campus-pilot
#
# Todos los datos viven en /data (monta un volumen ahí).

# Stage 1: build frontend
FROM node:22-alpine AS build-frontend
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Stage 2: Claude Code CLI (generador de lecciones). Es un binario nativo autónomo: solo
# se copia el ejecutable, sin Node en la imagen final. Versión fijada.
FROM node:22-slim AS claude-cli
ARG CLAUDE_CODE_VERSION=2.1.296
RUN npm install -g --no-audit --no-fund "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && cp "$(npm root -g)/@anthropic-ai/claude-code/bin/claude.exe" /claude \
 && /claude --version

# Stage 3: runtime
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Campus Pilot" \
      org.opencontainers.image.description="Carrera, semestre, estudio y trayectoria universitaria, con módulos de estudios instalables" \
      org.opencontainers.image.authors="Andrea Osma Rafael" \
      org.opencontainers.image.licenses="PolyForm-Noncommercial-1.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Paquetes del sistema al día (parches de seguridad de Debian) — la imagen base
# no siempre trae las últimas revisiones de util-linux/bsdutils/etc. El daemon Docker de
# la CI es compartido entre apps: sin invalidar esta capa reutilizaría un upgrade viejo y
# Trivy bloquearía por CVEs ya parcheados. La CI pasa la fecha del día como APT_CACHEBUST.
ARG APT_CACHEBUST=2026-10-09
RUN echo "apt cachebust ${APT_CACHEBUST}" && apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Solo dependencias de ejecución (pytest y compañía van en requirements-dev.txt).
COPY backend/requirements.txt .
# pip de la imagen base (25.0.1) trae CVE corregidos en 26.2: se actualiza a una versión fijada.
# Después se desinstala: no hace falta en runtime y sus dependencias vendorizadas
# (msgpack, urllib3…) acumulan CVE que Trivy marca en la imagen.
RUN pip install "pip==26.2.1" && pip install -r requirements.txt && pip uninstall -y pip

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .
COPY backend/startup.sh .
COPY packs ./packs
RUN chmod +x startup.sh

COPY --from=build-frontend /app/dist ./static
COPY --from=claude-cli /claude /usr/local/bin/claude

ENV CAMPUS_STATIC_DIR=/app/static \
    CAMPUS_DATA_DIR=/data \
    CAMPUS_PACKS_DIR=/app/packs \
    DATABASE_URL=sqlite:////data/campus.db \
    CAMPUS_TZ=Europe/Madrid \
    PORT=8080

# Usuario sin privilegios para quien autoaloje (deploy/docker-compose.yml lo usa con
# `user: 10001:10001`). La imagen sigue arrancando como root por defecto para no romper
# instalaciones existentes cuyo /data es de root.
RUN useradd --system --uid 10001 --home-dir /data --no-create-home campus \
    && mkdir -p /data && chown 10001:10001 /data

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')" || exit 1

CMD ["./startup.sh"]
