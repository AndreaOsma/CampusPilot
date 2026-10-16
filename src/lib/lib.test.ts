import { describe, expect, it } from "vitest";
import { addDays, daysBetween, fmtMinutes, numOrNull, obsidianUrl, relDays, weekStart } from "./format";
import { letterOf, letterPresets, nextTerm, offeredOptions, offeredShort, planTermOptions, termClash, termLabel, termOf } from "./rules";
import { splitMath } from "./math";
import { speakable } from "./speech";
import { setLocale, t } from "../i18n";

setLocale("es");

describe("fechas", () => {
  it("weekStart devuelve el lunes", () => {
    expect(weekStart("2026-10-09")).toBe("2026-10-05");
    expect(weekStart("2026-10-11")).toBe("2026-10-05");
    expect(weekStart("2026-10-05")).toBe("2026-10-05");
  });
  it("addDays y daysBetween cruzan meses y el cambio de hora", () => {
    expect(addDays("2026-10-30", 3)).toBe("2026-11-02");
    expect(daysBetween("2026-10-24", "2026-10-26")).toBe(2);
  });
  it("relDays", () => {
    expect(relDays("2026-10-09", "2026-10-09")).toBe("hoy");
    expect(relDays("2026-10-10", "2026-10-09")).toBe("mañana");
    expect(relDays("2026-10-14", "2026-10-09")).toBe("en 5 días");
    expect(relDays("2026-10-07", "2026-10-09")).toBe("hace 2 días");
  });
});

describe("formatos", () => {
  it("minutos", () => {
    expect(fmtMinutes(45)).toBe("45 min");
    expect(fmtMinutes(120)).toBe("2 h");
    expect(fmtMinutes(95)).toBe("1 h 35 min");
  });
  it("numOrNull acepta coma decimal", () => {
    expect(numOrNull("7,5")).toBe(7.5);
    expect(numOrNull("")).toBeNull();
    expect(numOrNull("abc")).toBeNull();
  });
  it("obsidianUrl codifica vault y ruta", () => {
    expect(obsidianUrl("Ing Teleco", "mates/apuntes")).toBe("obsidian://open?vault=Ing%20Teleco&file=mates%2Fapuntes");
  });
});

describe("splitMath", () => {
  it("separa fórmulas inline", () => {
    expect(splitMath("¿Qué es $i$ y qué cumple?")).toEqual([
      { math: false, text: "¿Qué es " },
      { math: true, text: "i" },
      { math: false, text: " y qué cumple?" },
    ]);
  });
  it("dólar escapado y sin cerrar quedan como texto", () => {
    expect(splitMath("cuesta 5\\$ y $x")).toEqual([{ math: false, text: "cuesta 5$ y $x" }]);
  });
});

describe("semestres personales", () => {
  it("deduce el semestre de una fecha", () => {
    expect(termOf("2026-10-13")).toBe("2026S1");
    expect(termOf("2027-01-20")).toBe("2026S1");
    expect(termOf("2027-03-01")).toBe("2026S2");
    expect(termOf("2027-09-01")).toBe("2027S1");
  });
  it("avanza y retrocede semestres", () => {
    expect(nextTerm("2026S1")).toBe("2026S2");
    expect(nextTerm("2026S2")).toBe("2027S1");
    expect(nextTerm("2026S1", -1)).toBe("2025S2");
    expect(nextTerm("2026S1", 3)).toBe("2027S2");
  });
  it("etiqueta y avisa de choques", () => {
    expect(termLabel("2026S2", true)).toBe("2026/27 · 2.º sem.");
    expect(termClash("s1", "2026S2")).toBe(true);
    expect(termClash("s1", "2026S1")).toBe(false);
    expect(termClash("both", "2026S2")).toBe(false);
    expect(termClash("s2", null)).toBe(false);
  });
  it("ofrece semestres ordenados e incluye el elegido", () => {
    const opts = planTermOptions("2040S1", "2026-10-13");
    expect(opts[0]).toBe("2025S1");
    expect(opts).toContain("2040S1");
    expect([...opts].sort()).toEqual(opts);
  });
});

describe("otros calendarios", () => {
  it("trimestres desde septiembre", () => {
    expect(termOf("2026-10-01", "trimesters")).toBe("2026T1");
    expect(termOf("2027-02-01", "trimesters")).toBe("2026T2");
    expect(termOf("2027-05-01", "trimesters")).toBe("2026T3");
    expect(nextTerm("2026T3")).toBe("2027T1");
    expect(termLabel("2026T2", true)).toBe("2026/27 · 2.º trim.");
  });
  it("curso que empieza en marzo (hemisferio sur) y anual", () => {
    expect(termOf("2026-02-10", "semesters", 3)).toBe("2025S2");
    expect(termOf("2026-04-10", "semesters", 3)).toBe("2026S1");
    expect(termOf("2026-10-10", "annual")).toBe("2026A");
    expect(nextTerm("2026A")).toBe("2027A");
    expect(termLabel("2026A")).toBe("2026/27");
  });
  it("periodos ofertados y choques", () => {
    expect(Object.keys(offeredOptions("trimesters"))).toEqual(["both", "t1", "t2", "t3"]);
    expect(offeredShort("t2")).toBe("solo 2.º trim.");
    expect(termClash("t1", "2026T2")).toBe(true);
    expect(termClash("s1", "2026T2")).toBe(false);
  });
});

describe("idioma", () => {
  it("traduce al inglés con variables y vuelve al español", () => {
    setLocale("en");
    expect(termLabel("2026S2", true)).toBe("2026/27 · 2nd sem.");
    expect(offeredShort("t1")).toBe("only 1st term");
    expect(t("en {n} días", { n: 3 })).toBe("in 3 days");
    expect(t("texto sin traducir")).toBe("texto sin traducir");
    setLocale("es");
    expect(termLabel("2026S2", true)).toBe("2026/27 · 2.º sem.");
  });
});

describe("speakable", () => {
  it("lee fórmulas y quita el Markdown", () => {
    setLocale("es");
    expect(speakable("- **Módulo**: $|z| = \\sqrt{a^2 + b^2}$")).toBe("Módulo: z = raíz de a al cuadrado + b al cuadrado");
    expect(speakable("$\\frac{1}{2}$ y ```code```")).toBe("1 entre 2 y");
  });
});

describe("letras", () => {
  it("da la letra de una nota y escala los presets", () => {
    const ec = letterPresets(10)[0].letters;
    const rules = { letters: ec } as Parameters<typeof letterOf>[1];
    expect(letterOf(9.2, rules)).toBe("A");
    expect(letterOf(5, rules)).toBe("C+");
    expect(letterOf(0, rules)).toBe("D");
    expect(letterOf(null, rules)).toBeNull();
    expect(letterOf(7, { letters: [] } as unknown as Parameters<typeof letterOf>[1])).toBeNull();
    expect(letterPresets(20)[0].letters[0]).toEqual({ label: "A", min: 18, value: 19 });
  });
});
