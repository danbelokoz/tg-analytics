// Vercel Serverless Function — добавляет канал в watchlist (через service_role).
// Защита простым ключом. ENV в Vercel: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ADMIN_KEY.
export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "method not allowed" });

  const body = (typeof req.body === "object" && req.body) || {};
  const { username, key } = body;

  if (!process.env.ADMIN_KEY || key !== process.env.ADMIN_KEY)
    return res.status(401).json({ error: "неверный ключ доступа" });

  let u = String(username || "").trim();
  u = u.replace(/^https?:\/\/t\.me\//i, "").replace(/^@/, "").replace(/\/.*$/, "");
  if (!/^[a-zA-Z0-9_]{4,32}$/.test(u))
    return res.status(400).json({ error: "некорректный username (4–32 символа: буквы/цифры/_)" });

  const base = (process.env.SUPABASE_URL || "").replace(/\/$/, "");
  const sk = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!base || !sk) return res.status(500).json({ error: "сервер не сконфигурирован (нет SUPABASE env)" });

  const r = await fetch(`${base}/rest/v1/watchlist?on_conflict=username`, {
    method: "POST",
    headers: {
      apikey: sk,
      Authorization: `Bearer ${sk}`,
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates,return=minimal",
    },
    body: JSON.stringify([{ username: u, is_active: true }]),
  });
  if (!r.ok) return res.status(502).json({ error: (await r.text()).slice(0, 200) });
  return res.status(200).json({ ok: true, username: u });
}
