#!/usr/bin/env bash
# Коммитит обновлённые data/*.json обратно в main. Пуш триггерит редеплой Vercel.
# Путь data/ не входит в триггеры workflow'ов, поэтому повторного запуска CI не будет.
# Без [skip ci] в сообщении — иначе Vercel пропустит деплой.
set -euo pipefail

git config user.name  "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

git add data/
if git diff --cached --quiet; then
  echo "data/ без изменений — коммит не нужен."
  exit 0
fi

git commit -m "chore(data): refresh static JSON snapshots"

# Два workflow'а (analyze/jobs) могут пушить одновременно — ребейзим и повторяем.
for attempt in 1 2 3; do
  if git pull --rebase --autostash origin main && git push; then
    echo "Запушено (попытка $attempt)."
    exit 0
  fi
  echo "Пуш не удался (попытка $attempt), повтор…"
  sleep $((attempt * 3))
done

echo "Не удалось запушить data/ после 3 попыток." >&2
exit 1
