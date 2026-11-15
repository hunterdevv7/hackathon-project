#!/usr/bin/env bash
# Deploy this working copy to a server, from your laptop (Git Bash, macOS or Linux):
#
#   ./deploy/deploy.sh <server-ip> [--with-env]
#
# Copies the repo's files (tracked plus new ones, minus anything .gitignore'd such
# as .venv and .env) to /opt/quantumfair and runs deploy/setup.sh there as root.
# Nothing has to be committed or pushed first.
#   --with-env   also upload your local .env (Quantum Rings credentials). It's sent
#                over SSH only, and stored on the server readable by the app alone.
# SSH key: set SSH_KEY to use a specific one (default: ~/.ssh/quantumfair_vultr if present).
set -euo pipefail

HOST="${1:?usage: deploy/deploy.sh <server-ip> [--with-env]}"
WITH_ENV="${2:-}"
cd "$(dirname "$0")/.."

KEY="${SSH_KEY:-$HOME/.ssh/quantumfair_vultr}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
[ -f "$KEY" ] && SSH_OPTS+=(-i "$KEY")
REMOTE="root@$HOST"

echo "==> Copying code to $REMOTE:/opt/quantumfair"
FILES=$(git ls-files --cached --others --exclude-standard)
# shellcheck disable=SC2086
tar -czf - $FILES | ssh "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p /opt/quantumfair && tar -xzf - -C /opt/quantumfair"

if [ "$WITH_ENV" = "--with-env" ]; then
  [ -f .env ] || { echo "No .env here to upload." >&2; exit 1; }
  echo "==> Uploading .env"
  scp -q "${SSH_OPTS[@]}" .env "$REMOTE:/opt/quantumfair/.env"
fi

echo "==> Running setup on the server"
ssh "${SSH_OPTS[@]}" "$REMOTE" "bash /opt/quantumfair/deploy/setup.sh"

echo "==> From here"
curl -fsS -m 10 "http://$HOST/health" && echo && echo "Live: http://$HOST/"
