#!/usr/bin/env bash
# Apply GitHub branch protection on `main` for cdasadiya/ai-hackathon-sept-2026.
#
# Requires admin access on the repo and ONE of:
#   - gh auth login   (recommended)
#   - export GITHUB_TOKEN=ghp_...  (repo admin scope)
#
# Usage:
#   ./scripts/apply-main-branch-protection.sh

set -euo pipefail

REPO="${GITHUB_REPOSITORY:-cdasadiya/ai-hackathon-sept-2026}"
BRANCH="${1:-main}"
GH="${GH_BIN:-gh}"

if ! command -v "$GH" >/dev/null 2>&1; then
  GH="/home/shreeji/.local/bin/gh"
fi

if ! command -v "$GH" >/dev/null 2>&1; then
  echo "GitHub CLI (gh) not found. Install from https://cli.github.com/" >&2
  exit 1
fi

if ! "$GH" auth status >/dev/null 2>&1; then
  echo "Not authenticated. Run: gh auth login" >&2
  echo "Or: export GITHUB_TOKEN=<PAT with repo admin> && gh auth login --with-token <<< \"\$GITHUB_TOKEN\"" >&2
  exit 1
fi

echo "Applying protection to ${REPO} branch ${BRANCH}..."

# Status check context = CI job id in .github/workflows/ci.yml (job: test)
"$GH" api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/${REPO}/branches/${BRANCH}/protection" \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      { "context": "test" }
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_linear_history": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": true
}
EOF

echo "Done. Verify: https://github.com/${REPO}/settings/branches"
