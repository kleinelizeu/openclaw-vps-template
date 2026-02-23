#!/usr/bin/env bash
# build-template.sh — Prepara uma VM Ubuntu 24.04 como template VPS com OpenClaw
# Rodar como root em uma VM limpa antes de converter em template QCOW2.
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

# ── 1. Atualizar sistema e instalar pacotes base ──
log "Atualizando sistema e instalando pacotes base"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y \
  curl wget git jq ufw fail2ban \
  nginx \
  python3 python3-pip python3-venv \
  ca-certificates gnupg lsb-release \
  openssl

# ── 2. Instalar Docker CE + Compose v2 ──
log "Instalando Docker CE"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker

log "Docker instalado: $(docker --version)"
log "Compose instalado: $(docker compose version)"

# ── 3. Clonar OpenClaw e pre-buildar imagem Docker ──
log "Clonando OpenClaw em ${OPENCLAW_DIR}"
if [[ -d "${OPENCLAW_DIR}" ]]; then
  rm -rf "${OPENCLAW_DIR}"
fi
git clone "${OPENCLAW_REPO}" "${OPENCLAW_DIR}"

log "Buildando imagem Docker openclaw:local"
cd "${OPENCLAW_DIR}"
docker build -t openclaw:local -f Dockerfile .

# ── 4. Instalar wizard web (Flask + Gunicorn) ──
log "Instalando wizard web de setup"
mkdir -p "${SETUP_DIR}"
cp "${SCRIPT_DIR}/setup/app.py" "${SETUP_DIR}/app.py"
cp "${SCRIPT_DIR}/setup/firstboot.sh" "${SETUP_DIR}/firstboot.sh"
cp "${SCRIPT_DIR}/setup/requirements.txt" "${SETUP_DIR}/requirements.txt"
chmod +x "${SETUP_DIR}/firstboot.sh"

python3 -m venv "${SETUP_DIR}/venv"
"${SETUP_DIR}/venv/bin/pip" install --no-cache-dir -r "${SETUP_DIR}/requirements.txt"

# ── 5. Instalar units systemd ──
log "Instalando servicos systemd"
cp "${SCRIPT_DIR}/systemd/openclaw-firstboot.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/systemd/openclaw-setup-web.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable openclaw-firstboot.service
systemctl enable openclaw-setup-web.service

# ── 6. Instalar MOTD ──
log "Configurando MOTD"
cp "${SCRIPT_DIR}/config/99-openclaw-motd" /etc/update-motd.d/99-openclaw-motd
chmod +x /etc/update-motd.d/99-openclaw-motd

# ── 7. Configurar Nginx (desabilitado por default, ativado pos-setup) ──
log "Configurando Nginx"
rm -f /etc/nginx/sites-enabled/default
cp "${SCRIPT_DIR}/config/openclaw-nginx.conf" /etc/nginx/sites-available/openclaw
# Nao ativa o site agora — sera ativado pelo wizard apos setup
systemctl disable nginx
systemctl stop nginx

# ── 8. Configurar firewall UFW ──
log "Configurando firewall UFW"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # Wizard / Nginx
ufw allow 18789/tcp # OpenClaw Gateway
ufw allow 18790/tcp # OpenClaw Bridge
ufw --force enable

# ── 9. Configurar fail2ban ──
log "Configurando fail2ban"
systemctl enable fail2ban
systemctl start fail2ban

# ── 10. Limpar estado para template ──
log "Limpando estado para conversao em template"

# Parar Docker (containers nao devem rodar no template)
docker system prune -af --volumes 2>/dev/null || true
systemctl stop docker

# Remover SSH host keys (serao regenerados no firstboot)
rm -f /etc/ssh/ssh_host_*

# Limpar machine-id (sera regenerado no boot)
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id

# Limpar cloud-init (se presente)
if command -v cloud-init &>/dev/null; then
  cloud-init clean --logs --seed
fi

# Limpar logs
find /var/log -type f -name "*.log" -exec truncate -s 0 {} \;
journalctl --rotate --vacuum-time=1s 2>/dev/null || true

# Limpar cache apt
apt-get clean
rm -rf /var/lib/apt/lists/*

# Limpar historico de comandos
rm -f /root/.bash_history
history -c 2>/dev/null || true

# Limpar /tmp
rm -rf /tmp/* /var/tmp/*

# Remover sentinel do firstboot (garantir que roda no proximo boot)
rm -f /var/lib/openclaw-firstboot-done
rm -f /var/lib/openclaw-token
rm -f /var/lib/openclaw-setup-done

log "Template preparado com sucesso!"
log "Proximo passo: desligue a VM (shutdown -h now) e converta em template QCOW2"
