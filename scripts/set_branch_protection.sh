#!/usr/bin/env bash
# Usage: export GITHUB_TOKEN=ghp_...; ./scripts/set_branch_protection.sh

set -euo pipefail
OWNER="aparnakumarishaw-stack"
REPO="MarketStimulator"
BRANCH="main"

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "Please set GITHUB_TOKEN environment variable with repo:admin or repo scope"
  exit 1
fi

API_URL="https://api.github.com/repos/${OWNER}/${REPO}/branches/${BRANCH}/protection"

BODY=$(cat <<JSON
{
  "required_status_checks": {"strict": true, "contexts": []},
  "enforce_admins": false,
  "required_pull_request_reviews": {"dismiss_stale_reviews": true, "require_code_owner_reviews": false, "required_approving_review_count": 1},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
)

curl -sS -X PUT "$API_URL" \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: token $GITHUB_TOKEN" \
  -d "$BODY" \
  | jq .

echo "Branch protection applied to ${OWNER}/${REPO}:${BRANCH} (if your token had sufficient rights)."