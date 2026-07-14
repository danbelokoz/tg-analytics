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
