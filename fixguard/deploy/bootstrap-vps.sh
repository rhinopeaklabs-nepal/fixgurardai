#!/usr/bin/env bash
# FixGuard AI - VPS bootstrap for Ubuntu on Hostinger KVM 1.
#
#   scp -r fixguard root@31.97.70.188:/opt/
#   ssh root@31.97.70.188 'bash /opt/fixguard/deploy/bootstrap-vps.sh'
#
# Idempotent: safe to run again after changing code or .env.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fixguard}"
API_HOST="${API_HOST:-srv1953517.hstgr.cloud}"
CERT_EMAIL="${CERT_EMAIL:-}"

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mxx  %s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$APP_DIR" ] || die "$APP_DIR not found. Upload the project there first."
cd "$APP_DIR"

# --- 1. Docker -------------------------------------------------------------
if command -v docker >/dev/null 2>&1; then
  log "Docker already installed: $(docker --version)"
else
  log "Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi

docker compose version >/dev/null 2>&1 || die "The docker compose plugin is missing."

# --- 2. Swap ---------------------------------------------------------------
# KVM 1 has 4 GB and Chromium is spiky. Swap is the difference between a slow
# audit and the kernel killing the browser mid-run.
if ! swapon --show | grep -q .; then
  log "Adding 2 GB swap"
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=10 >/dev/null
  grep -q 'vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
else
  log "Swap already configured"
fi

# --- 3. Firewall -----------------------------------------------------------
if command -v ufw >/dev/null 2>&1; then
  log "Allowing SSH, HTTP and HTTPS"
  ufw allow 22/tcp  >/dev/null 2>&1 || true
  ufw allow 80/tcp  >/dev/null 2>&1 || true
  ufw allow 443/tcp >/dev/null 2>&1 || true
  ufw --force enable >/dev/null 2>&1 || true
fi

# --- 4. Environment --------------------------------------------------------
if [ ! -f .env ]; then
  log "Creating .env"
  KEY="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 40)"
  cat > .env <<EOF
FIXGUARD_API_KEY=${KEY}
CORS_ORIGINS=https://REPLACE-WITH-YOUR-WEB-HOSTING-DOMAIN
PUBLIC_BASE_URL=https://REPLACE-WITH-YOUR-WEB-HOSTING-DOMAIN
API_PUBLIC_URL=https://${API_HOST}
RATE_LIMIT_PER_HOUR=10
EOF
  chmod 600 .env
  printf '\n\033[1;33m!!  Edit %s/.env and replace the dashboard domain, then run this again.\033[0m\n' "$APP_DIR"
  printf '    Your generated API key is: %s\n\n' "$KEY"
else
  log ".env already present, leaving it alone"
  grep -q 'REPLACE-WITH-YOUR' .env && \
    printf '\033[1;33m!!  .env still contains a REPLACE-WITH-YOUR placeholder.\033[0m\n'
fi

# --- 5. TLS ----------------------------------------------------------------
CERT_DIR="/etc/letsencrypt/live/${API_HOST}"
if [ ! -d "$CERT_DIR" ] && [ -n "$CERT_EMAIL" ]; then
  log "Requesting a certificate for ${API_HOST}"
  command -v certbot >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y certbot; }
  # NGINX is not up yet on a first run, so use standalone on port 80.
  docker compose down 2>/dev/null || true
  certbot certonly --standalone --non-interactive --agree-tos \
    -m "$CERT_EMAIL" -d "$API_HOST" || \
    printf '\033[1;33m!!  Certificate request failed; continuing on HTTP.\033[0m\n'
fi

if [ -d "$CERT_DIR" ]; then
  log "Installing certificate into the NGINX container path"
  mkdir -p nginx/certs
  cp -L "$CERT_DIR/fullchain.pem" nginx/certs/fullchain.pem
  cp -L "$CERT_DIR/privkey.pem"   nginx/certs/privkey.pem
  chmod 644 nginx/certs/fullchain.pem
  chmod 600 nginx/certs/privkey.pem
  sed -i "s/server_name _;/server_name ${API_HOST};/" nginx/fixguard.conf || true
fi

# --- 6. Build and start ----------------------------------------------------
log "Building and starting the stack (first build pulls Chromium, be patient)"
docker compose up -d --build

log "Waiting for the API to answer"
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1/api/v1/health" >/dev/null 2>&1; then
    log "API is up"
    curl -s "http://127.0.0.1/api/v1/health"; echo
    break
  fi
  [ "$i" = 60 ] && { docker compose logs --tail=60 api; die "API did not come up."; }
  sleep 2
done

log "Done"
echo "  Health : http://${API_HOST}/api/v1/health"
echo "  Key    : $(grep FIXGUARD_API_KEY .env | cut -d= -f2)"
echo
echo "  Logs   : cd ${APP_DIR} && docker compose logs -f api"
echo "  Restart: cd ${APP_DIR} && docker compose restart"
