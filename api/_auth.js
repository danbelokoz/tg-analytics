// Общая auth-библиотека для serverless-функций (Vercel, ESM, Node 20).
// Только встроенный node:crypto — никаких npm-зависимостей (РФ-доступность:
// в рантайме сайт ходит лишь на Vercel-функции, а те — на Supabase server-side).
//
// Файл с префиксом «_» Vercel не считает роутом — это shared-модуль.
//
// ENV (задать в Vercel → Project → Settings → Environment Variables):
//   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — как в остальном проекте
//   SESSION_SECRET — длинная случайная строка (подпись cookie-сессии)
import crypto from "node:crypto";

// ── Пароли: scrypt(salt) → "saltHex:hashHex" ─────────────────────────────────
const SCRYPT_KEYLEN = 64;

export function hashPassword(password) {
  const salt = crypto.randomBytes(16);
  const hash = crypto.scryptSync(String(password), salt, SCRYPT_KEYLEN);
  return `${salt.toString("hex")}:${hash.toString("hex")}`;
}

export function verifyPassword(password, stored) {
  if (typeof stored !== "string" || !stored.includes(":")) return false;
  const [saltHex, hashHex] = stored.split(":");
  const salt = Buffer.from(saltHex, "hex");
  const expected = Buffer.from(hashHex, "hex");
  const actual = crypto.scryptSync(String(password), salt, expected.length || SCRYPT_KEYLEN);
  return expected.length === actual.length && crypto.timingSafeEqual(expected, actual);
}

// ── Сессия: HMAC-подписанный cookie (payload.signature, base64url) ────────────
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 дней
const b64u = (buf) => Buffer.from(buf).toString("base64url");

function secret() {
  const s = process.env.SESSION_SECRET;
  if (!s) throw new Error("SESSION_SECRET не задан");
  return s;
}

export function signSession(user) {
  const payload = b64u(JSON.stringify({ uid: user.id, email: user.email, role: user.role, iat: Date.now() }));
  const sig = b64u(crypto.createHmac("sha256", secret()).update(payload).digest());
  return `${payload}.${sig}`;
}

export function verifySession(token) {
  if (typeof token !== "string" || !token.includes(".")) return null;
  const [payload, sig] = token.split(".");
  const good = b64u(crypto.createHmac("sha256", secret()).update(payload).digest());
  const a = Buffer.from(sig), b = Buffer.from(good);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    if (!data.iat || Date.now() - data.iat > SESSION_TTL_MS) return null; // протухла
    return data;
  } catch {
    return null;
  }
}

const COOKIE = "sess";

export function sessionCookie(token) {
  const maxAge = Math.floor(SESSION_TTL_MS / 1000);
  return `${COOKIE}=${token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${maxAge}`;
}
export function clearCookie() {
  return `${COOKIE}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0`;
}

export function userFromReq(req) {
  const raw = req.headers.cookie || "";
  const m = raw.match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`));
  return m ? verifySession(decodeURIComponent(m[1])) : null;
}

// ── Supabase REST (service role, server-side) ────────────────────────────────
export function sbConfig() {
  const base = (process.env.SUPABASE_URL || "").replace(/\/$/, "");
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  return { base, key, ok: Boolean(base && key) };
}

export async function sb(path, { method = "GET", body, prefer } = {}) {
  const { base, key } = sbConfig();
  const headers = { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json" };
  if (prefer) headers.Prefer = prefer;
  const r = await fetch(`${base}/rest/v1/${path}`, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  });
  return r;
}

// Разбор JSON-тела POST (Vercel может отдать объект или строку).
export function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  try { return JSON.parse(req.body || "{}"); } catch { return {}; }
}

export const EMAIL_RX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
