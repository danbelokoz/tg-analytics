# TG Job Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Карточка вакансии из Telegram показывает работодателя и должность, распознанные из текста поста, а не имя канала и сырую первую строку.

**Architecture:** Разбор поста выносится из inline-`<script>` в `jobs.html` в отдельный модуль `tgparse.js` — чистые функции без DOM, подключаемые и в браузер (`<script src>`), и в Node (тесты). Логика остаётся клиентской: правила меняются без миграции схемы и перескрейпа и сразу применяются ко всем уже собранным постам. Тесты — `node:test`, без новых зависимостей.

**Tech Stack:** Ванильный JS (ES2020, без сборки), Node ≥ 18 для `node:test`, Python 3 для скрипта охвата.

## Global Constraints

- Никаких внешних рантайм-зависимостей на странице: ни CDN, ни сторонних доменов. Сайт обязан открываться из РФ без VPN — всё самохостится (см. `PROJECT.md`).
- Никаких новых npm-зависимостей: тесты только на встроенном `node:test`.
- `tgparse.js` не трогает DOM и не читает глобальные переменные `jobs.html` — только аргументы функций.
- Имя TG-канала не выводится в карточке ленты ни при каком исходе разбора.
- Текст-заглушка в шапке — ровно `Вакансии из каналов ТГ`.
- Комментарии в коде — по-русски, как в остальном проекте.
- Вне объёма: посты-резюме кандидатов и разбивка дайджестов — следующий этап.

---

### Task 1: Модуль `tgparse.js` с текущим поведением + тесты

Механический перенос без изменения логики: сначала фиксируем тестами то, что есть, потом улучшаем. Так рост охвата в Task 5 будет измерим относительно базы.

**Files:**
- Create: `tgparse.js`
- Create: `tests/tgparse.test.mjs`
- Modify: `jobs.html` (удалить inline `CO_STOP`, `ROLE_WORD`, `cleanCo`, `parseTgJob` — строки 789–826; добавить `<script src="tgparse.js"></script>` перед основным `<script>`, т.е. перед строкой 371)

**Interfaces:**
- Produces: `parseTgJob(text, tags) -> {title: string|null, company: string|null}` — глобальная функция (`window.parseTgJob` в браузере, `module.exports.parseTgJob` в Node).

- [ ] **Step 1: Написать падающий тест**

Создать `tests/tgparse.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { parseTgJob } = require("../tgparse.js");

test("«роль в Компания» — вытаскивает и должность, и компанию", () => {
  const r = parseTgJob("QA Engineer (Data Stack) в Exness\n\nРебята активно ищут", []);
  assert.equal(r.company, "Exness");
  assert.equal(r.title, "QA Engineer (Data Stack)");
});

test("«Company is a…» во второй строке — вытаскивает компанию", () => {
  const r = parseTgJob(
    "Middle Product Owner\nZexter is a technology provider specializing in digital infrastructure.",
    [],
  );
  assert.equal(r.company, "Zexter");
  assert.equal(r.title, "Middle Product Owner");
});

test("дайджест — пар «должность+компания» не выделяем", () => {
  const r = parseTgJob("Вакансии для лидов\n\nSRE в Cloud.ru\nШеф-редактор в CHOICEIT", ["Дайджест"]);
  assert.equal(r.title, undefined);
  assert.equal(r.company, undefined);
});

test("город не считается компанией", () => {
  const r = parseTgJob("Менеджер по продажам в Москве", []);
  assert.equal(r.company, null);
});
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

Run: `node --test tests/`
Expected: FAIL — `Cannot find module '../tgparse.js'`

- [ ] **Step 3: Создать `tgparse.js` — перенести код как есть**

Скопировать из `jobs.html` строки 785–826 (`CO_STOP`, `ROLE_WORD`, `cleanCo`, `parseTgJob`) без изменения логики и добавить экспорт в конце файла:

```js
// Разбор TG-поста: должность и компания. Чистые функции, без DOM — подключаются
// и в браузер (<script src>), и в Node (тесты, скрипт охвата).
// ... сюда переносится существующий код CO_STOP / ROLE_WORD / cleanCo / parseTgJob ...

