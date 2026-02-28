#!/usr/bin/env bash
# utils.sh — Biblioteca de asserções para verificação de contratos upstream
# Usado por todos os scripts em upstream-checks/checks/

set -euo pipefail

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Contadores globais (inicializados apenas uma vez)
PASS_COUNT=${PASS_COUNT:-0}
FAIL_COUNT=${FAIL_COUNT:-0}
WARN_COUNT=${WARN_COUNT:-0}
FAILURES="${FAILURES:-}"
REPORT_LINES="${REPORT_LINES:-}"

# ── Funções de report ──

report_pass() {
  local check_name="$1"
  PASS_COUNT=$((PASS_COUNT + 1))
  echo -e "${GREEN}[PASS]${NC} ${check_name}"
  REPORT_LINES="${REPORT_LINES}\n- :white_check_mark: ${check_name}"
}

report_fail() {
  local check_name="$1"
  local reason="${2:-}"
  FAIL_COUNT=$((FAIL_COUNT + 1))
  echo -e "${RED}[FAIL]${NC} ${check_name}: ${reason}"
  FAILURES="${FAILURES}\n- ${check_name}: ${reason}"
  REPORT_LINES="${REPORT_LINES}\n- :x: **${check_name}**: ${reason}"
}

report_warn() {
  local check_name="$1"
  local reason="${2:-}"
  WARN_COUNT=$((WARN_COUNT + 1))
  echo -e "${YELLOW}[WARN]${NC} ${check_name}: ${reason}"
  REPORT_LINES="${REPORT_LINES}\n- :warning: ${check_name}: ${reason}"
}

# ── Funções de asserção ──

assert_file_exists() {
  local file_path="$1"
  local check_name="${2:-File exists: $(basename "$file_path")}"

  if [[ -f "$file_path" ]]; then
    report_pass "$check_name"
    return 0
  else
    report_fail "$check_name" "Arquivo nao encontrado: $file_path"
    return 1
  fi
}

assert_file_contains() {
  local file_path="$1"
  local search_string="$2"
  local check_name="${3:-Contains '$search_string' in $(basename "$file_path")}"

  if [[ ! -f "$file_path" ]]; then
    report_fail "$check_name" "Arquivo nao existe: $file_path"
    return 1
  fi

  if grep -q "$search_string" "$file_path" 2>/dev/null; then
    report_pass "$check_name"
    return 0
  else
    report_fail "$check_name" "'$search_string' nao encontrado em $(basename "$file_path")"
    return 1
  fi
}

assert_file_not_contains() {
  local file_path="$1"
  local search_string="$2"
  local check_name="${3:-Does not contain '$search_string' in $(basename "$file_path")}"

  if [[ ! -f "$file_path" ]]; then
    report_warn "$check_name" "Arquivo nao existe: $file_path (nao pode verificar)"
    return 0
  fi

  if grep -q "$search_string" "$file_path" 2>/dev/null; then
    report_fail "$check_name" "'$search_string' encontrado em $(basename "$file_path") (nao esperado)"
    return 1
  else
    report_pass "$check_name"
    return 0
  fi
}

# ── Funções auxiliares ──

# Lê um valor do contracts.json usando jq
read_contract() {
  local jq_filter="$1"
  local contracts_file="${CONTRACTS_FILE:-upstream-checks/contracts.json}"
  jq -r "$jq_filter" "$contracts_file" 2>/dev/null
}

# Lê um array do contracts.json como linhas
read_contract_array() {
  local jq_filter="$1"
  local contracts_file="${CONTRACTS_FILE:-upstream-checks/contracts.json}"
  jq -r "$jq_filter | .[]" "$contracts_file" 2>/dev/null
}

# Gera relatório final em markdown
generate_report() {
  local report_file="${1:-/tmp/check-report.md}"
  local upstream_repo
  upstream_repo=$(read_contract '.upstream_repo')

  cat > "$report_file" <<EOF
## Upstream Compatibility Report

**Upstream**: [${upstream_repo}](https://github.com/${upstream_repo})
**Data**: $(date -u '+%Y-%m-%d %H:%M UTC')
**Resultado**: ${PASS_COUNT} passed, ${FAIL_COUNT} failed, ${WARN_COUNT} warnings

### Detalhes
$(echo -e "$REPORT_LINES")

### Falhas Detectadas
$(if [[ -n "$FAILURES" ]]; then echo -e "$FAILURES"; else echo "Nenhuma falha detectada."; fi)

### Acao Necessaria

Verifique as mudancas no repositorio upstream e atualize o template conforme necessario:
- [Commits recentes](https://github.com/${upstream_repo}/commits/main)
- [Dockerfile](https://github.com/${upstream_repo}/blob/main/Dockerfile)
- [docker-compose.yml](https://github.com/${upstream_repo}/blob/main/docker-compose.yml)

---
*Gerado automaticamente por upstream-checks*
EOF

  echo ""
  echo "Relatorio salvo em: $report_file"
}

# Retorna exit code baseado nos resultados
get_exit_code() {
  if [[ $FAIL_COUNT -gt 0 ]]; then
    return 1
  fi
  return 0
}
