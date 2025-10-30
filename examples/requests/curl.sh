#!/usr/bin/env bash
set -euo pipefail
API="http://localhost:19400/v1/mcp"
KEY="change-me"

echo "== list_tools =="
curl -sS -H "X-Api-Key: ${KEY}" -H "Content-Type: application/json" \
  -d '{"id":"1","method":"list_tools","params":{}}' "$API" | jq

echo "== call disk_space =="
curl -sS -H "X-Api-Key: ${KEY}" -H "Content-Type: application/json" \
  -d '{"id":"2","method":"call_tool","name":"disk_space","args":{"path":"/"}}' "$API" | jq
