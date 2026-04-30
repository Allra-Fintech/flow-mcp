#!/usr/bin/env bash
set -euo pipefail

# One-shot installer for flow-mcp.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
#
# Override the source repo if needed:
#   FLOW_MCP_REPO_URL=git@github.com:Allra-Fintech/flow-mcp.git bash install.sh

REPO_URL="${FLOW_MCP_REPO_URL:-git@github.com:Allra-Fintech/flow-mcp.git}"
INSTALL_DIR="${FLOW_MCP_INSTALL_DIR:-$HOME/.flow-mcp/app}"
SERVER_NAME="${FLOW_MCP_SERVER_NAME:-flow}"
CONFIGURE_HERMES="${FLOW_MCP_CONFIGURE_HERMES:-1}"
LOGIN="${FLOW_MCP_LOGIN:-1}"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required but was not found." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

mkdir -p "$(dirname "$INSTALL_DIR")"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating flow-mcp in $INSTALL_DIR ..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  if [ -z "$REPO_URL" ]; then
    echo "FLOW_MCP_REPO_URL is empty." >&2
    exit 1
  fi
  echo "Cloning flow-mcp from $REPO_URL to $INSTALL_DIR ..."
  rm -rf "$INSTALL_DIR"
  if [ -d "$REPO_URL" ]; then
    mkdir -p "$INSTALL_DIR"
    (cd "$REPO_URL" && tar --exclude .venv --exclude .git --exclude __pycache__ --exclude .pytest_cache -cf - .) | (cd "$INSTALL_DIR" && tar -xf -)
  else
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
fi

cd "$INSTALL_DIR"
uv sync

SETUP_ARGS=(setup --project-dir "$INSTALL_DIR" --server-name "$SERVER_NAME")
if [ "$LOGIN" = "1" ]; then
  SETUP_ARGS+=(--login)
fi
if [ "$CONFIGURE_HERMES" = "1" ]; then
  SETUP_ARGS+=(--configure-hermes)
fi

uv run flow-mcp-setup "${SETUP_ARGS[@]}"

echo
echo "flow-mcp installed. If Hermes was already running, restart it so MCP tools are discovered."
