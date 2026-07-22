# Гигиена ленты: резюме и ложные дайджесты — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать из ленты 30 постов-резюме соискателей и вернуть в неё 19 настоящих вакансий, которые невидимы из-за ложного тега «Дайджест».

**Architecture:** Две чистые функции в `tgparse.js` — `isResumePost(text)` и `isDigestPost(text, lines)` — плюс их вызов в `looksLikeVacancy` в `jobs.html`. Всё на клиенте: правила применяются ко всем уже собранным постам без миграции и перескрейпа. `parser/scrape_posts.py` не трогаем.

**Tech Stack:** Ванильный JS (ES2020, без сборки), Node ≥ 18 для `node:test`.

## Global Constraints

- Никаких внешних рантайм-зависимостей: ни CDN, ни сторонних доменов. Сайт обязан открываться из РФ без VPN.
- Никаких новых npm-зависимостей: тесты только на встроенном `node:test`.
- `tgparse.js` не трогает DOM и не читает глобальные переменные `jobs.html` — только аргументы функций.
- Новые top-level имена в `tgparse.js` не должны совпадать с именами в `jobs.html` (в прошлый раз `const BRANDS` в обоих файлах дал `SyntaxError` и уронил весь сайт). Перед коммитом сверять: `grep -n "^const NEWNAME\|^function NEWNAME" jobs.html`.
- Комментарии в коде — по-русски.
- Вне объёма: разбивка подборок на отдельные карточки, вкладка «Резюме», правки в `parser/scrape_posts.py` и схеме БД.

---

### Task 1: Распознавание постов-резюме

**Files:**
- Modify: `tgparse.js` (добавить функцию и экспорт в конце файла)
- Test: `tests/tgparse.test.mjs`

**Interfaces:**
- Produces: `isResumePost(text) -> boolean` — глобальная функция в браузере, в `module.exports` для Node.

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/tgparse.test.mjs`. Тексты взяты из реальных постов ленты.

```js
test("резюме соискателя опознаётся", () => {
  const t = "Резюме: Head of Customer Operations / Руководитель клиентских операций\n\n" +
    "🧑‍💻 Сергей Рыбачек\nНик tg: @rybacheque\nНомер телефона: +7-985-474-31-67\n" +
    "Email: rybacheque@gmail.com\n\nВозраст: 31\nФормат/Локация: Москва - Офис; Гибрид; Удаленка";
  assert.equal(isResumePost(t), true);
});

test("вакансия, где просят прислать резюме, — не резюме", () => {
  const t = "🔎 Рекрутер\n\nМы \"VICTORY group\" являемся одним из лидирующих рекламных агентств России.\n\n" +
    "📎 Обязанности:\n • Массовый подбор персонала;\n • Поиск резюме на JOB-ресурсах, обработка откликов\n" +
    "Резюме присылайте на почту hr@victory.ru";
  assert.equal(isResumePost(t), false);
});

test("одного заголовка «Резюме:» без анкеты мало", () => {
  assert.equal(isResumePost("Резюме: Маркетолог\n\nПодробности по ссылке."), false);
});

test("пустой текст — не резюме", () => {
  assert.equal(isResumePost(""), false);
});
```

- [ ] **Step 2: Запустить, убедиться что падают**

Run: `node --test tests/`
Expected: FAIL — `isResumePost is not defined`

- [ ] **Step 3: Реализовать `isResumePost`**

Добавить в `tgparse.js` перед экспортом:

```js
// Пост-резюме соискателя, а не вакансия: канал jobster_resume и подобные
// публикуют анкеты людей, ищущих работу, с их личными контактами. Признаки
// структурные (заголовок-рубрика, контакты, анкетные поля), а не тематические:
// слово «резюме» само по себе встречается и в вакансиях («присылайте резюме»),
// поэтому одного признака мало — требуем два из трёх.
const RESUME_HEAD = /^\s*[^\p{L}\n]{0,4}(?:резюме|cv)\s*[:—-]/iu;
const RESUME_CONTACT = /(?:^|\n)\s*(?:ник\s*(?:tg|телеграм)|номер\s+телефона|телефон|email|почта)\s*[:—-]/iu;
const RESUME_FIELDS = /(?:^|\n)\s*(?:возраст|формат\s*\/\s*локация|опыт\s+работы|о\s+себе|обо\s+мне)\s*[:—-]/iu;

