// Comprueba que cada t("…") del frontend tiene traducción en src/i18n/en.json. Uso: npm run i18n:check
const path = require("path"), fs = require("fs");
const root = path.resolve(__dirname, "../..");
const ts = require(path.join(root, "node_modules/typescript"));
const keys = new Set();
const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? walk(path.join(d, e.name)) : /\.(tsx?|)$/.test(e.name) && !e.name.endsWith(".test.ts") ? [path.join(d, e.name)] : []);
for (const file of walk(path.join(root, "src"))) {
  if (!/\.tsx?$/.test(file)) continue;
  const sf = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const visit = (n) => {
    if (ts.isCallExpression(n) && ["t", "tx", "translated", "translatedList"].includes(n.expression.getText(sf)) && n.arguments[0]) {
      const a = n.arguments[0];
      if (ts.isStringLiteral(a) || ts.isNoSubstitutionTemplateLiteral(a)) keys.add(a.text);
      if (ts.isObjectLiteralExpression(a)) for (const p of a.properties) if (p.initializer && ts.isStringLiteral(p.initializer)) keys.add(p.initializer.text);
      if (ts.isArrayLiteralExpression(a)) for (const e of a.elements) if (ts.isStringLiteral(e)) keys.add(e.text);
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
}
["semestre","sem.","trimestre","trim.","periodo","per.","curso"].forEach((k) => keys.add(k));
const out = [...keys].sort((a, b) => a.localeCompare(b, "es"));
const en = JSON.parse(fs.readFileSync(path.join(root, "src/i18n/en.json"), "utf8"));
const missing = out.filter((k) => !(k in en) && !/^[\d\s{}.,:;·%+-]*$/.test(k));
if (missing.length) {
  console.error(`Sin traducir al inglés (${missing.length}) — añádelas a src/i18n/en.json:`);
  for (const k of missing) console.error("  " + JSON.stringify(k));
  process.exit(1);
}
console.log(`i18n: ${out.length} textos, todos traducidos`);
