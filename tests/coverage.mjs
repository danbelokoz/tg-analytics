// Замер охвата разбора на реальной выборке: доля постов, где распознаны компания
// и должность, плюс примеры промахов. Запуск: node tests/coverage.mjs
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const { parseTgJob, extractSkills } = createRequire(import.meta.url)("../tgparse.js");
const posts = JSON.parse(readFileSync(new URL("../data/job_feed.json", import.meta.url)));

let co = 0, ti = 0, sk = 0;
const coMisses = [];
const tiMisses = [];
for (const p of posts) {
  const r = parseTgJob(p.text, p.tags);
  if (r.company) co++;
  if (r.title) ti++;
  if (extractSkills(p.text).length) sk++;
  if (!r.company && coMisses.length < 15) coMisses.push(p.text.split("\n")[0].slice(0, 80));
  // Промахи по должности — та же логика, что и у компании: первая строка
  // поста как ориентир, где искать причину (нужна для итерации по ROLE_HINT).
  if (!r.title && tiMisses.length < 15) tiMisses.push(p.text.split("\n")[0].slice(0, 80));
}
const pct = n => `${((n / posts.length) * 100).toFixed(1)}%`;
console.log(`постов: ${posts.length}`);
console.log(`компания: ${co} (${pct(co)})`);
console.log(`должность: ${ti} (${pct(ti)})`);
console.log(`навыки: ${sk} (${pct(sk)})`);
console.log("\nбез компании (первые 15):");
for (const m of coMisses) console.log("  ·", m);
console.log("\nбез должности (первые 15):");
for (const m of tiMisses) console.log("  ·", m);
