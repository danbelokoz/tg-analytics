"""Фильтр языка вакансии: оставляем только русский или английский.

Зачем: в ленту попадают вакансии на испанском/португальском и т.п. (напр. Plata
из Мексики). Аудитория русско/англоязычная — прочие языки убираем и на витрине,
и в парсинге (общий модуль, чтобы правило было одно).

Без внешних зависимостей: кириллица → русский; латиница различаем по стоп-словам
(английский vs испанский/португальский/французский/итальянский/немецкий) и по
диакритике/пунктуации, характерной НЕ для английского. По умолчанию, если текст
явно не «другой», считаем английским и оставляем — чтобы не выкинуть валидный EN.
"""
import re

_WORD = re.compile(r"[a-zA-Zà-ÿ]+")
_CYR  = re.compile(r"[а-яёА-ЯЁ]")
# Диакритика/пунктуация, которой в английском практически не бывает.
_NON_EN_CHARS = set("áéíóúñ¿¡ãõçâêôîûàèìòùäöüßœ")

# Частотные служебные слова. EN — то, что оставляем; OTHER — сигнал «не английский».
_EN = {
    "the","and","of","to","for","in","is","on","with","as","we","you","our","are",
    "be","will","your","or","at","this","that","an","by","from","have","has","it",
    "who","what","how","their","they","about","role","team","work","experience",
}
_OTHER = {
    # es/pt
    "de","la","el","los","las","un","una","para","con","que","del","por","su","se",
    "como","más","también","empresa","trabajo","nuestro","nuestra","você","não",
    "com","uma","para","seu","sua","empresa","vaga","nós",
    # fr
    "le","les","des","une","pour","avec","nous","vous","votre","être","poste","et",
    "notre","dans","sur","est","sont","cette","chez","ainsi","afin","qui","au","aux",
    # es (доп.)
    "nuestro","nuestra","buscamos","estamos","somos","puesto","tus","según","será",
    # de/it
    "und","der","die","das","für","mit","wir","sie","eine","della","dei","gli","per",
    "azienda","lavoro","ist","ein","auch","zu","den","dem","nella","sono","cerca",
}


def _cyr_ratio(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _CYR.match(c)) / len(letters)


def lang_ok(text):
    """True, если описание на русском или английском (иначе — отбрасываем)."""
    if not text or not text.strip():
        return False
    if _cyr_ratio(text) > 0.20:          # заметная доля кириллицы → русский
        return True
    low = text.lower()
    words = _WORD.findall(low)
    if not words:
        return False
    en = sum(1 for w in words if w in _EN)
    other = sum(1 for w in words if w in _OTHER)
    accents = sum(1 for c in low if c in _NON_EN_CHARS)
    # Явный «другой» язык: не-английская пунктуация/диакритика или перевес чужих слов.
    if "¿" in text or "¡" in text:
        return False
    if other > en and (other >= 2 or accents >= 2):
        return False
    if accents >= 3 and en < 2:
        return False
    # Иначе считаем английским (не выкидываем валидный EN из-за коротких описаний).
    return True
