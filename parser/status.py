"""Статус прогонов пайплайна → Supabase (таблица pipeline_runs).

Питает админ-дешборд «последнее обновление / успех / ошибки». Пишется в конце
скрейпа и НИКОГДА не должен ронять сам сбор: без Supabase-env — тихий no-op,
любая ошибка проглатывается.
"""
import os
import json
import urllib.request
import urllib.error

_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""


def _enabled():
    return bool(_URL and _KEY)


def _headers(extra=None):
    h = {"apikey": _KEY, "Authorization": f"Bearer {_KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def prev_total(workflow):
    """Total прошлого прогона этого workflow (для health-check) или None."""
    if not _enabled():
        return None
    try:
        url = (f"{_URL}/rest/v1/pipeline_runs?workflow=eq.{workflow}"
               f"&select=total&order=finished_at.desc&limit=1")
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=15) as r:
            rows = json.loads(r.read().decode())
        return rows[0]["total"] if rows else None
    except Exception:  # noqa: BLE001
        return None


def record(workflow, *, total, failed=0, prev=None, error=None, meta=None):
    """Пишет строку прогона. ok вычисляется: нет фатальной ошибки и нет резкого
    (>50%) падения total относительно прошлого прогона."""
    if not _enabled():
        print(f"[status] Supabase не сконфигурирован — пропуск ({workflow})")
        return
    ok = error is None
    warn = None
    if prev and total is not None and total < prev * 0.5:
        ok, warn = False, f"резкое падение: было {prev}, стало {total}"
    row = {
        "workflow": workflow, "ok": ok, "total": total, "prev_total": prev,
        "failed": failed, "error": error or warn, "meta": meta,
    }
    try:
        req = urllib.request.Request(
            f"{_URL}/rest/v1/pipeline_runs",
            data=json.dumps([row]).encode(),
            headers=_headers({"Prefer": "return=minimal"}), method="POST")
        urllib.request.urlopen(req, timeout=15).read()
        print(f"[status] записан прогон {workflow}: ok={ok} total={total} failed={failed}")
    except Exception as e:  # noqa: BLE001
        print(f"[status] не удалось записать прогон: {e}")
