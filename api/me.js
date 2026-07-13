// GET /api/me — текущий пользователь из cookie-сессии (или 401).
import { userFromReq } from "./_auth.js";

export default async function handler(req, res) {
  const u = userFromReq(req);
  if (!u) return res.status(401).json({ error: "не авторизован" });
  return res.status(200).json({ email: u.email, role: u.role });
}
