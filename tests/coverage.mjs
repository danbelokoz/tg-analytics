// Замер охвата разбора на реальной выборке: доля постов, где распознаны компания
// и должность, плюс примеры промахов. Запуск: node tests/coverage.mjs
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const { parseTgJob, extractSkills, isDigestPost, isResumePost, isEasyMoneyPost } = createRequire(import.meta.url)("../tgparse.js");
const posts = JSON.parse(readFileSync(new URL("../data/job_feed.json", import.meta.url)));

let co = 0, ti = 0, sk = 0, skCards = 0;
const coMisses = [], tiMisses = [];
for (const p of posts) {
  const r = parseTgJob(p.text, p.tags);
  if (r.company) co++;
  if (r.title) ti++;
  // Навыки считаем так же, как их показывает карточка: подборки (isDigestPost),
  // резюме соискателей (isResumePost) и посты «лёгкий заработок» (isEasyMoneyPost)
  // в ленту не попадают — looksLikeVacancy в jobs.html отсеивает их этими же
  // функциями, а не тегом «Дайджест» (Находка 3, повторное ревью: тег ставится
  // эвристикой скрейпера «5+ ролевых слов» и висит на обычных длинных вакансиях —
  // доверять ему после этого нельзя нигде, включая замер охвата). Такие посты не
  // входят ни в числитель, ни в знаменатель. Company передаём вторым аргументом —
  // как в jobs.html, иначе «Яндекс Go» даст навык go.
  if (!isDigestPost(p.text) && !isResumePost(p.text) && !isEasyMoneyPost(p.text)) {
    skCards++;
    if (extractSkills(p.text, r.company).length) sk++;
  }
  if (!r.company && coMisses.length < 15) coMisses.push(p.text.split("\n")[0].slice(0, 80));
  if (!r.title && tiMisses.length < 15) tiMisses.push(p.text.split("\n")[0].slice(0, 80));
}
const pct = (n, d) => `${((n / d) * 100).toFixed(1)}%`;
console.log(`постов: ${posts.length}`);
console.log(`компания: ${co} (${pct(co, posts.length)})`);
console.log(`должность: ${ti} (${pct(ti, posts.length)})`);
console.log(`навыки: ${sk}/${skCards} (${pct(sk, skCards)}) — без подборок и резюме, они в ленту не попадают`);
console.log("\nбез компании (первые 15):");
for (const m of coMisses) console.log("  ·", m);
console.log("\nбез должности (первые 15):");
for (const m of tiMisses) console.log("  ·", m);
