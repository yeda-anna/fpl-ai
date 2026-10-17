---
name: pr-screenshots
description: Before/after screenshots of a UI change - main vs the PR branch, phone and desktop - checked for console errors and phone overflow, then embedded in the PR description. Use for any PR that changes what a page looks like, or when asked for "screenshots", "before and after" or "what does it look like".
---

# PR screenshots: before vs after

Every UI pull request carries phone (390x844) and desktop (1440x900) screenshots of
the changed view on `main` (before) and on the branch (after). Two scripts do the work:

| Script | Does |
| --- | --- |
| `scripts/serve_fake.py` | Serves any checkout on the made-up league in `tests/fakes.py`, network off. Every view works on the demo team (ID 0). |
| `scripts/screenshots.js` | Shoots one view on both servers at both sizes, plus hover/open states, and **fails** (exit 1) on console errors, overflow past 390px or a view that never draws. |

Screenshots made on the fake league show test data: players are called `C03-D4` and so
on. Say so in the PR. With live FPL access, run `./run.sh` on each branch instead and
pass `--team <your ID>` to see a real season.

## Example prompt

> Add before/after screenshots of Home → My squad to PR #18. Show the new season
> chart on phone and desktop, with the tooltip and the week-by-week table open.

Worked example: [#18](https://github.com/yeda-anna/fpl-ai/pull/18) (the season rank
chart). Its **Screenshots** section came from exactly these steps.

## Steps

### 1. Pin down what to shoot
- The PR number and its branch: `gh api repos/yeda-anna/fpl-ai/pulls/<N> --jq .head.ref`.
- The **view** as its address (`home/squad`, `plan/chips`, `players/projections` …).
- `--from`: where the crop starts. Pick an element that exists on **both** branches
  just above the change, so the pair lines up (e.g. `#v-home-squad .grid.g23 > .card:last-child`).
- `--focus`: the changed element (e.g. `.season-card`), plus `--hover` (what to
  hover or tap) and `--open` (a `<summary>`, a switch) for its interaction states.
  Read the branch's diff in `frontend/app.js` / `styles.css` for the class names.

### 2. Two checkouts, two servers
```bash
git fetch origin main <branch>
git worktree add ../shots-main origin/main
git worktree add ../shots-pr   origin/<branch>
./.venv/bin/python scripts/serve_fake.py --port 8791 --repo ../shots-main &   # before
./.venv/bin/python scripts/serve_fake.py --port 8790 --repo ../shots-pr   &   # after
curl -s localhost:8790/healthz      # {"ok": true, "model_ready": true}
```
The `--repo` checkout needs `tests/fakes.py` (on `main` since #17). Check the
"after" server really has the change (a new API field or element) before shooting.

### 3. Shoot and check
```bash
npm --prefix tests install          # once; not `ci`: there is no lockfile
node scripts/screenshots.js --before http://127.0.0.1:8791 --after http://127.0.0.1:8790 \
  --view home/squad --from '#v-home-squad .grid.g23 > .card:last-child' \
  --focus '.season-card' --hover '.season-hit' --open '.season-table summary' \
  --out tests/screenshots/pr-<N>
```
- `OK  8 screenshots …` and exit 0 = shot and checked. Any `FAIL` line means fix the branch
  (or the selectors) before going on; never publish screenshots of a page that failed.
- In a sandbox without Playwright's own browser: `PW_CHROMIUM=/opt/pw-browsers/chromium`.
- **Look at every PNG** before publishing: the pair lines up, nothing clipped or
  overlapping, no loader or error box. The script checks errors and width, not taste.

### 4. Put them in the PR
GitHub's API can't attach images to a PR body. Two ways:

- **By hand (simplest):** drag the PNGs into the PR description editor on GitHub.
- **From a session:** commit them to a standalone branch that is never merged, and link them:
  ```bash
  git worktree add --orphan -b pr-assets/<feature> ../shots-assets
  mkdir ../shots-assets/pr-<N> && cp tests/screenshots/pr-<N>/*.png ../shots-assets/pr-<N>/
  # downscale the desktop shots to 1x width (PIL: Image.LANCZOS, optimize=True) to keep them small
  # add a README: what the branch is, never merged, delete it when the PR closes
  git -C ../shots-assets add -A && git -C ../shots-assets commit -m "Add before/after screenshots for #<N>"
  git -C ../shots-assets push -u origin pr-assets/<feature>
  ```
  Link with the commit SHA: `https://raw.githubusercontent.com/yeda-anna/fpl-ai/<sha>/pr-<N>/<file>.png`
  and check one returns 200 (`curl -o /dev/null -w '%{http_code}'`). Raw links only
  render because the repo is public.

Then edit the description. Always start from the **live** body (the owner may have
edited it), and use REST (`gh pr create/edit` use GraphQL, which session proxies block):
```bash
gh api repos/yeda-anna/fpl-ai/pulls/<N> --jq .body > body.md
# insert the section below, above "## API" / "## Tests"
gh api -X PATCH repos/yeda-anna/fpl-ai/pulls/<N> -F body=@body.md
```

Section template:
```markdown
## Screenshots

These show the demo team on the made-up test league (`scripts/serve_fake.py`), so names
and numbers are test data. `main` on the left, this branch on the right.

**Phone (390 px)**

| Before (`main`) | After (this PR) |
| --- | --- |
| <img src="…/before-phone.png" width="300" alt="…"> | <img src="…/after-phone.png" width="300" alt="…"> |

**Desktop (1440 px)**

Before (`main`):

<img src="…/before-desktop.png" width="720" alt="…">

After (this PR):

<img src="…/after-desktop.png" width="720" alt="…">
```
Give every image an `alt` that says what it shows.

### 5. Clean up
- Stop the servers: `pkill -f 'serve_[f]ake.py'`. The brackets matter: a plain
  `pkill -f serve_fake.py` also matches the shell running it and kills that shell.
- `git worktree remove --force ../shots-main ../shots-pr ../shots-assets`, then `git worktree prune`.
- Nothing from this goes on the PR branch: screenshots, `node_modules` and worktrees
  stay out of commits (`tests/screenshots/` and `tests/node_modules/` are git-ignored).

## Report back
One or two lines: which view and states were shot, that the check passed (or what it
caught), that the images are test data, and where they're hosted. If you used a
`pr-assets/…` branch, say it can be deleted once the PR closes (the images then stop showing).
