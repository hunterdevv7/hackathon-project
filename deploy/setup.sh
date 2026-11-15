#!/usr/bin/env bash
# Server side of the deploy. Run as root on a fresh Vultr Ubuntu 24.04 instance,
# from /opt/quantumfair (deploy/deploy.sh copies the code there and runs this).
# Safe to run again: every step checks or overwrites, so a redeploy is the same command.
#
# Besides installing the app it hardens the box: security updates, key-only SSH,
# fail2ban, and the app running as an unprivileged user that cannot modify its own code.
set -euo pipefail

APP_DIR=/opt/quantumfair
APP_USER=quantumfair
cd "$APP_DIR"

echo "==> Packages (Python, venv, nginx, fail2ban) and security updates"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip nginx curl fail2ban unattended-upgrades
apt-get upgrade -y -q -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
apt-get autoremove -y -q

echo "==> App user"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"

echo "==> Python environment"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
find "$APP_DIR" -path "$APP_DIR/.venv" -prune -o -name __pycache__ -type d -print0 | xargs -0r rm -rf
.venv/bin/python -m compileall -q backend   # bytecode is built here, as root; the app can't write it

echo "==> .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    No .env was uploaded: created one from .env.example (QUANTUM_MODE=quantumrings, no credentials: draws fail until QR_TOKEN and QR_ACCOUNT are set)."
fi

echo "==> File ownership: code owned by root, readable (not writable) by the app"
chown -R root:"$APP_USER" "$APP_DIR"
chmod -R u=rwX,g=rX,o= "$APP_DIR"
chmod 640 .env                                  # credentials: root writes, the app reads, nobody else

echo "==> systemd service (gunicorn on 127.0.0.1:8000, sandboxed)"
cp deploy/quantumfair.service /etc/systemd/system/quantumfair.service
systemctl daemon-reload
systemctl enable quantumfair >/dev/null
systemctl restart quantumfair

echo "==> nginx (port 80 -> gunicorn, rate limits, security headers)"
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

echo "==> SSH: keys only, no password logins"
# Only when a key is already installed for root, so this can never lock everyone out.
# The file sorts before cloud-init's 50-cloud-init.conf; sshd keeps the first value it sees.
if [ -s /root/.ssh/authorized_keys ]; then
  cat > /etc/ssh/sshd_config.d/10-quantumfair.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 3
LoginGraceTime 30
EOF
  if sshd -t; then
    systemctl reload ssh
    echo "    Password logins disabled; SSH key required."
  else
    rm -f /etc/ssh/sshd_config.d/10-quantumfair.conf
    echo "    sshd config check failed; SSH left unchanged." >&2
  fi
else
  echo "    No SSH key installed for root; leaving password logins on so you can still get in." >&2
fi

echo "==> fail2ban (bans an IP for an hour after 5 failed SSH logins in 10 minutes)"
cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
backend = systemd
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
EOF
systemctl enable fail2ban >/dev/null
systemctl restart fail2ban

echo "==> Automatic security updates"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
systemctl enable unattended-upgrades >/dev/null

echo "==> Check"
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1/health && echo
curl -fsS http://127.0.0.1/engine && echo
echo "Done. Logs: journalctl -u quantumfair -f"
