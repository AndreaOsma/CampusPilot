# Bandeja de la universidad — Worker de Cloudflare

Recibe en una dirección tuya los correos que reenvía un filtro de tu buzón universitario, los
guarda en KV (30 días como máximo) y deja que tu Campus Pilot los recoja con un token
(`GET /pull`, `POST /ack`). Nada de fuera entra en tu red: solo hay tráfico de salida desde
donde corra la app. Nada inicia sesión en tu cuenta de la universidad.

- Solo admite remitentes de sobre de los dominios de `ALLOWED_FROM_DOMAINS`; el resto se rechaza.
- La verificación del reenvío de Gmail y lo que no se pueda guardar van a `FALLBACK_FORWARD`
  si la configuras; si no, se rechazan.

## Desplegar (una vez)

Necesitas un dominio en Cloudflare con Email Routing.

```sh
cd inbox-worker
npm ci
npx wrangler login
npx wrangler kv namespace create INBOX      # pega el id en wrangler.toml
openssl rand -hex 32 | tee /dev/tty | npx wrangler secret put PULL_TOKEN
npx wrangler deploy                         # da la URL https://campus-pilot-inbox.<cuenta>.workers.dev
```

Después:

1. **Email Routing** (tu dominio → Email → Routing rules): una dirección, p. ej.
   `bandeja@tu-dominio`, → *Send to a Worker* → `campus-pilot-inbox`.
2. **Campus Pilot**: `CAMPUS_INBOX_PULL_URL` = la URL del Worker y el mismo token en
   `CAMPUS_INBOX_PULL_TOKEN` (o en un fichero con `CAMPUS_INBOX_PULL_TOKEN_FILE`).
3. **Buzón de la universidad**: reenvío a esa dirección y un filtro con lo que quieras que
   llegue (p. ej. `from:(tu-universidad.edu)`).

## Tests

```sh
npm test
```
