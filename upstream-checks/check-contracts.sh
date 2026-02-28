#!/usr/bin/env bash
# check-contracts.sh — Orquestrador principal de verificação de contratos upstream
#
# Uso:
#   bash upstream-checks/check-contracts.sh [upstream_dir] [--skip-build]
#
# Se upstream_dir nao for fornecido, baixa os arquivos do GitHub automaticamente.
# Use --skip-build para pular o check 05-docker-build.sh (usado no check diario).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Exportar caminho do contracts.json para os scripts filhos
export CONTRACTS_FILE="${SCRIPT_DIR}/contracts.json"

# Source utils para gerar relatorio
source "${SCRIPT_DIR}/lib/utils.sh"

# ── Argumentos ──

UPSTREAM_DIR="${1:-}"
SKIP_BUILD=false

for arg in "$@"; do
  if [[ "$arg" == "--skip-build" ]]; then
    SKIP_BUILD=true
  fi
done

# ── Download dos arquivos upstream se necessario ──

if [[ -z "$UPSTREAM_DIR" ]] || [[ ! -d "$UPSTREAM_DIR" ]]; then
  UPSTREAM_DIR="/tmp/openclaw-upstream-check"
  rm -rf "$UPSTREAM_DIR"
  mkdir -p "$UPSTREAM_DIR"

  UPSTREAM_RAW=$(jq -r '.upstream_raw_url' "$CONTRACTS_FILE")
  FILES_TO_DOWNLOAD=("Dockerfile" "docker-compose.yml" ".env.example" "package.json")

  echo "Baixando arquivos upstream de ${UPSTREAM_RAW}..."
  for file in "${FILES_TO_DOWNLOAD[@]}"; do
    if curl -sf "${UPSTREAM_RAW}/${file}" -o "${UPSTREAM_DIR}/${file}" 2>/dev/null; then
      echo "  OK: ${file}"
    else
      echo "  MISSING: ${file}"
    fi
  done
  echo ""
fi

# ── Executar checks ──

echo "========================================="
echo "  Upstream Contract Checks"
echo "  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "========================================="

# Rodar checks estaticos (01–04)
for check_script in "${SCRIPT_DIR}"/checks/0[1-4]-*.sh; do
  if [[ -f "$check_script" ]]; then
    source "$check_script" "$UPSTREAM_DIR"
  fi
done

# Rodar check de build apenas se nao pulado
if [[ "$SKIP_BUILD" == false ]]; then
  build_script="${SCRIPT_DIR}/checks/05-docker-build.sh"
  if [[ -f "$build_script" ]]; then
    source "$build_script" "$UPSTREAM_DIR"
  fi
else
  echo ""
  echo "=== 05. Docker Build (PULADO — --skip-build) ==="
fi

# ── Relatorio ──

echo ""
echo "========================================="
echo "  Resultados"
echo "========================================="
echo -e "  ${GREEN}Passed:${NC}   ${PASS_COUNT}"
echo -e "  ${RED}Failed:${NC}   ${FAIL_COUNT}"
echo -e "  ${YELLOW}Warnings:${NC} ${WARN_COUNT}"
echo "========================================="

# Gerar relatorio markdown
generate_report "/tmp/check-report.md"

# Definir outputs para GitHub Actions
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  if [[ $FAIL_COUNT -gt 0 ]]; then
    echo "has_failures=true" >> "$GITHUB_OUTPUT"
  else
    echo "has_failures=false" >> "$GITHUB_OUTPUT"
  fi
  echo "pass_count=${PASS_COUNT}" >> "$GITHUB_OUTPUT"
  echo "fail_count=${FAIL_COUNT}" >> "$GITHUB_OUTPUT"
  echo "warn_count=${WARN_COUNT}" >> "$GITHUB_OUTPUT"
fi

# Exit code baseado nos resultados
if [[ $FAIL_COUNT -gt 0 ]]; then
  echo ""
  echo "RESULTADO: ${FAIL_COUNT} falha(s) detectada(s)!"
  exit 1
else
  echo ""
  echo "RESULTADO: Todos os checks passaram."
  exit 0
fi
