#!/bin/sh
set -e

PORT="${PORT:-8080}"
# /data lo crea Docker como root (bind mount): dárselo al usuario campus y arrancar ya sin privilegios.
if [ "$(id -u)" = "0" ]; then
  G=$(id -g campus)  # su grupo de sesión (useradd --system sin --user-group no crea «campus»)
  [ -d /data ] && chown -R campus:"$G" /data
  # Secretos montados de agenix (root 0400): copia dentro del contenedor que solo lee el usuario campus,
  # y las variables que apuntaban a /run/secrets/… pasan a la copia.
  if [ -d /run/secrets ]; then
    install -d -o campus -g "$G" -m 0500 /run/app-secrets
    for f in /run/secrets/*; do [ -f "$f" ] && install -o campus -g "$G" -m 0400 "$f" /run/app-secrets/; done
    for v in $(env | sed -n 's|^\([A-Za-z_][A-Za-z0-9_]*\)=/run/secrets/.*|\1|p'); do
      eval "export $v=\"/run/app-secrets/\${$v#/run/secrets/}\""
    done
  fi
  exec setpriv --reuid=campus --regid="$G" --init-groups --no-new-privs uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
