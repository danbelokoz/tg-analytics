// Разбор TG-поста: должность и компания. Чистые функции, без DOM — подключаются
// и в браузер (<script src>), и в Node (тесты, скрипт охвата).

// Эвристический разбор TG-поста: должность (первая содержательная строка) и
// компания по паттернам «<роль> в <Компания>», «роль / Компания», «<Company> is a…».
// Неидеально (~65%): дайджесты и анонимные посты остаются без company — тогда
// карточка показывает как раньше (канал + текст).
const CO_STOP = /^(москв|петербург|спб|санкт|росси|remote|удал|дистанц|офис|гибрид|команд|стартап|компани|проект|ваканс|it\b|hr\b|финтех|екатеринб|новосиб|казан|сша|европ|азия|dubai|дубай)/i;
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
function parseTgJob(text, tags){
  if(!text) return {};
  if((tags||[]).includes("Дайджест")) return {};        // список многих вакансий — пары не выделить
  const stripLead = s => s.replace(/^[^\p{L}\p{N}#@]+/u,"").trim();   // убрать ведущие эмодзи/пунктуацию (цифры оставляем — «2GIS»)
  let head="", rawHead="";
  for(const ln of text.split("\n")){
    const s=ln.trim(); if(!s) continue;
    if(s.startsWith("#") && s.split(/\s+/).length<=4) continue;       // строка сплошных хэштегов
    head=stripLead(s); rawHead=ln; break;
  }
  if(!head) return {};
  head = head.split(/\s+#/)[0].trim();                                // срезать хвостовые хэштеги
  let title=head, company=null;
  let m = head.match(/^(.*?\S)\s+в\s+([\p{Lu}\p{N}][^,\n:—]{1,40})/u) // «… в Компания» (компания с заглавной/цифры)
       || head.match(/^(.+?)\s*\/\s*([^/\n]{2,40})$/u);              // «роль / Компания»
  if(m){ const c=cleanCo(m[2]); if(c){ title=m[1].trim(); company=c; } }
  if(!company){
    for(const ln of text.split("\n").slice(0,4)){                     // «<Company> is a/an … company»
      const mi=ln.trim().match(/^([\p{Lu}][\w .&'’-]{1,40}?)\s+is\s+(?:a|an|the|one)\b/u);
      if(mi){ company=cleanCo(mi[1]); if(company) break; }
    }
  }
  title = title.replace(/[\s:—–-]+$/u,"").slice(0,90);
  // заголовки-подборки/дайджесты — это не должность
  if(/^(ваканс|подборк|дайджест|кого ищ|свежие|горячие|новые ваканс|топ[- ])/i.test(title)) title=null;
  return {title: title||null, company};
}

// Экспорт: в браузере функции уже глобальны, в Node — через module.exports.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseTgJob, cleanCo };
}
