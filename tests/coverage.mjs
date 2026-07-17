// Замер охвата разбора на реальной выборке: доля постов, где распознаны компания
// и должность, плюс примеры промахов. Запуск: node tests/coverage.mjs
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const { parseTgJob, extractSkills } = createRequire(import.meta.url)("../tgparse.js");
const posts = JSON.parse(readFileSync(new URL("../data/job_feed.json", import.meta.url)));

// Находка 4 (повторное ревью): цифра «навыки» должна отражать то, что реально
// видно на карточках в jobs.html, а не всё, что в принципе умеет найти
// extractSkills. Там чип навыков не рендерится для (1) постов, которые вообще
// не проходят фильтр вакансии looksLikeVacancy (реклама/меню канала/статьи —
// такой пост не становится карточкой) и (2) постов-дайджестов (isDigest по тегу
// «Дайджест» — cardTg сознательно не показывает чипы, потому что навыки в
// тексте перемешаны из разных вакансий). Чтобы цифра не расходилась с
// продакшеном при правках фильтра в jobs.html, оба условия не продублированы
// руками, а вырезаны прямо из исходника jobs.html — единый источник правды.
const jobsHtml = readFileSync(new URL("../jobs.html", import.meta.url), "utf8");
function cut(re, label) {
  const m = jobsHtml.match(re);
  if (!m) throw new Error(`coverage.mjs: не нашёл в jobs.html «${label}» — jobs.html изменился, обнови регэксп извлечения`);
  return m[0];
}
const looksLikeVacancy = new Function(`
  ${cut(/const G_ROLE\s*=\s*\[[^\]]*\];/u, "G_ROLE")}
  ${cut(/const G_FMT\s*=\s*\[[^\]]*\];/u, "G_FMT")}
  ${cut(/const G_GRADE\s*=\s*\[[^\]]*\];/u, "G_GRADE")}
  ${cut(/const G_EMPLOY\s*=\s*\[[^\]]*\];/u, "G_EMPLOY")}
  ${cut(/const VAC_RE\s*=\s*\/.*\/[a-z]*;/u, "VAC_RE")}
  ${cut(/const ADV_RE\s*=\s*\/.*\/[a-z]*;/u, "ADV_RE")}
  ${cut(/const STRUCT_VAC\s*=\s*\/.*\/[a-z]*;/u, "STRUCT_VAC")}
  ${cut(/const NAV_RE\s*=\s*\/.*\/[a-z]*;/u, "NAV_RE")}
  ${cut(/const CITY_RE\s*=\s*\/.*\/[a-z]*;/u, "CITY_RE")}
  const ROLE_SET = new Set(G_ROLE);
  const CORROB_SET = new Set([...G_GRADE, ...G_FMT, ...G_EMPLOY, "З/п указана"]);
  ${cut(/function looksLikeVacancy\(p\)\{[\s\S]*?\n\}/u, "looksLikeVacancy")}
  return looksLikeVacancy;
`)();

let co = 0, ti = 0, sk = 0, skCards = 0;
const coMisses = [];
const tiMisses = [];
for (const p of posts) {
  const r = parseTgJob(p.text, p.tags);
  if (r.company) co++;
  if (r.title) ti++;
  // Знаменатель для навыков — не все 500 постов, а только те, что становятся
  // карточкой (looksLikeVacancy); числитель — только среди них и не для
  // дайджестов (isDigest), как в cardTg.
  if (looksLikeVacancy(p)) {
    skCards++;
    const isDigest = (p.tags || []).includes("Дайджест");
    // company передаём вторым аргументом (Задача 6) — как и в jobs.html, чтобы
    // метрика отражала реальное поведение продакшена (без шума вида «Яндекс
    // Go» → навык go).
    if (!isDigest && extractSkills(p.text, r.company).length) sk++;
  }
  if (!r.company && coMisses.length < 15) coMisses.push(p.text.split("\n")[0].slice(0, 80));
  // Промахи по должности — та же логика, что и у компании: первая строка
  // поста как ориентир, где искать причину (нужна для итерации по ROLE_HINT).
  if (!r.title && tiMisses.length < 15) tiMisses.push(p.text.split("\n")[0].slice(0, 80));
}
const pct = (n, d) => `${((n / d) * 100).toFixed(1)}%`;
console.log(`постов: ${posts.length}`);
console.log(`компания: ${co} (${pct(co, posts.length)})`);
console.log(`должность: ${ti} (${pct(ti, posts.length)})`);
console.log(`навыки: ${sk}/${skCards} (${pct(sk, skCards)}) — среди карточек-вакансий (looksLikeVacancy), без дайджестов`);
console.log("\nбез компании (первые 15):");
for (const m of coMisses) console.log("  ·", m);
console.log("\nбез должности (первые 15):");
for (const m of tiMisses) console.log("  ·", m);
