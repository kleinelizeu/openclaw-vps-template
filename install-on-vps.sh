#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_REPO="https://github.com/openclaw/openclaw.git"
OPENCLAW_DIR="/opt/openclaw"
SETUP_DIR="/opt/openclaw-setup"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo -e "\n==> $1\n"; }

if [[ $EUID -ne 0 ]]; then
  echo "Erro: execute como root (sudo bash $0)"
  exit 1
fi

INSTALL_SENTINEL="/var/lib/openclaw-install-done"
if [[ -f "${INSTALL_SENTINEL}" ]]; then
  log "OpenClaw ja instalado (sentinela ${INSTALL_SENTINEL} existe). Saindo."
  exit 0
fi

log "Atualizando listas e instalando pacotes base"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  curl wget git jq ufw fail2ban \
  nginx \
  python3 python3-pip python3-venv \
  ca-certificates gnupg lsb-release \
  openssl qemu-guest-agent

log "Instalando Docker CE"
install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker

log "Docker: $(docker --version)"
log "Compose: $(docker compose version)"

log "Clonando OpenClaw em ${OPENCLAW_DIR}"
if [[ -d "${OPENCLAW_DIR}" ]]; then
  rm -rf "${OPENCLAW_DIR}"
fi
git clone "${OPENCLAW_REPO}" "${OPENCLAW_DIR}"

cd "${OPENCLAW_DIR}"
OPENCLAW_VERSION=$(git describe --tags "$(git rev-list --tags --max-count=1)" 2>/dev/null || echo "latest")
log "Usando versao: ${OPENCLAW_VERSION}"

log "Buildando imagem Docker openclaw:local (${OPENCLAW_VERSION}) — pode demorar ~10 min"
docker build -t openclaw:local -f Dockerfile .

log "Build OK (${OPENCLAW_VERSION} — $(git rev-parse --short HEAD))"

log "Instalando wizard web"
mkdir -p "${SETUP_DIR}"
cp "${SCRIPT_DIR}/setup/app.py"           "${SETUP_DIR}/app.py"
cp "${SCRIPT_DIR}/setup/firstboot.sh"     "${SETUP_DIR}/firstboot.sh"
cp "${SCRIPT_DIR}/setup/requirements.txt" "${SETUP_DIR}/requirements.txt"
cp "${SCRIPT_DIR}/setup/updater.py"       "${SETUP_DIR}/updater.py"
chmod +x "${SETUP_DIR}/firstboot.sh"

python3 -m venv "${SETUP_DIR}/venv"
"${SETUP_DIR}/venv/bin/pip" install --no-cache-dir -r "${SETUP_DIR}/requirements.txt"

log "Instalando services systemd"
cp "${SCRIPT_DIR}/systemd/openclaw-firstboot.service"  /etc/systemd/system/
cp "${SCRIPT_DIR}/systemd/openclaw-setup-web.service"  /etc/systemd/system/
cp "${SCRIPT_DIR}/systemd/openclaw-updater.service"    /etc/systemd/system/

systemctl daemon-reload
systemctl enable openclaw-firstboot.service
systemctl enable openclaw-setup-web.service
systemctl enable openclaw-updater.service

log "Instalando MOTD"
cp "${SCRIPT_DIR}/config/99-openclaw-motd" /etc/update-motd.d/99-openclaw-motd
chmod +x /etc/update-motd.d/99-openclaw-motd

log "Configurando Nginx (desativado ate o setup)"
rm -f /etc/nginx/sites-enabled/default
cp "${SCRIPT_DIR}/config/openclaw-nginx.conf" /etc/nginx/sites-available/openclaw
systemctl disable nginx || true
systemctl stop nginx || true

log "Configurando UFW"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 18789/tcp
ufw allow 18790/tcp
ufw --force enable

systemctl enable fail2ban
systemctl start fail2ban

cat > /etc/logrotate.d/openclaw <<'LOGROTATE'
/var/log/openclaw-*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
}
LOGROTATE

mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'DOCKERJSON'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
DOCKERJSON
systemctl restart docker

systemctl enable qemu-guest-agent
systemctl start qemu-guest-agent || true

log "Executando firstboot"
bash "${SETUP_DIR}/firstboot.sh"

log "Iniciando wizard web na porta 80"
systemctl start openclaw-setup-web.service

touch "${INSTALL_SENTINEL}"

log "Instalacao OpenClaw concluida com sucesso."
log "Wizard acessivel em http://<IP>/"
log "Token salvo em /var/lib/openclaw-token"
