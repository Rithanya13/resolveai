#!/usr/bin/env bash
# End-to-end check against a running deployment (CI runs this on a kind
# cluster). Expects the api on :8000 and web on :3000, e.g. via
#   kubectl -n resolveai port-forward svc/api 8000:8000 &
#   kubectl -n resolveai port-forward svc/web 3000:3000 &
set -euo pipefail

API=${API_URL:-http://localhost:8000}
WEB=${WEB_URL:-http://localhost:3000}

json() { python3 -c "import sys,json; print(json.load(sys.stdin)$1)"; }

echo "health: $(curl -fsS "$API/health")"

# A high-value refund must pause for a human, survive a GET, and resume on approval.
incident=$(curl -fsS -X POST "$API/incidents" -H 'Content-Type: application/json' -d '{
  "customer_id": "cust_1004",
  "subject": "Order never arrived, need refund",
  "description": "My order never arrived per tracking, I want a refund immediately."
}')
id=$(echo "$incident" | json "['incident_id']")
status=$(echo "$incident" | json "['status']")
[ "$status" = "pending_human_review" ] || { echo "expected pending_human_review, got $status"; exit 1; }
echo "submitted $id -> $status"

status=$(curl -fsS "$API/incidents/$id" | json "['status']")
[ "$status" = "pending_human_review" ] || { echo "GET returned $status"; exit 1; }

status=$(curl -fsS -X POST "$API/incidents/$id/approve" -H 'Content-Type: application/json' \
  -d '{"approved": true, "note": "k8s smoke test"}' | json "['status']")
[ "$status" = "resolved" ] || { echo "expected resolved after approval, got $status"; exit 1; }
echo "approved $id -> $status"

code=$(curl -s -o /dev/null -w '%{http_code}' "$WEB/")
[ "$code" = "200" ] || { echo "web returned $code"; exit 1; }
echo "web: $code"
echo "smoke test passed"
