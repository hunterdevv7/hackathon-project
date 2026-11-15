#!/usr/bin/env bash
# Create the QuantumFair server on Vultr through the Vultr API, from your laptop:
#
#   ./deploy/vultr.sh [region] [plan]          # defaults: ewr (New Jersey), vc2-1c-1gb
#
# Creates or reuses, all named "quantumfair":
#   - an SSH key (~/.ssh/quantumfair_vultr.pub)
#   - a firewall group allowing SSH (22) and HTTP (80)
#   - an Ubuntu 24.04 Cloud Compute instance in that group
# Then waits for it to boot and prints its public IP. Next: ./deploy/deploy.sh <ip>
#
# API key: export VULTR_API_KEY=..., or put it alone in deploy/.vultr-api-key
# (gitignored, never uploaded to the server).
# Cost: vc2-1c-1gb is $5/month billed hourly. Delete the instance when the event is over.
set -euo pipefail
cd "$(dirname "$0")/.."

REGION="${1:-ewr}"
PLAN="${2:-vc2-1c-1gb}"
OS_ID=2284           # Ubuntu 24.04 LTS x64
NAME=quantumfair
PUBKEY_FILE="$HOME/.ssh/quantumfair_vultr.pub"
PY="${PYTHON:-python}"

KEY="${VULTR_API_KEY:-}"
[ -z "$KEY" ] && [ -f deploy/.vultr-api-key ] && KEY="$(tr -d ' \r\n' < deploy/.vultr-api-key)"
[ -n "$KEY" ] || { echo "Set VULTR_API_KEY or create deploy/.vultr-api-key" >&2; exit 1; }
[ -f "$PUBKEY_FILE" ] || ssh-keygen -q -t ed25519 -f "${PUBKEY_FILE%.pub}" -N "" -C "quantumfair-vultr"

api() {  # api METHOD PATH [JSON]
  local method=$1 path=$2 body=${3:-}
  if [ -n "$body" ]; then
    curl -fsS -X "$method" "https://api.vultr.com/v2$path" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "$body"
  else
    curl -fsS -X "$method" "https://api.vultr.com/v2$path" -H "Authorization: Bearer $KEY"
  fi
}
json() { "$PY" -c "import json,sys; d=json.load(sys.stdin); print($1)" | tr -d '\r'; }  # Windows Python prints \r\n

echo "==> Account"
api GET /account | json "'  ' + d['account']['name'] + ' · balance ' + str(d['account']['balance']) + ' · pending ' + str(d['account']['pending_charges'])"

echo "==> SSH key"
SSHKEY_ID=$(api GET "/ssh-keys?per_page=500" | json "next((k['id'] for k in d['ssh_keys'] if k['name']=='$NAME'), '')")
if [ -z "$SSHKEY_ID" ]; then
  BODY=$("$PY" -c "import json,sys; print(json.dumps({'name': '$NAME', 'ssh_key': open(sys.argv[1]).read().strip()}))" "$PUBKEY_FILE")
  SSHKEY_ID=$(api POST /ssh-keys "$BODY" | json "d['ssh_key']['id']")
fi
echo "  $SSHKEY_ID"

echo "==> Firewall group (SSH 22, HTTP 80)"
FW_ID=$(api GET "/firewalls?per_page=500" | json "next((g['id'] for g in d['firewall_groups'] if g['description']=='$NAME'), '')")
if [ -z "$FW_ID" ]; then
  FW_ID=$(api POST /firewalls "{\"description\":\"$NAME\"}" | json "d['firewall_group']['id']")
  api POST "/firewalls/$FW_ID/rules" '{"ip_type":"v4","protocol":"tcp","subnet":"0.0.0.0","subnet_size":0,"port":"22","notes":"ssh"}' >/dev/null
  api POST "/firewalls/$FW_ID/rules" '{"ip_type":"v4","protocol":"tcp","subnet":"0.0.0.0","subnet_size":0,"port":"80","notes":"http"}' >/dev/null
  api POST "/firewalls/$FW_ID/rules" '{"ip_type":"v6","protocol":"tcp","subnet":"::","subnet_size":0,"port":"80","notes":"http"}' >/dev/null
fi
echo "  $FW_ID"

echo "==> Instance ($PLAN in $REGION, Ubuntu 24.04)"
INST_ID=$(api GET "/instances?label=$NAME&per_page=500" | json "next((i['id'] for i in d['instances'] if i['label']=='$NAME'), '')")
if [ -z "$INST_ID" ]; then
  BODY="{\"region\":\"$REGION\",\"plan\":\"$PLAN\",\"os_id\":$OS_ID,\"label\":\"$NAME\",\"hostname\":\"$NAME\",\"sshkey_id\":[\"$SSHKEY_ID\"],\"firewall_group_id\":\"$FW_ID\",\"backups\":\"disabled\",\"enable_ipv6\":true}"
  INST_ID=$(api POST /instances "$BODY" | json "d['instance']['id']")
  echo "  created $INST_ID"
else
  echo "  reusing $INST_ID"
fi

echo "==> Waiting for it to boot"
IP=""
for i in $(seq 1 90); do
  read -r STATUS POWER IP < <(api GET "/instances/$INST_ID" | json "' '.join([d['instance']['status'], d['instance']['power_status'], d['instance']['main_ip']])")
  [ "$STATUS" = active ] && [ "$POWER" = running ] && [ "$IP" != 0.0.0.0 ] && break
  sleep 5
done
[ "$STATUS" = active ] || { echo "Instance not ready after 7 minutes (status $STATUS)." >&2; exit 1; }
for i in $(seq 1 60); do
  ssh -q -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -i "${PUBKEY_FILE%.pub}" "root@$IP" true 2>/dev/null && break
  sleep 5
done
echo "Public IP: $IP"
echo "Next: ./deploy/deploy.sh $IP"
