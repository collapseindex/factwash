const gate = require("./gate.js");
const cases = require("./expected.json");
let bad = [];
for (const c of cases) {
  const r = gate.check(c.src, c.mem);
  const flags = [...new Set(r.flags.filter(f => f.severity === "fail" || f.severity === "warn").map(f => f.name))].sort();
  if (r.verdict !== c.verdict || JSON.stringify(flags) !== JSON.stringify(c.flags)) {
    bad.push({ tag: c.tag, py: [c.verdict, c.flags], js: [r.verdict, flags], mem: c.mem.slice(0, 70).replace(/\n/g, " ") });
  }
}
console.log(`compared ${cases.length} pairs; ${bad.length} disagreement(s)`);
bad.slice(0, 10).forEach(b =>
  console.log("  " + b.tag + "\n    PY " + JSON.stringify(b.py) + "\n    JS " + JSON.stringify(b.js) + "\n    mem: " + b.mem));
