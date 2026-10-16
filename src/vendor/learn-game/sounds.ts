/* GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs */
/** Sonidos del juego sintetizados con Web Audio (sin ficheros). Silenciables. */
let ctx: AudioContext | null = null;

function audio(): AudioContext | null {
  try {
    if (!ctx) {
      const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return null;
      ctx = new Ctor();
    }
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

function tone(freq: number, start: number, dur: number, type: OscillatorType = "sine", gain = 0.12) {
  const a = audio();
  if (!a) return;
  const t0 = a.currentTime + start;
  const osc = a.createOscillator();
  const g = a.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(gain, t0 + 0.015);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(g).connect(a.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.02);
}

export type Sound = "correct" | "wrong" | "complete" | "combo" | "tap" | "chest";

export function play(sound: Sound, enabled = true) {
  if (!enabled) return;
  switch (sound) {
    case "correct":
      tone(660, 0, 0.12, "triangle");
      tone(990, 0.09, 0.18, "triangle");
      break;
    case "wrong":
      tone(220, 0, 0.18, "sawtooth", 0.06);
      tone(180, 0.12, 0.22, "sawtooth", 0.05);
      break;
    case "combo":
      [784, 988, 1175].forEach((f, i) => tone(f, i * 0.07, 0.14, "triangle", 0.09));
      break;
    case "complete":
      [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.11, 0.26, "triangle"));
      break;
    case "chest":
      [880, 1109, 1319, 1760].forEach((f, i) => tone(f, i * 0.06, 0.2, "sine", 0.1));
      break;
    case "tap":
      tone(520, 0, 0.05, "sine", 0.04);
      break;
  }
}

export function vibrate(pattern: number | number[]) {
  try {
    navigator.vibrate?.(pattern);
  } catch {
    /* sin vibración */
  }
}
