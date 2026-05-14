#!/usr/bin/env bash
set -euo pipefail

APP_ENTRYPOINT="main.py"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

log() {
  printf "\033[1;34m[run]\033[0m %s\n" "$*"
}

success() {
  printf "\033[1;32m[ok]\033[0m %s\n" "$*"
}

fail() {
  printf "\033[1;31m[error]\033[0m %s\n" "$*" >&2
}

install_uv() {
  log "uv was not found. Installing uv..."

  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    fail "uv is not installed, and neither curl nor wget is available."
    exit 1
  fi

  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

  if ! command -v uv >/dev/null 2>&1; then
    fail "uv installation finished, but uv is still not on PATH. Open a new shell or add ~/.local/bin to PATH."
    exit 1
  fi

  success "uv installed: $(uv --version)"
}

main() {
  cd "$(dirname "$0")"

  log "Starting Data Dash"
  log "Project root: $(pwd)"

  if ! command -v uv >/dev/null 2>&1; then
    install_uv
  else
    success "uv found: $(uv --version)"
  fi

  log "Syncing Python environment..."
  uv sync
  success "Environment is ready."

  log "Launching Streamlit on port ${STREAMLIT_PORT}..."
  log "Open http://localhost:${STREAMLIT_PORT}"
  exec uv run streamlit run "$APP_ENTRYPOINT" --server.port "$STREAMLIT_PORT"
}

main "$@"
