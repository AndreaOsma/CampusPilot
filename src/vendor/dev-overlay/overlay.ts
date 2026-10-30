/* GENERADO desde dev/lib/dev-overlay (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
/**
 * Modo dev de ágora: seleccionar un elemento de esta app (como en un editor) para pedir un cambio.
 *
 * La app va dentro de un iframe de ágora (otro subdominio), así que ágora no puede tocar su DOM:
 * este script, que cada app importa una vez en main.tsx, hace la selección y le manda a ágora la
 * descripción del elemento por postMessage. Seguridad:
 * - Solo obedece a mensajes de AGORA_ORIGIN y solo si la app está dentro de un iframe.
 * - Mientras se selecciona, los clics no llegan a la app (no se dispara ninguna acción).
 * - Nunca manda valores de campos (ni contraseñas ni lo escrito), ni scripts: solo estructura y texto
 *   visible, recortados.
 *
 * Protocolo (todo con { type: "agora-dev" }):
 *   ágora → app: { action: "start" | "stop" | "grow" | "ping" }
 *   app → ágora: { event: "ready", version } al cargar · { event: "pick", element, canGrow } · { event: "cancel" }
 *
 * Funciona igual con ratón y con el dedo: en táctil se puede hacer scroll mientras eliges (solo un
 * toque sin arrastrar elige), y lo elegido se queda marcado hasta que se envía o se cancela.
 */
export const AGORA_ORIGIN = "https://agora.andreaosma.com";

export type PickedElement = {
  selector: string;
  tag: string;
  role: string;
  label: string;
  text: string;
  html: string;
  heading: string;
  page: string;
  title: string;
  rect: { x: number; y: number; w: number; h: number; vw: number; vh: number };
};

const clip = (s: string | null | undefined, n: number) => {
  const t = (s ?? "").replace(/\s+/g, " ").trim();
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
};

function cssPath(el: Element): string {
  const parts: string[] = [];
  for (let e: Element | null = el, depth = 0; e && e !== document.body && depth < 8; e = e.parentElement, depth++) {
    if (e.id && /^[A-Za-z][\w-]*$/.test(e.id) && document.querySelectorAll(`#${e.id}`).length === 1) {
      parts.unshift(`#${e.id}`);
      break;
    }
    let part = e.tagName.toLowerCase();
    const cls = [...e.classList].filter((c) => /^[A-Za-z][\w-]*$/.test(c)).slice(0, 2);
    if (cls.length) part += "." + cls.join(".");
    const parent = e.parentElement;
    if (parent) {
      const same = [...parent.children].filter((c) => c.tagName === e!.tagName);
      if (same.length > 1) part += `:nth-of-type(${same.indexOf(e) + 1})`;
    }
    parts.unshift(part);
  }
  return parts.join(" > ");
}

/** HTML del elemento sin valores de campos, sin scripts y recortado. */
function safeHtml(el: Element): string {
  const copy = el.cloneNode(true) as Element;
  copy.querySelectorAll("script, style, svg, canvas, iframe").forEach((n) => n.remove());
  for (const n of [copy, ...copy.querySelectorAll("*")]) {
    for (const a of [...n.attributes]) {
      if (a.name === "value" || a.name.startsWith("on") || a.name === "style" || (a.name === "src" && a.value.startsWith("data:"))) n.removeAttribute(a.name);
    }
    if (n instanceof HTMLInputElement || n instanceof HTMLTextAreaElement) n.textContent = "";
  }
  return clip(copy.outerHTML, 1500);
}

function nearestHeading(el: Element): string {
  for (let e: Element | null = el; e; e = e.parentElement) {
    const h = e.querySelector?.(":scope > h1, :scope > h2, :scope > h3, :scope > header h1, :scope > header h2");
    if (h && h !== el) return clip(h.textContent, 120);
  }
  return clip(document.querySelector("h1")?.textContent, 120);
}

function describe(el: Element): PickedElement {
  const r = el.getBoundingClientRect();
  const isField = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement;
  return {
    selector: cssPath(el),
    tag: el.tagName.toLowerCase() + (el instanceof HTMLInputElement ? `[type=${el.type}]` : ""),
    role: el.getAttribute("role") ?? "",
    label: clip(el.getAttribute("aria-label") ?? el.getAttribute("title") ?? el.getAttribute("alt") ?? el.getAttribute("placeholder") ?? "", 160),
    text: isField ? "" : clip((el as HTMLElement).innerText ?? el.textContent, 300),
    html: safeHtml(el),
    heading: nearestHeading(el),
    page: location.pathname + location.hash,
    title: clip(document.title, 120),
    rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), vw: innerWidth, vh: innerHeight },
  };
}

let active = false; // eligiendo
let hoverBox: HTMLDivElement | null = null; // lo que hay bajo el ratón/dedo
let selBox: HTMLDivElement | null = null; // lo elegido: se queda marcado mientras escribes el cambio
let current: Element | null = null;
let selected: Element | null = null;
let down: { x: number; y: number; type: string } | null = null;
const MOVE_PX = 10; // más que esto entre tocar y soltar = estabas haciendo scroll, no eligiendo

function post(msg: Record<string, unknown>) {
  window.parent.postMessage({ type: "agora-dev", ...msg }, AGORA_ORIGIN);
}

function makeBox(fill: string, border: string, shade: boolean): HTMLDivElement {
  const b = document.createElement("div");
  b.setAttribute("aria-hidden", "true");
  b.dataset.agoraDev = "";
  Object.assign(b.style, {
    position: "fixed", zIndex: "2147483647", pointerEvents: "none", border: `2px solid ${border}`, borderRadius: "6px",
    background: fill, boxShadow: shade ? "0 0 0 9999px rgba(0,0,0,0.18)" : "none", display: "none", transition: "all 60ms",
  });
  document.body.appendChild(b);
  return b;
}