// Экспорт: в браузере функции уже глобальны, в Node — через module.exports.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseTgJob, cleanCo };
}
```

- [ ] **Step 4: Запустить тесты**

Run: `node --test tests/`
Expected: PASS — 4/4. Если «город не считается компанией» падает, это уже дефект текущей логики: пометить тест `{ todo: true }` и починить в Task 2, не правя логику здесь.

- [ ] **Step 5: Подключить модуль в `jobs.html` и удалить inline-копию**

В `jobs.html` перед строкой 371 (`<script>`):

```html
<script src="tgparse.js"></script>
```

Удалить из inline-`<script>` строки 789–826 (`CO_STOP`, `ROLE_WORD`, `cleanCo`, `parseTgJob`), оставив комментарий-ссылку:

```js
// Разбор TG-поста (должность/компания) — в tgparse.js, чтобы покрыть тестами.
```

- [ ] **Step 6: Проверить страницу в браузере**

Открыть `jobs.html` через preview, убедиться: лента рендерится, в консоли нет `parseTgJob is not defined`.

- [ ] **Step 7: Коммит**

```bash
git add tgparse.js tests/tgparse.test.mjs jobs.html
git commit -m "refactor(jobs): вынести разбор TG-поста в tgparse.js + тесты"
```

---

### Task 2: Улучшить распознавание компании

**Files:**
- Modify: `tgparse.js`
- Modify: `tests/tgparse.test.mjs`

**Interfaces:**
- Consumes: `parseTgJob(text, tags)` из Task 1.
- Produces: сигнатура не меняется; растёт доля непустых `company`.

- [ ] **Step 1: Написать падающие тесты на реальных постах**

Добавить в `tests/tgparse.test.mjs`:

```js
test("метка «Компания:» — самый надёжный источник", () => {
  const r = parseTgJob(
    "Вакансия: Product Leader Adult Project\nКомпания: New Sky Group\nФормат: полная занятость, удалённо",
    [],
  );
  assert.equal(r.company, "New Sky Group");
});

test("метка «Работодатель:» на следующей строке", () => {
  const r = parseTgJob(
    "Менеджер по продажам в студию детской киношколы\n\nРаботодатель:\nСтудия Звёзд, федеральная сеть детских киношкол.",
    [],
  );
  assert.equal(r.company, "Студия Звёзд");
});

test("«X» ищет <кого-то> — компания в кавычках", () => {
  const r = parseTgJob("«Союзмультфильм» ищет менеджера проектов, который будет координировать ИИ", []);
  assert.equal(r.company, "Союзмультфильм");
});

test("«X ищет …» без кавычек", () => {
  const r = parseTgJob("Smm-менеджер\nЗ/п от 50 000 рублей\n\nКрокодил маркетинга ищет крутого smm", []);
  assert.equal(r.company, "Крокодил маркетинга");
});

test("«в X» на второй строке", () => {
  const r = parseTgJob("CTO\nв X-Labs — лаборатория продуктов, разрабатывающая ПО.\nМинск, Беларусь.", []);
  assert.equal(r.company, "X-Labs");
});

test("хвост после компании отсекается по точке", () => {
  const r = parseTgJob("SMM-менеджер / Контент-creator в Simply Rent. Москва. Частичная удаленка.", []);
  assert.equal(r.company, "Simply Rent");
});

