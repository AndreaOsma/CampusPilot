// Bandeja de la universidad — Worker de Cloudflare para Campus Pilot (ver README.md).
//
// email(): Email Routing entrega aquí lo que llega a tu dirección de la bandeja (reenviado por
//   un filtro del buzón universitario). Se parsea y se guarda en KV, 30 días como mucho.
// fetch(): tu Campus Pilot recoge (GET /pull) y confirma (POST /ack) con un token. Así nada
//   de fuera tiene que entrar en tu red: solo hay tráfico de salida desde tu servidor.
import PostalMime from "postal-mime";

const PREFIX = "msg:";
const TTL_SECONDS = 60 * 60 * 24 * 30;
const MAX_RAW_BYTES = 2_000_000;
const MAX_TEXT = 200_000;
const MAX_PULL = 50;

function envelopeDomain(address) {
  const at = String(address || "").toLowerCase().lastIndexOf("@");
  return at >= 0 ? String(address).toLowerCase().slice(at + 1).replace(/>$/, "") : "";
}

export function isAllowed(envelopeFrom, allowedDomains) {
  const domain = envelopeDomain(envelopeFrom);
  const allowed = String(allowedDomains || "")
    .toLowerCase()
    .split(",")
    .map((d) => d.trim())
    .filter(Boolean);
  return allowed.some((d) => domain === d || domain.endsWith(`.${d}`));
}

export function isForwardingVerification(envelopeFrom) {
  return String(envelopeFrom || "").toLowerCase().includes("forwarding-noreply@google.com");
}

export function toItem(parsed, envelope) {
  const from = parsed.from?.address ? `${parsed.from.name ? `${parsed.from.name} ` : ""}<${parsed.from.address}>` : envelope.from;
  const text = String(parsed.text || "").slice(0, MAX_TEXT);
  return {
    message_id: parsed.messageId || envelope.messageId || `generated-${crypto.randomUUID()}`,
    sender: from,
    recipient: envelope.to,
    subject: String(parsed.subject || "").slice(0, 500),
    date: parsed.date || new Date().toISOString(),
    text,
    html: text ? undefined : String(parsed.html || "").slice(0, MAX_TEXT),
  };
}

async function safeEqual(a, b) {
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([crypto.subtle.digest("SHA-256", enc.encode(a)), crypto.subtle.digest("SHA-256", enc.encode(b))]);
  return crypto.subtle.timingSafeEqual(ha, hb);
}

async function authorized(request, env) {
  const header = request.headers.get("authorization") || "";
  const given = header.toLowerCase().startsWith("bearer ") ? header.slice(7).trim() : "";
  return Boolean(env.PULL_TOKEN && given) && (await safeEqual(given, env.PULL_TOKEN));
}

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });

// Sin FALLBACK_FORWARD configurado no hay a dónde reenviar: se rechaza (el remitente recibe
// el aviso) en vez de perder el correo en silencio.
async function fallback(message, env, reason) {
  if (env.FALLBACK_FORWARD) await message.forward(env.FALLBACK_FORWARD);
  else message.setReject(reason);
}

export default {
  async email(message, env) {
    if (isForwardingVerification(message.from)) {
      // Código de verificación del reenvío de Gmail: a la bandeja de siempre.
      await fallback(message, env, "Configura FALLBACK_FORWARD para recibir la verificación del reenvío");
      return;
    }
    if (!isAllowed(message.from, env.ALLOWED_FROM_DOMAINS)) {
      message.setReject("Esta dirección solo acepta reenvíos del buzón universitario");
      return;
    }
    if (message.rawSize > MAX_RAW_BYTES) {
      await fallback(message, env, "Correo demasiado grande para la bandeja");
      return;
    }
    try {
      const raw = await new Response(message.raw).arrayBuffer();
      const parsed = await PostalMime.parse(raw);
      const item = toItem(parsed, { from: message.from, to: message.to, messageId: message.headers.get("message-id") });
      const key = `${PREFIX}${Date.now()}:${crypto.randomUUID()}`;
      await env.INBOX.put(key, JSON.stringify(item), { expirationTtl: TTL_SECONDS });
    } catch (err) {
      console.error("No se pudo guardar el correo; se reenvía a la bandeja de siempre", err);
      await fallback(message, env, "No se pudo guardar el correo");
    }
  },

  async fetch(request, env) {
    if (!(await authorized(request, env))) return json({ error: "unauthorized" }, 401);
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/pull") {
      const limit = Math.min(Math.max(Number(url.searchParams.get("limit")) || 20, 1), MAX_PULL);
      const listed = await env.INBOX.list({ prefix: PREFIX, limit });
      const items = [];
      for (const { name } of listed.keys) {
        const value = await env.INBOX.get(name);
        if (value) items.push({ key: name, message: JSON.parse(value) });
      }
      return json({ items });
    }
    if (request.method === "POST" && url.pathname === "/ack") {
      const body = await request.json().catch(() => ({}));
      const keys = Array.isArray(body.keys) ? body.keys.filter((k) => typeof k === "string" && k.startsWith(PREFIX)).slice(0, MAX_PULL * 2) : [];
      await Promise.all(keys.map((k) => env.INBOX.delete(k)));
      return json({ deleted: keys.length });
    }
    return json({ error: "not found" }, 404);
  },
};
