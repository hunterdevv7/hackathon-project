#!/usr/bin/env bash
# Server side of the deploy. Run as root on a fresh Vultr Ubuntu 24.04 instance,
# from /opt/quantumfair (deploy/deploy.sh copies the code there and runs this).
# Safe to run again: every step checks or overwrites, so a redeploy is the same command.
set -euo pipefail

APP_DIR=/opt/quantumfair
APP_USER=quantumfair
cd "$APP_DIR"

echo "==> Packages (Python 3.12, venv, nginx)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip nginx curl

echo "==> App user"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"

echo "==> Python environment"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "==> .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    No .env was uploaded: created one from .env.example (QUANTUM_MODE=quantumrings, no credentials: draws fail until QR_TOKEN and QR_ACCOUNT are set)."
fi
chmod 600 .env
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> systemd service (gunicorn on 127.0.0.1:8000)"
cp deploy/quantumfair.service /etc/systemd/system/quantumfair.service
systemctl daemon-reload
systemctl enable quantumfair >/dev/null
systemctl restart quantumfair

echo "==> nginx (port 80 -> gunicorn)"
cp deploy/nginx-quantumfair.conf /etc/nginx/sites-available/quantumfair
ln -sf /etc/nginx/sites-available/quantumfair /etc/nginx/sites-enabled/quantumfair
rm -f /etc/nginx/sites-enabled/default
nginx -t -q
systemctl enable nginx >/dev/null
systemctl reload nginx || systemctl restart nginx

echo "==> Host firewall"
# Vultr's Ubuntu images ship with ufw on and only SSH allowed.
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow OpenSSH >/dev/null
  ufw allow 80/tcp >/dev/null
  echo "    ufw: SSH and HTTP allowed."
fi

echo "==> Check"
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1/health && echo
curl -fsS http://127.0.0.1/engine && echo
echo "Done. Logs: journalctl -u quantumfair -f"
