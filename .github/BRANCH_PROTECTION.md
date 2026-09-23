# Protect `main` on GitHub

GitHub shows **“Your main branch isn't protected”** until branch protection rules are enabled. This repo includes CI (`.github/workflows/ci.yml`); **`main` should require the `test` check** before merge.

## Option A — Script (recommended)

1. Install and sign in to [GitHub CLI](https://cli.github.com/):
   ```bash
   gh auth login
   ```
2. From the repo root:
   ```bash
   chmod +x scripts/apply-main-branch-protection.sh
   ./scripts/apply-main-branch-protection.sh
   ```

Using a personal access token instead:

```bash
export GITHUB_TOKEN=ghp_YOUR_TOKEN   # repo admin scope
gh auth login --with-token <<< "$GITHUB_TOKEN"
./scripts/apply-main-branch-protection.sh
```

## Option B — GitHub UI

1. Open [Branches settings](https://github.com/cdasadiya/ai-hackathon-sept-2026/settings/branches) (must be signed in as repo admin).
2. **Add branch ruleset** or **Add classic branch protection rule** for **`main`**.
3. Enable:
   - **Require status checks to pass** → select **`test`** (from the CI workflow)
   - **Require branches to be up to date before merging**
   - **Do not allow bypassing the above settings** (recommended)
   - **Block force pushes**
   - **Prevent deletion**

## What the script configures

| Rule | Setting |
| --- | --- |
| Force push | Blocked |
| Branch deletion | Blocked |
| Status checks | Required: `test` (strict) |

After the first CI run on a PR, the **`test`** check appears in the protection rule dropdown if it was missing when the rule was created.
