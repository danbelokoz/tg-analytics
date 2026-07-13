// POST /api/register — регистрация нового пользователя (роль user), выдаёт сессию.
import { hashPassword, signSession, sessionCookie, sb, sbConfig, readBody, EMAIL_RX } from "./_auth.js";

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "method not allowed" });
  if (!sbConfig().ok) return res.status(500).json({ error: "сервер не сконфигурирован (SUPABASE env)" });

  const { email, password } = readBody(req);
  const mail = String(email || "").trim().toLowerCase();
  if (!EMAIL_RX.test(mail)) return res.status(400).json({ error: "некорректный e-mail" });
  if (String(password || "").length < 8) return res.status(400).json({ error: "пароль минимум 8 символов" });

  // уже занят?
  const exists = await sb(`app_users?email=eq.${encodeURIComponent(mail)}&select=id`);
  if (exists.ok && (await exists.json()).length) return res.status(409).json({ error: "e-mail уже зарегистрирован" });

  const ins = await sb("app_users", {
    method: "POST",
    prefer: "return=representation",
    body: [{ email: mail, pass_hash: hashPassword(password), role: "user" }],
  });
  if (!ins.ok) return res.status(502).json({ error: (await ins.text()).slice(0, 200) });
  const user = (await ins.json())[0];

  res.setHeader("Set-Cookie", sessionCookie(signSession(user)));
  return res.status(200).json({ email: user.email, role: user.role });
}
