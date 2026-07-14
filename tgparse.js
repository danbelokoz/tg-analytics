// Разбор TG-поста: должность и компания. Чистые функции, без DOM — подключаются
// и в браузер (<script src>), и в Node (тесты, скрипт охвата).

// Эвристический разбор TG-поста: должность (первая содержательная строка) и
// компания по паттернам «<роль> в <Компания>», «роль / Компания», «<Company> is a…».
// Неидеально (~65%): дайджесты и анонимные посты остаются без company — тогда
// карточка показывает как раньше (канал + текст).
const CO_STOP = /^(москв|петербург|спб|санкт|росси|remote|удал|дистанц|офис|гибрид|команд|стартап|компани|проект|ваканс|it\b|hr\b|финтех|екатеринб|новосиб|казан|сша|европ|азия|dubai|дубай|поиске|связи|течение|отдел|сфер|област|направлени|штат|найм)/i;
// Аббревиатуры и слова-должности, ошибочно попадающие в «компанию»
// (напр. «Chief Technology Officer / CTO» → «CTO» — это должность, не компания).
const ROLE_WORD = /^(c[a-z]?o|ciso|vp|pm|po|pmm|ba|sa|qa|tl|hrd|hrbp|smm|pr|ux|ui|team\s?lead|tech\s?lead|(?:back|front|full[\s-]?stack)[\s-]?end|developer|engineer|manager|designer|analyst|architect|specialist|lead|intern|разработчик\w*|инженер\w*|менеджер\w*|дизайнер\w*|аналитик\w*|директор\w*|руководител\w*|специалист\w*|стажёр\w*|тимлид\w*)$/i;
function cleanCo(s){
  s = (s||"").replace(/^[^\p{L}\p{N}]+/u,"").trim();
  s = s.split(/\s{2,}|https?:|[.,:;•|]|\s+[—–-]\s+/u)[0].trim();      // отсечь хвост/ссылку/пунктуацию
  s = s.replace(/\s+(?:ищет|ищут|нанимает|hiring|команда).*$/iu,"").trim();
  if(!s || s.length<2 || CO_STOP.test(s) || ROLE_WORD.test(s) || !/\p{L}/u.test(s)) return null;
  return s.slice(0,40);
}
// Источники компании по убыванию надёжности. Каждый возвращает сырого кандидата,
// его чистит cleanCo (стоп-листы городов и слов-должностей).
const CO_LABEL = /^(?:компания|работодатель|о компании)\s*[:—-]\s*(.*)$/iu;
// \b тут не годится: JS-регэкспы считают word-символами только [A-Za-z0-9_],
// поэтому граница после кириллического «ищет» перед пробелом не находится —
// используем lookahead «дальше не буква/цифра» вместо \b.
const CO_HIRES = /^[«"“]?([\p{Lu}\p{N}][^«»"”\n]{1,40}?)[»"”]?\s+(?:ищет|ищут|нанимает|в поиске)(?![\p{L}\p{N}])/u;
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
  // 2. «X ищет …» / «X is a …» / «… в X» — в первых строках поста. Идём
  //    построчно сверху вниз (а не паттерн за паттерном по всему тексту):
  //    иначе случайное совпадение CO_HIRES в дальней строке («Ребята активно
  //    ищут…») перебивает надёжный CO_IN из заголовка («…в Exness»).
  for (const ln of lines) {
    for (const rx of [CO_HIRES, CO_IS_A, CO_IN]) {
      const m = ln.match(rx);
      if (!m) continue;
      const c = cleanCo(m[1]);
      if (c) return c;
    }
  }
  return null;
}

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

// Разбор заголовка (первая содержательная строка + паттерны «роль в Компания»,
// «роль / Компания»). Пока не меняем поведение — доработка в Task 3.
function titleFrom(lines, company) {
  const stripLead = s => s.replace(/^[^\p{L}\p{N}#@]+/u,"").trim();   // убрать ведущие эмодзи/пунктуацию (цифры оставляем — «2GIS»)
  let head = "";
  for (const s of lines) {
    if (s.startsWith("#") && s.split(/\s+/).length <= 4) continue;    // строка сплошных хэштегов
    head = stripLead(s);
    break;
  }
  if (!head) return null;
  head = head.split(/\s+#/)[0].trim();                                // срезать хвостовые хэштеги
  let title = head;
  let m = head.match(/^(.*?\S)\s+в\s+([\p{Lu}\p{N}][^,\n:—]{1,40})/u) // «… в Компания» (компания с заглавной/цифры)
       || head.match(/^(.+?)\s*\/\s*([^/\n]{2,40})$/u);              // «роль / Компания»
  if (m) {
    const c = cleanCo(m[2]);
    if (c) title = m[1].trim();
  }
  title = title.replace(/[\s:—–-]+$/u,"").slice(0,90);
  // заголовки-подборки/дайджесты — это не должность
  if (/^(ваканс|подборк|дайджест|кого ищ|свежие|горячие|новые ваканс|топ[- ])/i.test(title)) title = null;
  return title;
}

function parseTgJob(text, tags) {
  if (!text) return {};
  if ((tags || []).includes("Дайджест")) return {};   // список многих вакансий — пары не выделить
  const lines = text.split("\n").map(s => s.trim()).filter(Boolean).slice(0, 8);
  if (!lines.length) return {};
  const company = companyFrom(lines) || brandFrom(text);
  const title = titleFrom(lines, company);
  return { title: title || null, company };
}

// Экспорт: в браузере функции уже глобальны, в Node — через module.exports.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseTgJob, cleanCo };
}
