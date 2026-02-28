#!/usr/bin/env bash
# 05-docker-build.sh — Build real do Docker (executado apenas semanalmente)
# Clona o repo upstream e tenta buildar a imagem openclaw:local

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/utils.sh"

echo ""
echo "=== 05. Docker Build (integracao) ==="

# Verificar se Docker esta disponivel
if ! command -v docker &>/dev/null; then
  report_fail "Docker disponivel" "Comando docker nao encontrado"
  exit 0
fi

UPSTREAM_REPO=$(read_contract '.upstream_repo')
CLONE_DIR="/tmp/openclaw-build-test"

# Limpar diretorio anterior
rm -rf "$CLONE_DIR"

# 1. Clonar o repositorio upstream
echo "Clonando ${UPSTREAM_REPO}..."
if git clone --depth 1 "https://github.com/${UPSTREAM_REPO}.git" "$CLONE_DIR" 2>/dev/null; then
  report_pass "Clone do repositorio upstream"
else
  report_fail "Clone do repositorio upstream" "git clone falhou"
  exit 0
fi

# 2. Build da imagem Docker
echo "Buildando imagem Docker (pode demorar)..."
if docker build -t openclaw:build-test -f "${CLONE_DIR}/Dockerfile" "$CLONE_DIR" 2>&1; then
  report_pass "Docker build da imagem openclaw"
else
  report_fail "Docker build da imagem openclaw" "docker build falhou"
  rm -rf "$CLONE_DIR"
  exit 0
fi

# 3. Verificar que a imagem existe
if docker image inspect openclaw:build-test &>/dev/null; then
  report_pass "Imagem openclaw:build-test criada"
else
  report_fail "Imagem openclaw:build-test criada" "Imagem nao encontrada apos build"
fi

# 4. Verificar que o entry point funciona
echo "Validando entry point..."
if docker run --rm openclaw:build-test node dist/index.js --help &>/dev/null; then
  report_pass "Entry point dist/index.js responde a --help"
else
  report_warn "Entry point --help" "Comando --help nao retornou sucesso (pode nao ser critico)"
fi

# Cleanup
docker rmi openclaw:build-test 2>/dev/null || true
rm -rf "$CLONE_DIR"
