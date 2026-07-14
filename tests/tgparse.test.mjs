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

test("известный бренд ловится в любом месте текста", () => {
  const r = parseTgJob("Ищем сильного разработчика.\nРаботать будешь над платформой Ozon.", []);
  assert.equal(r.company, "Ozon");
});
