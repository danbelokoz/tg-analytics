// GET /api/status — состояние пайплайнов сбора (только для роли admin).
// Отдаёт последний прогон каждого workflow + недавнюю историю с health-флагами.
import { userFromReq, sb, sbConfig } from "./_auth.js";

export default async function handler(req, res) {
  const u = userFromReq(req);
  if (!u) return res.status(401).json({ error: "не авторизован" });
  if (u.role !== "admin") return res.status(403).json({ error: "нужны права администратора" });
  if (!sbConfig().ok) return res.status(500).json({ error: "сервер не сконфигурирован (SUPABASE env)" });

  // Последние 100 прогонов, свежие сверху.
  const r = await sb("pipeline_runs?select=*&order=finished_at.desc&limit=100");
  if (!r.ok) return res.status(502).json({ error: "ошибка БД" });
  const runs = await r.json();

  // Последний прогон по каждому workflow — это и есть «карточки статуса».
  const latest = {};
  for (const run of runs) if (!latest[run.workflow]) latest[run.workflow] = run;

  return res.status(200).json({ latest: Object.values(latest), history: runs, now: new Date().toISOString() });
}