function isResumePost(text) {
  const t = String(text || "");
  if (!t) return false;
  const hits = [RESUME_HEAD, RESUME_CONTACT, RESUME_FIELDS].filter(rx => rx.test(t)).length;
  return hits >= 2;
}
```

Добавить `isResumePost` в `module.exports` (сейчас там `{ parseTgJob, extractSkills }`).

Импорт в тестах: файл уже импортирует функции через `createRequire` в начале — добавить `isResumePost` в тот же деструктурирующий импорт.

- [ ] **Step 4: Запустить тесты**

Run: `node --test tests/`
Expected: PASS — все существующие плюс 4 новых.

- [ ] **Step 5: Проверить охват на реальных данных**

```bash
node -e '
const {isResumePost}=require("./tgparse.js");
const posts=require("./data/job_feed.json");
const hit=posts.filter(p=>isResumePost(p.text));
console.log("опознано резюме:",hit.length,"из",posts.length);
const ch={}; hit.forEach(p=>{const c=p.link.split("/")[3]; ch[c]=(ch[c]||0)+1;});
console.log("по каналам:",JSON.stringify(ch));
hit.slice(0,10).forEach(p=>console.log("   "+p.text.split("\n")[0].slice(0,60)));
'
```

Expected: около 30 постов, большинство из `jobster_resume`. Просмотреть список глазами: каждая строка должна быть резюме, а не вакансией. Если попала вакансия — ужесточить правило и вернуться к шагу 4.

- [ ] **Step 6: Коммит**

```bash
git add tgparse.js tests/tgparse.test.mjs
git commit -m "feat(jobs): распознавание постов-резюме соискателей"
```

---

### Task 2: Единое определение дайджеста

**Files:**
- Modify: `tgparse.js` (добавить `isDigestPost`, экспортировать её и `isJobDigest`)
- Test: `tests/tgparse.test.mjs`

**Interfaces:**
- Consumes: `isJobDigest(lines)` и константа `DIGEST_ENTRY` — оба уже существуют в `tgparse.js` (около строки 387). `isJobDigest` принимает массив первых непустых строк; `DIGEST_ENTRY` — регулярка строки-пункта «Роль в/‌/ Компания». Заново их объявлять не нужно, только использовать.
- Produces: `isDigestPost(text) -> boolean` — принимает сырой текст поста, сам режет его на строки.

- [ ] **Step 1: Написать падающие тесты**

```js
test("подборка с маркером-рубрикой (буллиты, без «роль в компания»)", () => {
  const t = "#дайджест \nДайджест вакансий от компаний, которые нанимают на удаленку в Европе.\n" +
    "Instories — продукт для создания контента на базе Gen AI и ML.\n" +
    "• Senior Growth Product Manager (Web) ⚡️\n• Senior Growth Product Manager (Mobile) ⚡️\n" +
    "Lovi care refers to the Lóvi app, a personal skincare assistant app.\n" +
    "• AI Medical Research & Content Assistant ⚡️\n• Senior User Acquisition Manager ⚡️";
  assert.equal(isDigestPost(t), true);
});

test("подборка БУДУ: строки-пункты с ведущими эмодзи", () => {
  const t = "🥸 Подборка вакансий от БУДУ:\n😞 Лид направления спецпроектов в Онлайн-кампус НИУ ВШЭ\n" +
    "Опыт: более 3-х лет\nЗарплата: 140 000₽\n😞 Маркетолог в ИИ-стартап\nОпыт: от 1 месяца\n" +
    "Зарплата: 80 000₽\n😞 Менеджер по продажам в Multiways\nОпыт: от 1 года";
  assert.equal(isDigestPost(t), true);
});

test("подборка без маркера ловится структурно (Хабр Карьера)", () => {
  const t = "Вакансии для лидов на Хабр Карьере.\n\nРуководитель направления SRE в Cloud .ru. Можно удаленно. Москва.\n\n" +
    "Руководитель команды разработки в МТ-Интеграция. Москва.\n\nШеф-редактор в CHOICEIT. Можно удаленно.";
  assert.equal(isDigestPost(t), true);
});

