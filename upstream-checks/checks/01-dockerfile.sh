#!/usr/bin/env bash
# 01-dockerfile.sh — Verifica contrato do Dockerfile upstream
# O template depende de: base image node:22, pnpm, dist/index.js, user node (uid 1000)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/utils.sh"

UPSTREAM_DIR="${1:?Uso: $0 <upstream_dir>}"
DOCKERFILE="${UPSTREAM_DIR}/Dockerfile"

echo ""
echo "=== 01. Dockerfile ==="

# 1. Arquivo deve existir
assert_file_exists "$DOCKERFILE" "Dockerfile existe no upstream" || true

# 2. Base image node:22
assert_file_contains "$DOCKERFILE" "node:22" \
  "Dockerfile usa base image node:22" || true

# 3. pnpm como package manager
assert_file_contains "$DOCKERFILE" "pnpm" \
  "Dockerfile usa pnpm" || true

# 4. openclaw.mjs como entry point (CMD no Dockerfile usa openclaw.mjs, compose sobrescreve com dist/index.js)
assert_file_contains "$DOCKERFILE" "openclaw.mjs" \
  "Dockerfile referencia openclaw.mjs (entry point)" || true

# 5. Roda como user node (nao root)
assert_file_contains "$DOCKERFILE" "USER node" \
  "Dockerfile roda como user node" || true

# 6. UID 1000 (container precisa ser compativel com chown do firstboot.sh)
assert_file_contains "$DOCKERFILE" "1000" \
  "Dockerfile referencia UID 1000" || true
