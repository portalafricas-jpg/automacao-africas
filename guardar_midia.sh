#!/usr/bin/env bash
# Guarda vídeos no galho "midia" (fora do histórico principal). Apagados sozinhos após 7 dias.
# Uso: bash guardar_midia.sh "mensagem" caminho/relativo/1.mp4 [caminho/relativo/2.mp4 ...]
# Os caminhos são relativos à raiz do repositório e o arquivo precisa existir nesse caminho.
set -euo pipefail
MSG="$1"; shift
RAIZ="$(cd "$(dirname "$0")" && pwd)"
URL="$(git -C "$RAIZ" remote get-url origin)"
if [ -n "${GITHUB_ACTIONS:-}" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
  URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}"
fi
TMP="$(mktemp -d)"
if git ls-remote --exit-code --heads "$URL" midia >/dev/null 2>&1; then
  git clone -q --depth 1 --branch midia "$URL" "$TMP/m"
else
  git init -q "$TMP/m"; git -C "$TMP/m" checkout -q --orphan midia; git -C "$TMP/m" remote add origin "$URL"
fi
for f in "$@"; do
  mkdir -p "$TMP/m/$(dirname "$f")"; cp "$RAIZ/$f" "$TMP/m/$f"
done
cd "$TMP/m"
git config user.name "${GIT_AUTHOR_NAME:-robo-africas}"
git config user.email "${GIT_AUTHOR_EMAIL:-robo-africas@users.noreply.github.com}"
git add -f -- "$@"
git diff --cached --quiet && { echo "Nada novo para guardar."; exit 0; }
git commit -qm "$MSG"
for i in 1 2 3 4 5; do
  git push -q origin HEAD:midia && { echo "Guardado no galho midia: $*"; exit 0; }
  sleep 5; git pull -q --rebase origin midia || true
done
exit 1
