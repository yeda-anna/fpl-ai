---
name: create-pr
description: Open or tidy up a pull request - one squashed commit on top of main, a short What/Why/How/Tests description, screenshots for UI changes. Use when asked to "open a PR", "squash", "clean up the PR" or "shorten the description".
---

# Create a PR

The owner's style: **simple, short and sweet.** Convey the intent; let screenshots do
the talking. Worked example: #18 (season rank chart).

## Rules
- Never push to or force-push `main` - it deploys to production.
- Branch from latest `main`: `feat/`, `fix/`, `test/`, `chore/` + a short name.
- One concern per PR, and **one commit** on top of `main`.
- Use `gh api` (REST). `gh pr create/edit/view` use GraphQL, which session proxies block.

## 1. Branch
New work:
```bash
git fetch origin main && git checkout -b feat/<name> origin/main
```
An existing PR (works in a shallow clone too):
```bash
B=$(gh api repos/yeda-anna/fpl-ai/pulls/<N> --jq .head.ref)
git fetch --depth=50 origin +main:refs/remotes/origin/main +$B:refs/remotes/origin/$B
git checkout -B $B origin/$B
```

## 2. Commit message
- Subject: imperative, at most 72 chars, in user terms
  ("Chart the season's overall rank on Home → My squad").
- Body: why first (the user's problem), then what changed in plain words, then one
  short paragraph on tests.

## 3. Squash to one commit
When the branch has more than one commit (merges from `main` included), keep the
message of the first real commit:
```bash
OLD=$(git rev-parse HEAD); T=$(git rev-parse HEAD^{tree})
git log -1 --format=%B <first-commit> > msg.txt
git reset --soft origin/main
GIT_AUTHOR_DATE="$(git log -1 --format=%aD <first-commit>)" git commit -F msg.txt
[ "$(git rev-parse HEAD^{tree})" = "$T" ] && echo "code unchanged"
git push --force-with-lease=$B:$OLD origin $B
```
Merge `main` into the branch first if it is behind, so the soft reset keeps the
resolved tree. If the tree is identical, say so: history changed, code didn't.

## 4. Upstream tracking
Shallow clones don't track the branch, so `git status` and stop hooks report
"unpushed" commits that are already on GitHub:
```bash
git config --add remote.origin.fetch "+refs/heads/$B:refs/remotes/origin/$B"
git config branch.$B.remote origin && git config branch.$B.merge refs/heads/$B
git log --oneline @{u}..HEAD   # expect nothing
```

## 5. Description - about 300 words, not counting images
```markdown
## What
One or two sentences: the change as the user sees it, **UI paths in bold**.

## Why
One or two sentences: the user's problem.

## How
- Two or three bullets: key design choices, API shape. No JSON dumps.

## Screenshots
Phone (390 px) and desktop (1440 px), before (`main`) vs after.

## Tests
- New tests and counts, one line each; say which fail on `main`.
- **Not verified:** anything not run (e.g. e2e against live FPL data), and the
  command the reviewer should run.
```
Leave out verification walkthroughs, long edge-case lists and side observations -
raise those in chat or as their own issues.

## 6. Screenshots
For UI changes, follow the `pr-screenshots` skill. When rewriting an existing
description, keep its screenshot section byte for byte and check no image was lost:
```bash
diff <(grep -o 'https://raw[^"]*' old.md) <(grep -o 'https://raw[^"]*' new.md)
```

## 7. Open or update
```bash
# new
gh api repos/yeda-anna/fpl-ai/pulls -f title="<subject>" -f head=$B -f base=main \
  -F body=@body.md --jq .html_url
# existing
gh api repos/yeda-anna/fpl-ai/pulls/<N> --jq .body > old.md
gh api -X PATCH repos/yeda-anna/fpl-ai/pulls/<N> -F body=@body.md --jq .html_url
```

## 8. Report
Lead with the PR link, then a few lines: the commit SHA, whether the code changed,
the description's word count, and anything dropped or not verified.
