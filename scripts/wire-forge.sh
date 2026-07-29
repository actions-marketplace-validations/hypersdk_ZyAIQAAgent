#!/usr/bin/env bash
# Copyright 2026 ZyvorAI Labs Private Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Wire the QA agent to Forge — stand up Forge locally (API gateway + web UI) and
# run the agent's suite against it. Forge is a FastAPI gateway + Vite web UI, so
# it runs without the full Rust/K8s stack (K8s-backed endpoints degrade to 500
# when no cluster is reachable — that's expected and is itself a contract finding).
#
# Usage:
#   scripts/wire-forge.sh [--forge-dir ../forge] [--key forge-dev-key] [--no-ui] [--suite-only]
#
# Env it sets for Forge:  FORGE_API_KEY (bearer), KUBECONFIG (throwaway), OIDC_ENABLED=false
set -euo pipefail

FORGE_DIR="${FORGE_DIR:-$(cd "$(dirname "$0")/../../forge" 2>/dev/null && pwd || echo ../forge)}"
KEY="${FORGE_KEY:-forge-dev-key}"
GW_PORT="${FORGE_GW_PORT:-8001}"
UI_PORT="${FORGE_UI_PORT:-3000}"
START_UI=true
SUITE_ONLY=false
AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE="${TMPDIR:-/tmp}/wire-forge"
mkdir -p "$STATE"

while [ $# -gt 0 ]; do case "$1" in
  --forge-dir) FORGE_DIR="$2"; shift 2 ;;
  --key) KEY="$2"; shift 2 ;;
  --no-ui) START_UI=false; shift ;;
  --suite-only) SUITE_ONLY=true; shift ;;
  *) echo "unknown arg $1"; exit 2 ;;
esac; done

log() { printf '\033[36m▸ %s\033[0m\n' "$*"; }

if [ "$SUITE_ONLY" = false ]; then
  # 1. throwaway kubeconfig so the gateway starts without a real cluster
  cat > "$STATE/kubeconfig.yaml" <<'EOF'
apiVersion: v1
kind: Config
clusters: [{cluster: {server: https://127.0.0.1:6443}, name: local}]
contexts: [{context: {cluster: local, user: local}, name: local}]
current-context: local
users: [{name: local, user: {}}]
EOF

  # 2. API gateway (FastAPI) — python3.13 venv (pydantic-core wheels), bearer = FORGE_API_KEY
  log "installing + starting Forge API gateway on :$GW_PORT"
  ( cd "$FORGE_DIR/services/api-gateway"
    PYBIN="$(command -v python3.13 || command -v python3)"
    [ -d .qa-venv ] || "$PYBIN" -m venv .qa-venv
    ./.qa-venv/bin/pip install -q -r requirements.txt
    KUBECONFIG="$STATE/kubeconfig.yaml" FORGE_API_KEY="$KEY" OIDC_ENABLED=false \
      ./.qa-venv/bin/uvicorn main:app --host 127.0.0.1 --port "$GW_PORT" > "$STATE/gateway.log" 2>&1 &
    echo $! > "$STATE/gateway.pid" )
  for _ in $(seq 1 30); do curl -sf -m2 "http://127.0.0.1:$GW_PORT/openapi.json" >/dev/null 2>&1 && break; sleep 1; done
  log "gateway up — $(curl -s "http://127.0.0.1:$GW_PORT/openapi.json" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["paths"]),"endpoints")')"

  # 3. web UI (Vite)
  if [ "$START_UI" = true ]; then
    log "starting Forge web UI on :$UI_PORT"
    ( cd "$FORGE_DIR/web-ui" && [ -d node_modules ] || npm ci
      npm run dev > "$STATE/webui.log" 2>&1 & echo $! > "$STATE/webui.pid" )
    for _ in $(seq 1 30); do curl -sf -m2 "http://localhost:$UI_PORT/" >/dev/null 2>&1 && break; sleep 1; done
  fi
fi

# 4. run the agent's suite against Forge
log "wiring the QA agent → Forge"
cd "$AGENT_DIR"
PY="./.venv/bin/python"

log "API contract (366-endpoint OpenAPI, bearer auth)"
$PY -m orchestrator.cli api-test "http://127.0.0.1:$GW_PORT" \
  --spec "http://127.0.0.1:$GW_PORT/openapi.json" --token "$KEY" || true

if [ "$START_UI" = true ]; then
  log "Core Web Vitals (web UI)"
  $PY -m orchestrator.cli vitals "http://localhost:$UI_PORT" || true
  log "AI test (heuristic without an LLM key; set LLM_PROVIDER for autonomy)"
  $PY -m orchestrator.cli ai-test "http://localhost:$UI_PORT" \
    --goal "open the jobs page and confirm it loads" --max-steps 6 || true
fi

cat <<EOF

$(log "Forge is wired. Endpoints:")
  API gateway   http://127.0.0.1:$GW_PORT   (bearer: $KEY)   OpenAPI: /openapi.json
  Web UI        http://localhost:$UI_PORT
  logs          $STATE/gateway.log · $STATE/webui.log
  stop          kill \$(cat $STATE/gateway.pid $STATE/webui.pid 2>/dev/null)
EOF
