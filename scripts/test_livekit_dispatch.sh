#!/usr/bin/env bash
set -e
###############################################################################
### Test: LiveKit room + agent dispatch (OSS-native, via lk CLI)
###
### Mirrors Luminai's sip-socket pattern:
###   1. create_room WITH metadata (workflow_id, org_id) — the worker reads
###      workflow_id from ROOM metadata (ctx.job.room.metadata)
###   2. agent_dispatch.create_dispatch → assigns dograh-agent to the room
###
### Works on LiveKit OSS. Requires the `lk` CLI.
###############################################################################

BASE_DIR="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)"

LIVEKIT_URL="${LIVEKIT_URL:-http://localhost:7880}"
LIVEKIT_API_KEY="${LIVEKIT_API_KEY:-devkey}"
LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET:-a70f4c337479e4b153980a294b0ec1e0fb37b0e5605b43e6d865b4247b2492c6}"

AGENT_NAME="${DOGRAH_LIVEKIT_AGENT:-dograh-agent}"
WORKFLOW_ID="${1:-}"
ORG_ID="${2:-}"

usage() {
  echo "Usage: $0 <workflow_id> <org_id>"
  echo ""
  echo "  workflow_id — Dograh workflow ID (must have published version)"
  echo "  org_id      — Dograh organization ID"
  echo ""
  echo "  Example: $0 1 1"
  exit 1
}

[[ -z "$WORKFLOW_ID" || -z "$ORG_ID" ]] && usage

if [[ -f "$BASE_DIR/dograh-livekit/.env" ]]; then
  set -a && . "$BASE_DIR/dograh-livekit/.env" && set +a
fi

DOGRAH_TOKEN="${DOGRAH_INTERNAL_TOKEN:-dev-internal-token}"
DOGRAH_API="${DOGRAH_API_URL:-http://localhost:8000}"

export LIVEKIT_URL LIVEKIT_API_KEY LIVEKIT_API_SECRET

echo "━━━ Test: LiveKit Room → agent dispatch (OSS, lk CLI) ━━━"
echo ""

# Verify workflow
echo -n "Verifying workflow $WORKFLOW_ID... "
RESP=$(curl -s "$DOGRAH_API/api/internal/workflows/$WORKFLOW_ID/runtime-config" \
  -H "X-Internal-Token: $DOGRAH_TOKEN" 2>/dev/null || echo "{}")
if echo "$RESP" | grep -q '"workflow_id"'; then
  AGENT_N=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_name','unknown'))" 2>/dev/null)
  echo "OK ($AGENT_N)"
else
  echo "FAIL — check workflow_id and DOGRAH_INTERNAL_TOKEN"
  exit 1
fi

ROOM_NAME="dograh-test-$(date +%s)"
METADATA="{\"workflow_id\":${WORKFLOW_ID},\"org_id\":${ORG_ID},\"channel\":\"voice_sip\"}"

# STEP 1: create room (simple), then set metadata — worker reads workflow_id
# from ctx.job.room.metadata, so the ROOM (not just the dispatch) must carry it.
echo -n "Creating room $ROOM_NAME... "
lk room create "$ROOM_NAME" >/dev/null 2>&1 && echo "OK" || { echo "FAIL"; exit 1; }

echo -n "Setting room metadata... "
lk room update "$ROOM_NAME" --metadata "$METADATA" >/dev/null 2>&1 && echo "OK" || { echo "FAIL (lk room update)"; exit 1; }

# STEP 2: dispatch agent to room
echo -n "Dispatching agent '$AGENT_NAME' to room... "
lk dispatch create --room "$ROOM_NAME" --agent-name "$AGENT_NAME" --metadata "$METADATA" 2>&1 | grep -q "created" && echo "OK" || { echo "FAIL"; lk dispatch create --room "$ROOM_NAME" --agent-name "$AGENT_NAME" --metadata "$METADATA"; exit 1; }

echo ""
echo "✓ Room: $ROOM_NAME (workflow $WORKFLOW_ID, org $ORG_ID)"
echo "  Agent '$AGENT_NAME' dispatched — watch the worker terminal."
echo ""
echo "The worker should log: 'Session start — room=... workflow=$WORKFLOW_ID'"
echo "Then fetch config from Dograh and start the Agno workflow."