test("город после «в» — не компания", () => {
  const r = parseTgJob("Менеджер по продажам в Москве. Офис.", []);
  assert.equal(r.company, null);
});
```

- [ ] **Step 2: Запустить, убедиться что падают**

Run: `node --test tests/`
Expected: FAIL на метках `Компания:` / `Работодатель:`, на «X ищет» и на «в X» во второй строке — текущий код смотрит только первую строку.

- [ ] **Step 3: Реализовать источники по приоритету**

В `tgparse.js` добавить перед `parseTgJob`:

```js
// Источники компании по убыванию надёжности. Каждый возвращает сырого кандидата,
// его чистит cleanCo (стоп-листы городов и слов-должностей).
const CO_LABEL = /^(?:компания|работодатель|о компании)\s*[:—-]\s*(.*)$/iu;
const CO_HIRES = /^[«"“]?([\p{Lu}\p{N}][^«»"”\n]{1,40}?)[»"”]?\s+(?:ищет|ищут|нанимает|в поиске)\b/u;
const CO_IS_A  = /^([\p{Lu}][\w .&'’-]{1,40}?)\s+is\s+(?:a|an|the|one)\b/u;
const CO_IN    = /(?:^|\s)в\s+([\p{Lu}\p{N}][^,\n:—(]{1,40})/u;

function companyFrom(lines) {
  // 1. Явная метка. Значение может стоять на той же строке или на следующей
  //    («Работодатель:\nСтудия Звёзд, …»).
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(CO_LABEL);
    if (!m) continue;
    const c = cleanCo(m[1]) || cleanCo(lines[i + 1] || "");
    if (c) return c;
  }
  // 2. «X ищет …» / «X is a …» / «… в X» — в первых строках поста.
  for (const rx of [CO_HIRES, CO_IS_A, CO_IN]) {
    for (const ln of lines) {
      const m = ln.match(rx);
      if (!m) continue;
      const c = cleanCo(m[1]);
      if (c) return c;
    }
  }
  return null;
}
```

Переписать тело `parseTgJob` так, чтобы оно бралo первые 8 непустых строк и звало `companyFrom`:

```js
function parseTgJob(text, tags) {
  if (!text) return {};
  if ((tags || []).includes("Дайджест")) return {};   // список многих вакансий — пары не выделить
  const lines = text.split("\n").map(s => s.trim()).filter(Boolean).slice(0, 8);
  if (!lines.length) return {};
  const company = companyFrom(lines);
  const title = titleFrom(lines, company);            // titleFrom появится в Task 3
  return { title: title || null, company };
}
```

Пока Task 3 не сделан, `titleFrom` определить как текущую логику первой строки — целиком перенести существующий разбор заголовка в функцию `titleFrom(lines, company)`, не меняя поведения.

Дополнить `CO_STOP` словами, которые встречаются после «в» и компанией не являются:

```js
const CO_STOP = /^(москв|петербург|спб|санкт|росси|remote|удал|дистанц|офис|гибрид|команд|стартап|компани|проект|ваканс|it\b|hr\b|финтех|екатеринб|новосиб|казан|сша|европ|азия|dubai|дубай|поиске|связи|течение|отдел|сфер|област|направлени|штат|найм)/i;
```

- [ ] **Step 4: Запустить тесты**

Run: `node --test tests/`
Expected: PASS — все тесты Task 1 и Task 2.

- [ ] **Step 5: Словарь известных брендов — последний источник**

Тест:

```js
test("известный бренд ловится в любом месте текста", () => {
  const r = parseTgJob("Ищем сильного разработчика.\nРаботать будешь над платформой Ozon.", []);
  assert.equal(r.company, "Ozon");
});
```

Реализация в `tgparse.js` — брать имена из `parser/companies_ats.json` при генерации не нужно: список короткий и статичный, держим его прямо в модуле рядом с паттернами.

```js
// Известные бренды — последний источник, когда паттерны не сработали. Ищем по
// границам слова в любом месте поста. Пополнять по результатам tests/coverage.mjs.
const BRANDS = [
  "Яндекс","Yandex","Ozon","Wildberries","Сбер","Sber","Тинькофф","Т-Банк","Авито","Avito",
  "VK","МТС","Мегафон","Билайн","Альфа-Банк","Газпромбанк","Х5","Лента","Магнит","Самокат",
  "Райффайзен","Точка","Skyeng","Ламода","Lamoda","Циан","Домклик","Купер","Exness","Kaspi",
  "InDrive","Nebius","ClickHouse","JetBrains","Miro","Semrush","Revolut","Plata","Aviasales",
  "Selectel","Cloud.ru","Positive Technologies","Kaspersky","Касперск","2ГИС","2GIS",
];
const BRAND_RX = BRANDS.map(b => [b, new RegExp(
  `(?<![\\p{L}\\p{N}])${b.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\p{L}\\p{N}])`, "iu")]);

function brandFrom(text) {
  for (const [name, rx] of BRAND_RX) if (rx.test(text)) return name;
  return null;
}
```

В `parseTgJob` использовать как fallback: `const company = companyFrom(lines) || brandFrom(text);`

- [ ] **Step 6: Запустить тесты**

Run: `node --test tests/`
Expected: PASS — все тесты Task 1 и Task 2, включая бренды.

- [ ] **Step 7: Коммит**

```bash
git add tgparse.js tests/tgparse.test.mjs
git commit -m "feat(jobs): распознавание компании по меткам, «X ищет», «в X», словарю брендов"
```

---

### Task 3: Улучшить распознавание должности

**Files:**
- Modify: `tgparse.js`
- Modify: `tests/tgparse.test.mjs`

**Interfaces:**
- Consumes: `companyFrom(lines)`, `cleanCo(s)` из Task 2.
- Produces: `titleFrom(lines, company) -> string|null` — внутренняя функция, наружу видна через `parseTgJob().title`.

- [ ] **Step 1: Написать падающие тесты**

```js
test("метка «Вакансия:» — должность", () => {
  const r = parseTgJob("Вакансия: Product Leader Adult Project\nКомпания: New Sky Group", []);
  assert.equal(r.title, "Product Leader Adult Project");
});

test("«X ищет <должность>» — должность из винительного падежа", () => {
  const r = parseTgJob("«Союзмультфильм» ищет менеджера проектов, который будет координировать ИИ", []);
  assert.equal(r.title, "менеджера проектов");
});

test("ссылка и город вычищаются из заголовка", () => {
  const r = parseTgJob("Менеджер по продажам в студию детской киношколы (г. Санкт-Петербург)\nhttps://t.me/x", []);
  assert.match(r.title, /^Менеджер по продажам/);
  assert.doesNotMatch(r.title, /https?:/);
});

test("строка без ролевого слова — должность не распознана", () => {
  const r = parseTgJob("Всем привет! Открыли новый набор на осень.\nПодробности ниже.", []);
  assert.equal(r.title, null);
});
```

- [ ] **Step 2: Запустить, убедиться что падают**

Run: `node --test tests/`
Expected: FAIL — сейчас `title` = сырая первая строка, ролевая проверка отсутствует.

- [ ] **Step 3: Реализовать `titleFrom`**

```js
// Слова, по которым строка опознаётся как должность. Без единого совпадения
// строку заголовком не считаем — иначе в заголовок лезет «Всем привет!».
const ROLE_HINT = /(разработчик|инженер|менеджер|дизайнер|аналитик|директор|руководител|специалист|тимлид|маркетолог|редактор|копирайтер|продюсер|таргетолог|рекрутер|бухгалтер|юрист|тестировщик|стажёр|стажер|ассистент|developer|engineer|manager|designer|analyst|architect|specialist|lead|head\s+of|director|officer|marketer|writer|editor|producer|recruiter|intern|owner|smm|seo|qa|devops|pm\b|po\b|cto|ceo|cmo|cpo)/iu;
const T_LABEL = /^(?:вакансия|должность|позиция|position|role)\s*[:—-]\s*(.*)$/iu;
const T_HIRES = /\b(?:ищет|ищем|ищут|требуется|требуются|нужен|нужна|в поиске)\s+(?:[а-яё]+\s+)?([^,.\n(]{3,60})/iu;

function titleFrom(lines, company) {
  // 1. Явная метка.
  for (const ln of lines) {
    const m = ln.match(T_LABEL);
    if (m && ROLE_HINT.test(m[1])) return cleanTitle(m[1]);
  }
  // 2. Первая строка, если в ней есть ролевое слово.
  const head = cleanTitle(stripCompany(lines[0], company));
  if (head && ROLE_HINT.test(head)) return head;
  // 3. «… ищет <должность>» в любой из первых строк.
  for (const ln of lines) {
    const m = ln.match(T_HIRES);
    if (m && ROLE_HINT.test(m[1])) return cleanTitle(m[1]);
  }
  return null;
}

// Заголовок без хвостов: ссылка, зарплата, город в скобках, хвостовые хэштеги
// и пунктуация. Оставляем скобки вида «(Data Stack)» — это часть должности.
function cleanTitle(s) {
  return String(s || "")
    .replace(/https?:\S+/gu, "")
    .replace(/\(\s*г\.[^)]*\)/giu, "")
    .replace(/\s+#\S+/gu, "")
    .replace(/^[^\p{L}\p{N}]+/u, "")
    .replace(/[\s:—–,-]+$/u, "")
    .trim()
    .slice(0, 90);
}

// Убрать «в <Компания>» из строки, чтобы компания не дублировалась в заголовке.
function stripCompany(line, company) {
  if (!company) return line;
  const esc = company.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return line.replace(new RegExp(`\\s*(?:в|at|@)\\s+[«"“]?${esc}[»"”]?.*$`, "iu"), "")
             .replace(new RegExp(`\\s*[/|]\\s*${esc}\\s*$`, "iu"), "");
}
```

Убрать из `parseTgJob` старую отсечку заголовков-подборок (`/^(ваканс|подборк|дайджест|…)/`) — `ROLE_HINT` теперь отсекает их сам, а метка `Вакансия:` должна работать.

- [ ] **Step 4: Запустить тесты**

Run: `node --test tests/`
Expected: PASS — все тесты Task 1–3.

- [ ] **Step 5: Коммит**

```bash
git add tgparse.js tests/tgparse.test.mjs
git commit -m "feat(jobs): распознавание должности по меткам и ролевым словам"
```

---

### Task 4: Навыки для чипов

**Files:**
- Modify: `tgparse.js`
- Modify: `tests/tgparse.test.mjs`

**Interfaces:**
- Produces: `extractSkills(text) -> string[]` — строчные названия навыков, порядок словаря, без дублей.

- [ ] **Step 1: Написать падающий тест**

```js
import { createRequire } from "node:module";
const { extractSkills } = createRequire(import.meta.url)("../tgparse.js");

test("навыки — из текста, строчными, без дублей", () => {
  const s = extractSkills("4+ года опыта, SQL, Python, опыт в fintech и AI-агентах. Kafka, Docker.");
  assert.deepEqual(s, ["python", "sql", "kafka", "docker", "ai", "fintech"]);
});

test("границы слова: go не ловится в google", () => {
  assert.deepEqual(extractSkills("Работаем с Google Ads и Google Analytics"), []);
});

test("пустой текст — пустой список", () => {
  assert.deepEqual(extractSkills(""), []);
});
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `node --test tests/`
Expected: FAIL — `extractSkills is not a function`

- [ ] **Step 3: Реализовать `extractSkills`**

```js
// Навыки для чипов карточки. Порядок словаря = порядок чипов: сначала языки и
// инструменты, потом домен. Ключ — то, что показываем; значения — как это пишут
// в постах. Границы слова обязательны: «go» не должно ловиться в «google».
const SKILLS = [
  ["python", ["python", "питон", "django", "fastapi"]],
  ["sql", ["sql", "postgres", "postgresql", "mysql", "clickhouse"]],
  ["js/ts", ["javascript", "typescript", "react", "vue", "node.js", "nodejs"]],
  ["java", ["java", "kotlin", "spring"]],
  ["go", ["golang", "go"]],
  ["php", ["php", "laravel"]],
  ["1c", ["1с", "1c"]],
  ["kafka", ["kafka", "кафка"]],
  ["docker", ["docker", "докер"]],
  ["kubernetes", ["kubernetes", "k8s"]],
  ["ci/cd", ["ci/cd", "gitlab ci", "jenkins"]],
  ["linux", ["linux", "линукс"]],
  ["git", ["git"]],
  ["figma", ["figma", "фигма"]],
  ["excel", ["excel", "эксель"]],
  ["seo", ["seo", "сео"]],
  ["smm", ["smm", "смм"]],
  ["ai", ["ai", "искусственн", "llm", "gpt", "ml", "machine learning"]],
  ["saas", ["saas"]],
  ["b2b", ["b2b"]],
  ["fintech", ["fintech", "финтех"]],
  ["e-commerce", ["e-commerce", "ecommerce", "маркетплейс"]],
];

// Кириллице разрешаем свободный суффикс («докер» → «докера»), латинице — обе
// границы. Та же логика, что в _kw_rx скрейпера (parser/scrape_posts.py).
const CYR = /[а-яё]/i;
const skillRx = words => new RegExp(
  words.map(w => {
    const e = w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return CYR.test(w) ? `(?<![а-яёa-z0-9])${e}` : `(?<![a-z0-9])${e}(?![a-z0-9])`;
  }).join("|"), "i");
const SKILL_RX = SKILLS.map(([name, words]) => [name, skillRx(words)]);

function extractSkills(text) {
  const t = String(text || "");
  return SKILL_RX.filter(([, rx]) => rx.test(t)).map(([name]) => name);
}
```

Добавить `extractSkills` в `module.exports`.

- [ ] **Step 4: Запустить тесты**

Run: `node --test tests/`
Expected: PASS. Если порядок в первом тесте не совпал — привести ожидание к порядку словаря (`SKILLS`), это и есть контракт.

- [ ] **Step 5: Коммит**

```bash
git add tgparse.js tests/tgparse.test.mjs
git commit -m "feat(jobs): словарь навыков для чипов карточки"
```

---

### Task 5: Карточка — шапка, аватар, чипы

**Files:**
- Modify: `jobs.html` (`cardTg` — строки 882–908; `badge` — 626–639; блок превью — около 1048)

**Interfaces:**
- Consumes: `parseTgJob`, `extractSkills` из `tgparse.js`.

- [ ] **Step 1: Добавить значок Telegram и аватар для TG-карточек**

В `jobs.html` рядом с `badge()` (после строки 639):

```js
// Значок Telegram — inline-SVG: никаких внешних запросов, грузится из РФ.
const TG_ICON = `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M9.8 15.6 9.6 19c.4 0 .6-.2.8-.4l2-1.9 4.1 3c.8.4 1.3.2 1.5-.7l2.7-12.6c.3-1.1-.4-1.6-1.1-1.3L2.9 10.4c-1.1.4-1.1 1-.2 1.3l4.3 1.3 10-6.3c.5-.3.9-.1.5.2l-7.7 7z"/></svg>`;
// Аватар TG-карточки: логотип компании, если он у нас есть; иначе — значок Telegram.
function avatarTg(company) {
  const slug = company ? slugOf(company) : null;
  if (slug && LOGOS.has(slug)) return badge(company, hueOf(slug), slug);
  return `<div class="ava tg">${TG_ICON}</div>`;
}
// Слаг компании для сопоставления с logos/*.png («Cloud.ru» → «cloud-ru»).
const slugOf = s => String(s || "").toLowerCase().trim()
  .replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-|-$/g, "");
```

Рядом с CSS-классом `.ava` (около строки 160, найти по `.ava{`) добавить:

```css
.ava.tg{background:#e8f1fb;color:#2f8ee0}
```

- [ ] **Step 2: Переписать `cardTg`**

Заменить тело `cardTg` (строки 882–908):

```js
function cardTg(p){
  const grade=(p.tags||[]).filter(t=>GRADE.has(t));
  const fmt=(p.tags||[]).filter(t=>FMT.has(t));
  const {title:jobTitle, company} = parseTgJob(p.text, p.tags);
  const isDigest=(p.tags||[]).includes("Дайджест");
  const title = jobTitle || firstLine(p.text) || (isDigest?"Подборка вакансий":"Вакансия");
  // Имя канала в карточке не показываем: либо работодатель, либо общая подпись.
  const srcName = company || "Вакансии из каналов ТГ";
  // Чипы — стек и навыки из текста поста (роли остаются тегами для фильтров слева).
  const tags=salPill(p)+metaPills([...fmt, ...grade])+skillChips(extractSkills(p.text));
  const exc=tgExcerpt(p.text, title) || "Подробности — на странице вакансии.";
  return `<div class="post" data-kind="tg" data-id="${p._id}" data-link="${esc(p.link)}">
    <div class="ptop">${avatarTg(company)}
      <span class="src-name">${esc(srcName)}</span>
      <span class="ptime">${timeAgo(p.posted_at)}</span>${EYE}
    </div>
    <div class="ptitle">${esc(title)}</div>
    <div class="pexc">${esc(exc)}</div>
    <div class="tags">${tags}</div>
  </div>`;
}
```

- [ ] **Step 3: Чипы — как на референсе (5 + «+N skills»)**

Заменить `skillChips` (строки 774–778):

```js
// Чипы навыков: 5 штук + счётчик остатка, как в референсном макете.
function skillChips(skills){
  const shown=skills.slice(0,5), extra=skills.length-shown.length;
  return shown.map(t=>`<span class="tag">${esc(t)}</span>`).join("")
    + (extra>0?`<span class="tag tmore">+${extra} skills</span>`:"");
}
```

- [ ] **Step 4: Поправить превью TG-поста**

В блоке превью (около строки 1048) заменить имя канала на ту же подпись:

```js
  const {title:jt, company:co}=parseTgJob(p.text,p.tags);
  ava:avatarTg(co), company:co||"Вакансии из каналов ТГ",
```

Ссылку на канал (`@username`) в превью оставить — она не в карточке ленты, и по спеке допустима.

- [ ] **Step 5: Проверить в браузере**

Открыть `jobs.html` через preview. Убедиться глазами и через `read_page`:
- ни в одной карточке ленты нет названия канала («Резюме ⚡️…», «FtRD4», «Хабр Карьера»);
- у карточек с распознанной компанией в шапке имя работодателя, у остальных — «Вакансии из каналов ТГ»;
- чипы — строчные навыки, максимум 5 + «+N skills»;
- в консоли нет ошибок.

- [ ] **Step 6: Коммит**

```bash
git add jobs.html
git commit -m "feat(jobs): в шапке TG-карточки работодатель или «Вакансии из каналов ТГ», чипы-стек"
```

---

### Task 6: Замер охвата

**Files:**
- Create: `tests/coverage.mjs`

**Interfaces:**
- Consumes: `parseTgJob`, `extractSkills` из `tgparse.js`; `data/job_feed.json` (500 постов).

- [ ] **Step 1: Написать скрипт охвата**

```js
// Замер охвата разбора на реальной выборке: доля постов, где распознаны компания
// и должность, плюс примеры промахов. Запуск: node tests/coverage.mjs
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const { parseTgJob, extractSkills } = createRequire(import.meta.url)("../tgparse.js");
const posts = JSON.parse(readFileSync(new URL("../data/job_feed.json", import.meta.url)));

let co = 0, ti = 0, sk = 0;
const misses = [];
for (const p of posts) {
  const r = parseTgJob(p.text, p.tags);
  if (r.company) co++;
  if (r.title) ti++;
  if (extractSkills(p.text).length) sk++;
  if (!r.company && misses.length < 15) misses.push(p.text.split("\n")[0].slice(0, 80));
}
const pct = n => `${((n / posts.length) * 100).toFixed(1)}%`;
console.log(`постов: ${posts.length}`);
console.log(`компания: ${co} (${pct(co)})`);
console.log(`должность: ${ti} (${pct(ti)})`);
console.log(`навыки: ${sk} (${pct(sk)})`);
console.log("\nбез компании (первые 15):");
for (const m of misses) console.log("  ·", m);
```

- [ ] **Step 2: Запустить и записать цифры**

Run: `node tests/coverage.mjs`
Expected: печатает три процента и список промахов. Ожидание по спеке — охват по компании заметно выше нынешних ~65%; если нет, разобрать список промахов и дополнить паттерны/стоп-листы в `tgparse.js`, повторив Task 2.

- [ ] **Step 3: Коммит**

```bash
git add tests/coverage.mjs
git commit -m "test(jobs): скрипт замера охвата разбора TG-постов"
```
