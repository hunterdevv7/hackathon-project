# Deploying QuantumFair on Vultr

**Live demo:** http://144.202.9.26/ (Vultr `vc2-1c-1gb`, New Jersey; destroy it after the event)

One Vultr Cloud Compute instance runs everything: Ubuntu 24.04, gunicorn running the Flask app (which serves both the page and the API), and nginx on port 80 in front of it. The page calls the API on the same address, so there's no CORS to configure. Quantum draws run through the Quantum Rings SDK on the instance's CPU.

`setup.sh` also hardens the box on every deploy: security updates, key-only SSH with fail2ban, a sandboxed service user that can't modify the code, and nginx rate limits and security headers. [SECURITY.md](SECURITY.md) has the full list and what to do if a credential leaks.

```
browser ──80──> nginx ──127.0.0.1:8000──> gunicorn (2 workers) ──> Flask: page + API ──> QuantumRingsLib
```

## What's in `deploy/`
| File | Runs on | What it does |
|---|---|---|
| `vultr.sh` | your laptop | Uses the Vultr API to create the SSH key, the firewall group (ports 22 and 80) and the instance, then prints the public IP |
| `deploy.sh` | your laptop | Copies this working copy to `/opt/quantumfair` over SSH and runs `setup.sh` there. Nothing has to be pushed first. |
| `setup.sh` | the server | Installs Python and nginx, creates the venv, installs `requirements.txt`, and installs the systemd service and the nginx site. Safe to run again. |
| `quantumfair.service` | the server | systemd unit for gunicorn, sandboxed (read-only filesystem, no privileges, memory cap). It restarts on crash and starts at boot, so the app survives SSH disconnects and reboots. |
| `nginx-quantumfair.conf` | the server | Port 80 forwarding to gunicorn, with per-IP rate limits, a 64 KB body cap and security headers (CSP and friends) |

The scripts need bash, ssh and curl. On Windows, use Git Bash.

## 1. Vultr account and API key
1. Before paying for anything, check the hacker packet or the MLH page for a Vultr promo code. Sign up at vultr.com and apply the code under **Billing**.
2. Go to **Account → API**, enable the API and copy the key. Under **Access Control**, allow your current IP, or "Any IPv4" for the weekend.
3. Save the key in `deploy/.vultr-api-key`. The file is gitignored and is never uploaded. You can also `export VULTR_API_KEY=...` in your shell instead.

## 2. Create the server
```bash
./deploy/vultr.sh              # region ewr (New Jersey), plan vc2-1c-1gb
./deploy/vultr.sh ord          # or pick another region, e.g. Chicago
```
- **Plan:** `vc2-1c-1gb` is 1 vCPU and 1 GB of RAM for $5/month, billed hourly. A hackathon weekend costs well under $1. If your account has Vultr's free tier, use `./deploy/vultr.sh sea vc2-1c-0.5gb-free` (available in sea, fra and mia).
- **What it prints:** the account balance, then the public IP once SSH answers. Running it again reuses everything named `quantumfair`.

**In the dashboard instead:** go to Deploy → Cloud Compute → Shared CPU, choose Ubuntu 24.04 and the smallest plan with IPv4, and add the public key from `~/.ssh/quantumfair_vultr.pub`. Under **Network → Firewall**, create a group allowing TCP 22 and TCP 80 and attach it to the instance.

## 3. Deploy the app
```bash
./deploy/deploy.sh <ip> --with-env    # uploads .env with QUANTUM_MODE=quantumrings, QR_TOKEN, QR_ACCOUNT
./deploy/deploy.sh <ip>               # without credentials: the page shows "Quantum Rings unavailable" and draws nothing
```
The last line prints `Live: http://<ip>/`. To redeploy after changes, run the same command again.

## 4. Check it
- **The page:** open `http://<ip>/`. On the live demo's Quantum draw side, the pill should read **Quantum Rings SDK**. "Quantum Rings unavailable" means the credentials are missing or wrong.
- **The API:** `curl http://<ip>/engine` should return `{"engine": "quantumrings", "ready": true, ...}`.
- **Logs:** `ssh -i ~/.ssh/quantumfair_vultr root@<ip> journalctl -u quantumfair -f`
- **Restart:** `ssh -i ~/.ssh/quantumfair_vultr root@<ip> systemctl restart quantumfair`

## 5. After the event
Delete the instance in the dashboard (Server → Settings → Destroy) so billing stops. The firewall group and SSH key cost nothing.
