#!/usr/bin/env bash
# 04-cli-entrypoint.sh — Verifica contrato da interface CLI do OpenClaw
# O app.py executa comandos docker compose exec/run com subcomandos especificos.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/utils.sh"

UPSTREAM_DIR="${1:?Uso: $0 <upstream_dir>}"

echo ""
echo "=== 04. CLI Entrypoint ==="

# O compose referencia dist/index.js como entry point.
# Verificamos no Dockerfile e docker-compose.yml que os comandos esperados existem.

DOCKERFILE="${UPSTREAM_DIR}/Dockerfile"
COMPOSE="${UPSTREAM_DIR}/docker-compose.yml"

# 1. Dockerfile deve ter o symlink ou referencia ao openclaw binary
if [[ -f "$DOCKERFILE" ]]; then
  assert_file_contains "$DOCKERFILE" "openclaw" \
    "Dockerfile referencia 'openclaw' (binary ou link)" || true
fi

# 2. Entry point dist/index.js no compose
if [[ -f "$COMPOSE" ]]; then
  assert_file_contains "$COMPOSE" "dist/index.js" \
    "docker-compose.yml usa dist/index.js como entry point" || true
fi

# 3. Verificar que o package.json existe (indica que o build funciona)
PACKAGE="${UPSTREAM_DIR}/package.json"
if [[ -f "$PACKAGE" ]]; then
  assert_file_exists "$PACKAGE" "package.json existe" || true

  # Verificar que tem scripts de build
  assert_file_contains "$PACKAGE" '"build"' \
    "package.json tem script 'build'" || true
else
  # package.json nao foi baixado — nao eh erro critico
  report_warn "package.json" "Nao baixado neste check (apenas Dockerfile e compose)"
fi

# 4. Verificar que o Dockerfile produz o entry point esperado
if [[ -f "$DOCKERFILE" ]]; then
  # O Dockerfile deve ter um CMD ou ENTRYPOINT que usa dist/index.js ou openclaw
  if grep -qE '(CMD|ENTRYPOINT).*dist/index\.js' "$DOCKERFILE" 2>/dev/null || \
     grep -qE '(CMD|ENTRYPOINT).*openclaw' "$DOCKERFILE" 2>/dev/null; then
    report_pass "Dockerfile CMD/ENTRYPOINT usa dist/index.js ou openclaw"
  else
    report_fail "Dockerfile CMD/ENTRYPOINT" \
      "Nao encontrou CMD ou ENTRYPOINT com dist/index.js ou openclaw"
  fi
fi
