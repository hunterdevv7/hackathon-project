# Security

QuantumFair is a public demo: anyone can open the page and call the API. It stores no
user data and keeps nothing between requests except the last batch of bits per source.
What needs protecting is the server itself and the two credentials it holds.

## Secrets
| Secret | Where it lives | Never |
|---|---|---|
| Quantum Rings token + account (`QR_TOKEN`, `QR_ACCOUNT`) | `.env` on your laptop; `/opt/quantumfair/.env` on the server (`root:quantumfair`, mode 640) | committed, pasted in chat, or sent anywhere but over SSH by `deploy/deploy.sh --with-env` |
| Vultr API key | `deploy/.vultr-api-key` on your laptop | committed or uploaded to the server |

Both files are gitignored, and CI fails if either is ever tracked or a token shows up
in the code. If a secret leaks: revoke it at quantumrings.com or in the Vultr dashboard,
issue a new one, update `.env` / `deploy/.vultr-api-key`, and redeploy.

## What the server enforces
- **SSH:** key only (`~/.ssh/quantumfair_vultr`); password logins are disabled, and
  fail2ban bans an IP for an hour after 5 failed attempts.
- **Firewall:** Vultr's group and ufw both allow only TCP 22 and 80.
- **Patches:** `setup.sh` applies all updates on each deploy; unattended-upgrades
  installs security updates daily in between.
- **The app process:** runs as the unprivileged `quantumfair` user inside a systemd
  sandbox (read-only filesystem, no new privileges, no device or kernel access,
  syscall filter, memory cap). The code and `.env` are owned by root, so a compromised
  app cannot change its own code or credentials.
- **nginx:** hides its version, caps request bodies at 64 KB, rate-limits each client
  IP (10 API requests/s, 20 page requests/s, 20 connections), refuses dotfile paths,
  and sends a strict Content-Security-Policy (scripts only from this site), plus
  `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` and `Permissions-Policy`.
- **The API:** validates every parameter, returns JSON errors only (no stack traces or
  HTML), accepts no cross-origin browser calls unless `CORS_ORIGINS` is set, and never
  falls back to mock bits when the quantum engine fails.

## Known limits
- **No HTTPS.** The demo is served over plain HTTP on a bare IP, because certificates
  need a domain name. If the team gets one, point it at the server and run
  `certbot --nginx`; the rest of the setup is unchanged.
- **Rate limits are per IP**, so a distributed flood could still slow the single-CPU
  box. Scale the Vultr plan up if that becomes a problem.

## Reporting
Found something? Open an issue on the repository or tell a team member directly:
Adrian Spencer, Adriel Reyes, Hasset Admasu, Hunter Burk.
