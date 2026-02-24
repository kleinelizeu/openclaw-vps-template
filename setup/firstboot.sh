#!/usr/bin/env bash
# firstboot.sh — Executa uma unica vez no primeiro boot da VPS
# Gera token, prepara .env, inicia wizard web.
set -euo pipefail

SENTINEL="/var/lib/openclaw-firstboot-done"
TOKEN_FILE="/var/lib/openclaw-token"
SETUP_DONE_FILE="/var/lib/openclaw-setup-done"
OPENCLAW_DIR="/opt/openclaw"
ENV_FILE="${OPENCLAW_DIR}/.env"

log() { echo "[openclaw-firstboot] $1" | systemd-cat -t openclaw-firstboot; echo "[openclaw-firstboot] $1"; }

# Verificar se ja rodou
if [[ -f "${SENTINEL}" ]]; then
  log "Firstboot ja executado anteriormente. Saindo."
  exit 0
fi

log "Iniciando firstboot do OpenClaw..."

# ── 1. Regenerar SSH host keys ──
log "Regenerando SSH host keys"
dpkg-reconfigure openssh-server 2>/dev/null || ssh-keygen -A
systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true

# ── 2. Regenerar machine-id ──
log "Regenerando machine-id"
if [[ ! -s /etc/machine-id ]]; then
  systemd-machine-id-setup
fi

# ── 3. Criar diretorios do OpenClaw ──
log "Criando diretorios do OpenClaw"
mkdir -p /root/.openclaw
mkdir -p /root/.openclaw/workspace
mkdir -p /root/.openclaw/cron

# ── 3b. Criar openclaw.json com gateway.mode=local ──
log "Criando openclaw.json com gateway.mode=local"
cat > /root/.openclaw/openclaw.json <<OCJSON
{
  "gateway": {
    "mode": "local",
    "controlUi": {
      "dangerouslyDisableDeviceAuth": true,
      "dangerouslyAllowHostHeaderOriginFallback": true
    }
  }
}
OCJSON

# Permissoes para o user node (UID 1000) do container Docker
chown -R 1000:1000 /root/.openclaw

# ── 4. Gerar token de acesso ──
log "Gerando token de acesso"
GATEWAY_TOKEN=$(openssl rand -hex 32)
echo "${GATEWAY_TOKEN}" > "${TOKEN_FILE}"
chmod 600 "${TOKEN_FILE}"

# ── 5. Escrever .env inicial ──
log "Escrevendo .env em ${ENV_FILE}"
cat > "${ENV_FILE}" <<EOF
# OpenClaw Environment — gerado automaticamente pelo firstboot
# Editado pelo wizard web apos setup

# Imagem Docker
OPENCLAW_IMAGE=openclaw:local

# Token de acesso ao gateway (64 chars hex)
OPENCLAW_GATEWAY_TOKEN=${GATEWAY_TOKEN}

# Bind: lan = acessivel pela rede (necessario para VPS)
OPENCLAW_GATEWAY_BIND=lan

# Diretorios (CONFIG_DIR monta em /home/node/.openclaw no container)
OPENCLAW_CONFIG_DIR=/root/.openclaw
OPENCLAW_WORKSPACE_DIR=/root/.openclaw/workspace

# API Keys — serao preenchidas pelo wizard web
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=

# Variaveis opcionais (evita warnings do docker-compose)
CLAUDE_AI_SESSION_KEY=
CLAUDE_WEB_SESSION_KEY=
CLAUDE_WEB_COOKIE=
EOF

chmod 600 "${ENV_FILE}"

# ── 6. Iniciar Docker ──
log "Garantindo que Docker esta rodando"
systemctl start docker

# ── 7. Marcar firstboot como concluido ──
touch "${SENTINEL}"
log "Firstboot concluido. Token salvo em ${TOKEN_FILE}"
log "Wizard web sera iniciado pelo systemd."
