#!/usr/bin/env bash
# 03-env-example.sh — Verifica contrato do .env.example upstream
# O firstboot.sh gera um .env baseado nas variaveis que o upstream espera.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/utils.sh"

UPSTREAM_DIR="${1:?Uso: $0 <upstream_dir>}"
ENV_EXAMPLE="${UPSTREAM_DIR}/.env.example"

echo ""
echo "=== 03. .env.example ==="

# 1. Arquivo deve existir
assert_file_exists "$ENV_EXAMPLE" ".env.example existe" || true

# 2. Variaveis criticas usadas pelo template
assert_file_contains "$ENV_EXAMPLE" "OPENCLAW_GATEWAY_TOKEN" \
  "OPENCLAW_GATEWAY_TOKEN documentada" || true

assert_file_contains "$ENV_EXAMPLE" "ANTHROPIC_API_KEY" \
  "ANTHROPIC_API_KEY documentada" || true

assert_file_contains "$ENV_EXAMPLE" "OPENAI_API_KEY" \
  "OPENAI_API_KEY documentada" || true

assert_file_contains "$ENV_EXAMPLE" "OPENROUTER_API_KEY" \
  "OPENROUTER_API_KEY documentada" || true

# 3. Variavel do Telegram (canal principal configurado pelo wizard)
assert_file_contains "$ENV_EXAMPLE" "TELEGRAM" \
  "Configuracao Telegram documentada" || true