test("обычная вакансия — не подборка", () => {
  const t = "Контент-маркетолог клуба в Forbes Club\n\nЧто делать:\n" +
    "– понимать и сегментировать аудиторию клуба;\n– находить, где эта аудитория бывает;\n" +
    "– разрабатывать и вести контент-стратегию;\n– создавать контент.";
  assert.equal(isDigestPost(t), false);
});

test("короткая вакансия — не подборка", () => {
  assert.equal(isDigestPost("QA Backend Tech Lead в Qatar Insurance Сompany\n\nОпыт от 4 лет. Доха."), false);
});
```

- [ ] **Step 2: Запустить, убедиться что падают**

Run: `node --test tests/`
Expected: FAIL — `isDigestPost is not defined`

- [ ] **Step 3: Реализовать `isDigestPost`**

Добавить в `tgparse.js` рядом с существующей `isJobDigest`:

```js
// Маркер-рубрика в шапке поста: канал прямо объявляет подборку. Это точная
// часть правила _DIGEST из parser/scrape_posts.py, перенесённая на клиент.
// Ошибочно в скрейпере соседнее условие «5+ ролевых слов в тексте» — оно вешает
// тег «Дайджест» на длинные обычные вакансии, поэтому на клиент не переносится
// и самому тегу лента больше не верит.
const DIGEST_MARK = /#дайджест|дайджест\s+ваканс|подборка\s+ваканс|вакансии\s+недели|кого\s+ищут|лучшее\s+за\s+неделю|топ\s+(?:открытых\s+)?(?:позиц|ваканс)/i;
// Буллит-список ролей под абзацем о компании («• Senior Growth Product Manager»)
// — форма подборки, где у строк нет вида «роль в компания» (канал young_relocate).
const DIGEST_BULLET = /^[•·▪]\s*\S/;

// Пост — подборка многих вакансий: либо канал объявил это рубрикой (DIGEST_MARK),
// либо структура выдаёт список (isJobDigest / буллиты). Одна карточка обещает одну
// вакансию, поэтому подборки в ленту не берём.
function isDigestPost(text) {
  const lines = String(text || "").split("\n").map(s => s.trim()).filter(Boolean);
  if (lines.length < 4) return false;
  if (isJobDigest(lines.slice(0, 8))) return true;
  if (!DIGEST_MARK.test(lines.slice(0, 2).join(" "))) return false;
  // Маркер сам по себе не приговор: он встречается и в подписи-навигации под
  // обычной вакансией. Требуем ещё и список — буллиты либо строки-пункты.
  const bullets = lines.filter(ln => DIGEST_BULLET.test(ln)).length;
  const entries = lines.slice(1).filter(ln => DIGEST_ENTRY.test(ln.replace(/^[^\p{L}\p{N}]+/u, ""))).length;
  return bullets >= 3 || entries >= 2;
}
```

Добавить `isDigestPost` в `module.exports`.

- [ ] **Step 4: Запустить тесты**

Run: `node --test tests/`
Expected: PASS — все существующие плюс 5 новых.

- [ ] **Step 5: Проверить классификацию на реальных данных**

```bash
node -e '
const {isDigestPost}=require("./tgparse.js");
const posts=require("./data/job_feed.json");
const tagged=posts.filter(p=>(p.tags||[]).includes("Дайджест"));
console.log("подборок среди помеченных тегом:",tagged.filter(p=>isDigestPost(p.text)).length,"из",tagged.length);
console.log("\nвернутся в ленту (тег стоял, но это не подборка):");
tagged.filter(p=>!isDigestPost(p.text)).forEach(p=>console.log("   "+p.text.split("\n")[0].slice(0,58)));
const untagged=posts.filter(p=>!(p.tags||[]).includes("Дайджест")&&isDigestPost(p.text));
console.log("\nподборки без тега (уже отсекались структурно):",untagged.length);
'
```

Expected: среди помеченных тегом подборками признаются 8; возвращаются 23 поста (из них 4 — резюме, их отсечёт Task 1); подборок без тега — около 21 (Хабр Карьера). Просмотреть оба списка глазами: в «вернутся в ленту» не должно быть настоящих подборок.

- [ ] **Step 6: Коммит**

```bash
git add tgparse.js tests/tgparse.test.mjs
git commit -m "feat(jobs): единое определение подборки — маркер-рубрика или структура"
```

---

### Task 3: Подключить правила к ленте

**Files:**
- Modify: `jobs.html` (функция `looksLikeVacancy`, строки 1109–1123)

**Interfaces:**
- Consumes: `isResumePost(text)` из Task 1, `isDigestPost(text)` из Task 2 — обе доступны как глобальные функции, `tgparse.js` подключён в `jobs.html` через `<script src="tgparse.js">`.

- [ ] **Step 1: Заменить проверку дайджеста и добавить проверку резюме**

В `jobs.html` заменить в `looksLikeVacancy` строки с проверкой тега:

```js
  // Дайджест — подборка из многих РАЗНЫХ вакансий в одном посте. Карточка обещает одну
  // вакансию: заголовок, вилка и «Откликнуться» относились бы к случайной строке
  // подборки. Одна карточка = одна вакансия, поэтому подборки в ленту не берём.
  // Тегу «Дайджест» от скрейпера не верим: он ставится при 5+ ролевых словах и висит
  // на обычных длинных вакансиях (см. isDigestPost в tgparse.js).
  if(isDigestPost(text)) return false;
  // Резюме соискателя — не вакансия: анкета человека с его личными контактами.
  if(isResumePost(text)) return false;
