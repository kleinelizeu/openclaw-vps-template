#!/usr/bin/env bash
# 02-docker-compose.sh — Verifica contrato do docker-compose.yml upstream
# Este é o check mais critico: o template interage extensivamente com o compose.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/utils.sh"

UPSTREAM_DIR="${1:?Uso: $0 <upstream_dir>}"
COMPOSE="${UPSTREAM_DIR}/docker-compose.yml"

echo ""
echo "=== 02. Docker Compose ==="

# 1. Arquivo deve existir
assert_file_exists "$COMPOSE" "docker-compose.yml existe" || true

# 2. Servico openclaw-gateway (usado por: app.py para up/restart/exec)
assert_file_contains "$COMPOSE" "openclaw-gateway" \
  "Servico openclaw-gateway definido" || true

# 3. Servico openclaw-cli (usado por: app.py para onboard)
assert_file_contains "$COMPOSE" "openclaw-cli" \
  "Servico openclaw-cli definido" || true

# 4. Porta 18789 (gateway — usado por: nginx, firstboot.sh, app.py health check)
assert_file_contains "$COMPOSE" "18789" \
  "Porta 18789 (gateway) configurada" || true

# 5. Porta 18790 (bridge — aberta no UFW)
assert_file_contains "$COMPOSE" "18790" \
  "Porta 18790 (bridge) configurada" || true

# 6. Variavel OPENCLAW_IMAGE (usada em firstboot.sh: OPENCLAW_IMAGE=openclaw:local)
assert_file_contains "$COMPOSE" "OPENCLAW_IMAGE" \
  "Variavel OPENCLAW_IMAGE referenciada" || true

# 7. Variavel OPENCLAW_GATEWAY_TOKEN (gerada pelo firstboot, usada pelo gateway)
assert_file_contains "$COMPOSE" "OPENCLAW_GATEWAY_TOKEN" \
  "Variavel OPENCLAW_GATEWAY_TOKEN referenciada" || true

# 8. Variavel OPENCLAW_GATEWAY_BIND (definida como 'lan' no .env)
assert_file_contains "$COMPOSE" "OPENCLAW_GATEWAY_BIND" \
  "Variavel OPENCLAW_GATEWAY_BIND referenciada" || true

# 9. Variavel OPENCLAW_CONFIG_DIR (monta /root/.openclaw no container)
assert_file_contains "$COMPOSE" "OPENCLAW_CONFIG_DIR" \
  "Variavel OPENCLAW_CONFIG_DIR referenciada" || true

# 10. Variavel OPENCLAW_WORKSPACE_DIR
assert_file_contains "$COMPOSE" "OPENCLAW_WORKSPACE_DIR" \
  "Variavel OPENCLAW_WORKSPACE_DIR referenciada" || true

# 11. Comando gateway usa node dist/index.js gateway
assert_file_contains "$COMPOSE" "dist/index.js" \
  "Comando usa dist/index.js como entry point" || true

assert_file_contains "$COMPOSE" '"gateway"' \
  "Comando do gateway inclui subcomando 'gateway'" || true

# 12. Variaveis CLAUDE (definidas vazias no firstboot.sh para evitar warnings)
assert_file_contains "$COMPOSE" "CLAUDE_AI_SESSION_KEY" \
  "Variavel CLAUDE_AI_SESSION_KEY referenciada" || true

assert_file_contains "$COMPOSE" "CLAUDE_WEB_SESSION_KEY" \
  "Variavel CLAUDE_WEB_SESSION_KEY referenciada" || true

assert_file_contains "$COMPOSE" "CLAUDE_WEB_COOKIE" \
  "Variavel CLAUDE_WEB_COOKIE referenciada" || true

# 13. Volume monta em /home/node/.openclaw
assert_file_contains "$COMPOSE" "/home/node/.openclaw" \
  "Volume monta em /home/node/.openclaw" || true