function place(b: HTMLDivElement | null, el: Element | null) {
  if (!b) return;
  if (!el || !el.isConnected) { b.style.display = "none"; return; }
  const r = el.getBoundingClientRect();
  Object.assign(b.style, { display: "block", left: `${r.left - 2}px`, top: `${r.top - 2}px`, width: `${r.width + 4}px`, height: `${r.height + 4}px` });
}

const isOurs = (el: Element | null) => !!el && el instanceof HTMLElement && "agoraDev" in el.dataset;
const at = (x: number, y: number) => {
  const el = document.elementFromPoint(x, y);
  return el && !isOurs(el) && el !== document.documentElement && el !== document.body ? el : null;
};

function select(el: Element) {
  selected = el;
  selBox ??= makeBox("rgba(124, 58, 237, 0.10)", "#7c3aed", false);
  place(selBox, el);
  post({ event: "pick", element: describe(el), canGrow: !!el.parentElement && el.parentElement !== document.body });
}

// Durante la selección nada llega a la app: ni clics, ni envíos de formularios, ni el foco en
// campos (que abriría el teclado en el móvil). El scroll sí, para llegar a lo que quieres cambiar.
const block = (e: Event) => { e.preventDefault(); e.stopPropagation(); };
const onDown = (e: PointerEvent) => {
  down = { x: e.clientX, y: e.clientY, type: e.pointerType };
  current = at(e.clientX, e.clientY);
  place(hoverBox, current);
  if (e.pointerType === "mouse") block(e); // en táctil, bloquearlo impediría el scroll
  else e.stopPropagation();
};
const onMove = (e: PointerEvent) => {
  if (e.pointerType === "mouse" || !down) { current = at(e.clientX, e.clientY); place(hoverBox, current); }
};
const onUp = (e: PointerEvent) => {
  e.stopPropagation();
  if (e.pointerType === "mouse") e.preventDefault();
  const d = down; down = null;
  if (!d || Math.hypot(e.clientX - d.x, e.clientY - d.y) > MOVE_PX) return; // era un scroll
  const el = at(e.clientX, e.clientY) ?? current;
  if (!el) return;
  select(el);
  stopPicking();
};
// En el móvil, sin esto el toque acabaría en un clic sintético (y en el foco de un campo).
const onTouchEnd = (e: TouchEvent) => { e.stopPropagation(); if (e.cancelable) e.preventDefault(); };
const onKey = (e: KeyboardEvent) => {
  if (e.key === "Escape") { block(e); post({ event: "cancel" }); stop(); }
};
const follow = () => { place(hoverBox, current); place(selBox, selected); }; // scroll y giros de pantalla

const BLOCKED = ["click", "mousedown", "mouseup", "dblclick", "contextmenu", "auxclick", "submit", "focusin"];

function start() {
  if (active) return;
  active = true;
  hoverBox ??= makeBox("rgba(124, 58, 237, 0.14)", "#a78bfa", true);
  document.documentElement.style.cursor = "crosshair";
  window.addEventListener("pointerdown", onDown, true);
  window.addEventListener("pointermove", onMove, true);
  window.addEventListener("pointerup", onUp, true);
  window.addEventListener("touchend", onTouchEnd, { capture: true, passive: false });
  for (const t of BLOCKED) window.addEventListener(t, block, true);
  window.addEventListener("keydown", onKey, true);
}

function stopPicking() {
  if (!active) return;
  active = false;
  window.removeEventListener("pointerdown", onDown, true);
  window.removeEventListener("pointermove", onMove, true);
  window.removeEventListener("pointerup", onUp, true);
  // El toque que eligió aún termina (touchend, clic sintético): se bloquea un instante más.
  setTimeout(() => {
    if (active) return;
    window.removeEventListener("touchend", onTouchEnd, true);
    for (const t of BLOCKED) window.removeEventListener(t, block, true);
  }, 400);
  window.removeEventListener("keydown", onKey, true);
  hoverBox?.remove(); hoverBox = null; current = null; down = null;
  document.documentElement.style.cursor = "";
}

/** Fuera del modo dev del todo: nada marcado. */
function stop() {
  stopPicking();
  selBox?.remove(); selBox = null; selected = null;
}

/** Ampliar la selección al contenedor (tocaste el texto y querías el botón entero). */
function grow() {
  const p = selected?.parentElement;
  if (p && p !== document.body && p !== document.documentElement) select(p);
}

/** Engancha el modo dev (no hace nada fuera de un iframe de ágora). Llamar una vez al arrancar. */
export function installDevOverlay(): void {
  if (typeof window === "undefined" || window.parent === window) return;
  window.addEventListener("message", (e: MessageEvent) => {
    if (e.origin !== AGORA_ORIGIN || e.source !== window.parent) return;
    const d = e.data as { type?: string; action?: string } | null;
    if (!d || d.type !== "agora-dev") return;
    if (d.action === "start") { selBox?.remove(); selBox = null; selected = null; start(); }
    else if (d.action === "stop") stop();
    else if (d.action === "grow") grow();
    else if (d.action === "ping") post({ event: "ready" });
  });
  window.addEventListener("scroll", follow, { capture: true, passive: true });
  window.addEventListener("resize", follow, { passive: true });
  post({ event: "ready", version: 2 });
}

installDevOverlay();