```

Удалить строку `if(tags.includes("Дайджест")) return false;` и её комментарий-обоснование (заменены выше). Переменная `tags` в функции используется дальше (`ROLE_SET`, `CORROB_SET`) — её объявление не трогать.

- [ ] **Step 2: Проверить, что счёт ленты изменился как ожидалось**

```bash
node -e '
const fs=require("fs");
const {isDigestPost,isResumePost}=require("./tgparse.js");
const posts=require("./data/job_feed.json");
const было=posts.filter(p=>!(p.tags||[]).includes("Дайджест")).length;
const стало=posts.filter(p=>!isDigestPost(p.text)&&!isResumePost(p.text)).length;
console.log("проходит фильтр дайджеста/резюме: было",было,"стало",стало);
'
```

Expected: печатает два числа; «стало» меньше «было» примерно на 20–30 (ушли резюме, вернулись вакансии). Точное совпадение не требуется — окончательную цифру даёт браузер на шаге 4, потому что `looksLikeVacancy` применяет ещё и другие правила.

- [ ] **Step 3: Проверить отсутствие конфликта имён**

```bash
grep -n "isResumePost\|isDigestPost\|DIGEST_MARK\|DIGEST_BULLET\|RESUME_HEAD\|RESUME_CONTACT\|RESUME_FIELDS" jobs.html
```

Expected: только строки вызовов внутри `looksLikeVacancy`, никаких `const`/`function` с этими именами. Если `jobs.html` объявляет такое имя сам — переименовать в `tgparse.js`, иначе `SyntaxError` уронит весь скрипт страницы.

- [ ] **Step 4: Проверить в браузере**

```bash
python3 -m http.server 8765
```

Открыть `http://localhost:8765/jobs.html` и убедиться:
- лента рендерится, в консоли нет ошибок (особенно `SyntaxError` и `is not defined`);
- карточек-резюме нет — ни одного заголовка вида «Резюме: …»;
- карточек-подборок нет — ни «Подборка вакансий от БУДУ», ни «Вакансии с удалёнкой», ни «Вакансии … на Хабр Карьере»;
- появились вернувшиеся вакансии, например «Контент-маркетолог клуба» с работодателем «Forbes Club».

Проверить счётчиком в консоли браузера:

```js
[...document.querySelectorAll('.post[data-kind="tg"]')]
  .map(c => c.querySelector('.ptitle')?.textContent.trim())
  .filter(t => /^Резюме:|Подборка ваканс|Вакансии .* Хабр/i.test(t));
```

Expected: пустой массив.

- [ ] **Step 5: Прогнать тесты и замер охвата**

Run: `node --test tests/ && node tests/coverage.mjs`
Expected: все тесты зелёные; охват по компании и должности не ниже прежнего (компания ~235, должность ~365 на 500 постах).

- [ ] **Step 6: Коммит**

```bash
git add jobs.html
git commit -m "feat(jobs): убрать резюме из ленты, не верить тегу «Дайджест»"
```
