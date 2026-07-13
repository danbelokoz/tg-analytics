// POST /api/login — вход по e-mail/паролю, выдаёт cookie-сессию.
import { verifyPassword, signSession, sessionCookie, sb, sbConfig, readBody } from "./_auth.js";

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "method not allowed" });
  if (!sbConfig().ok) return res.status(500).json({ error: "сервер не сконфигурирован (SUPABASE env)" });

  const { email, password } = readBody(req);
  const mail = String(email || "").trim().toLowerCase();

  const r = await sb(`app_users?email=eq.${encodeURIComponent(mail)}&select=id,email,role,pass_hash`);
  if (!r.ok) return res.status(502).json({ error: "ошибка БД" });
  const user = (await r.json())[0];

  // Единый ответ на «нет юзера» и «неверный пароль» — не раскрываем, есть ли e-mail.
  if (!user || !verifyPassword(password, user.pass_hash))
    return res.status(401).json({ error: "неверный e-mail или пароль" });

  res.setHeader("Set-Cookie", sessionCookie(signSession(user)));
  return res.status(200).json({ email: user.email, role: user.role });
}
