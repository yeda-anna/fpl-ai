# Plan: a build + deploy gate on every pull request

**Status:** approved (PR #19); phase 1 implemented in PR A `chore/ci-workflow` · **Author:** rugvedj (with Claude) · **Date:** 2026-10-17
**Base:** `main` @ `7ad7e86` (after #17, the baseline unit tests)

## 1. Goal

No pull request can be merged into `main` (which Railway deploys to production
straight away) until:

1. the code has been **built the way Railway builds it** and the built app
   **boots and answers its health check**,
2. the **tests pass** (offline unit tests on Python 3.9 and 3.12, frontend checks),
3. *(phase 2)* the PR has been **deployed to its own Railway preview** and the
   Playwright suite passes **against that deployment**, and
4. a reviewer has **approved the latest commit** — a new push after approval
   needs a fresh approval and fresh green checks.

Nothing here touches production. The gate only decides whether the merge
button is enabled.

## 2. Where we are today (checked, not assumed)

| What | Finding | How I know |
| --- | --- | --- |
| CI | **None.** There is no `.github/` folder at all. | fresh clone of `main` |
| Branch rules | No rulesets on the repo. Classic branch protection on `main` couldn't be read with my access — owner to confirm in Settings → Branches. | `GET /repos/…/rulesets` → `[]`; `…/branches/main/protection` → 403 |
| Railway → GitHub | Railway already reports on every `main` commit: a commit status **`aware-renewal - fpl-ai`** and a GitHub *deployment* to environment **`aware-renewal / production`**. Its `environment_url` is the Railway **dashboard**, not the public app URL. | `GET /commits/7ad7e86/status`, `/deployments/…/statuses` |
| Preview deploys | Only one environment has ever been deployed (`production`), so Railway PR environments are **off**. | `GET /deployments` |
| Build | Railway builds with **Railpack** (`railway.json`); start command `uvicorn main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}`, also in `Procfile`. Python 3.12 from `.python-version`. | repo files, `docs/DEPLOYMENT.md` |
| Who opens PRs | Mostly the owner (`yeda-anna`, #9–#16), now also `rugvedj` (#17, #18). | `GET /pulls` |

**Baseline test run** on `7ad7e86` in this session (so later failures are attributable):

| Check | Command | Result |
| --- | --- | --- |
| Unit tests, Python 3.13 | `FPL_CACHE_ONLY=1 python -m unittest discover -s tests -p 'test_*.py'` | **129 run, OK** (1 expected failure — the known `/api/meta` Elo bug in `test_api.py`) |
| Unit tests, **Python 3.9** | same, in a 3.9 venv with `requirements.txt` | **129 run, OK** (same expected failure) — so the pinned deps install and run on 3.9 |
| Contrast | `python3 scripts/check_contrast.py` | exit 0 |
| JS syntax | `node --check frontend/{app,motion,magic,intro}.js` | all OK |
| Playwright e2e | `npm --prefix tests test` | **not run here** — needs a server with FPL data; this sandbox has no FPL access |

## 3. Design

Two phases, so the cheap deterministic gate lands first and the slower,
network-dependent one is proven before it can block anyone.

### Phase 1 — CI build + test gate (GitHub Actions only)

New workflow `.github/workflows/ci.yml`, triggered on `pull_request` to `main`,
`push` to `main` and `workflow_dispatch`. Read-only token (`permissions:
contents: read`). PR runs cancel superseded runs; `main` runs are never
cancelled (Railway's *Wait for CI* would treat a cancelled run badly — §4).

| Job (required check name) | What it does | Why |
| --- | --- | --- |
| **`unit (py3.9)`** | `pip install -r requirements.txt` → `python -m compileall -q backend tests` → `FPL_CACHE_ONLY=1 python -m unittest discover -s tests -p 'test_*.py'` | Enforces CLAUDE.md's "Python 3.9-compatible" rule mechanically (catches `match`, runtime `X \| Y`, 3.10+ APIs). Offline: no FPL calls. |
| **`unit (py3.12)`** | same on 3.12 | What production actually runs. |
| **`frontend`** | `node --check` on **every** `frontend/*.js` (vendor excluded) → `python3 scripts/check_contrast.py` | No-build SPA: a syntax error would ship straight to users. Contrast is a stated rule. |
| **`build`** | 1. Assert `Procfile` and `railway.json` carry the **same** start command. 2. Install a **pinned** Railpack CLI, start BuildKit, `railpack build .` → image. 3. Run the image with `PORT=8000 FPL_CACHE_ONLY=1`. 4. `scripts/smoke.sh http://127.0.0.1:8000` (below). | Builds with the same builder Railway uses, so a broken dependency pin, Python version or start command fails here instead of in production. Booting proves `/healthz` answers before the engine has warmed up. |

**`scripts/smoke.sh <base-url> [--live]`** — one small script, reused by CI,
the preview job and the manual post-deploy check in `docs/DEPLOYMENT.md`:

- `/healthz` → 200 with `"ok": true` within 60 s
- `/` → 200 and contains `<meta name="app-build" …>`
- `/version` → its `build` equals that meta value
- the first `/static/…?v=<hash>` asset in the page → 200
- with `--live` only (real FPL data): `/api/entry/999999999` → **404**, as `docs/DEPLOYMENT.md` already expects

Illustrative sketch (final file will pin every action by commit SHA and Railpack/BuildKit by version):

```yaml
name: CI
on:
  pull_request: { branches: [main] }
  push:         { branches: [main] }
  workflow_dispatch:
permissions: { contents: read }
concurrency:
  group: ci-${{ github.event.pull_request.number || github.sha }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  unit:
    name: unit (py${{ matrix.python }})
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    strategy: { fail-fast: false, matrix: { python: ['3.9', '3.12'] } }
    steps:
      - uses: actions/checkout@<sha>
      - uses: actions/setup-python@<sha>
        with: { python-version: '${{ matrix.python }}', cache: pip }
      - run: pip install -r requirements.txt
      - run: python -m compileall -q backend tests
      - run: python -m unittest discover -s tests -p 'test_*.py' -v
        env: { FPL_CACHE_ONLY: '1' }

  frontend:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@<sha>
      - run: for f in frontend/*.js; do node --check "$f"; done
      - run: python3 scripts/check_contrast.py

  build:
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@<sha>
      - run: python3 scripts/check_start_command.py      # Procfile == railway.json
      - run: curl -sSL https://railpack.com/install.sh | RAILPACK_VERSION=<pinned> sh
      - run: docker run --rm --privileged -d --name buildkit moby/buildkit:<pinned>
      - run: railpack build . --name fpl-ai:ci
        env: { BUILDKIT_HOST: 'docker-container://buildkit' }
      - run: docker run -d --name app -p 8000:8000 -e PORT=8000 -e FPL_CACHE_ONLY=1 fpl-ai:ci
      - run: scripts/smoke.sh http://127.0.0.1:8000
      - if: failure()
        run: docker logs app
```

### Phase 2 — deploy every PR to a Railway preview, test it there

This is the "deployment step". Railway's **PR Environments** create a
temporary copy of the project for each PR, give it its own Railway URL, comment
the URL on the PR, and tear it down when the PR is merged or closed. Builds
aren't billed; the running preview is (usage-based).

New workflow `.github/workflows/preview.yml` (`pull_request` to `main`), job
**`preview e2e`**:

1. **Wait for the preview deploy** — poll the PR head commit's statuses until
   Railway's PR-environment status is `success` (fail on `failure`/`error`,
   timeout 20 min). Production's context is `aware-renewal - fpl-ai`; the PR
   environment's exact context name will be read off the first preview and
   written into the workflow.
2. **Find the preview URL.** Railway's GitHub deployment carries a dashboard
   link, not the app URL, so one of:
   - **(a, recommended)** Railway CLI/API with a project token stored as the repo secret `RAILWAY_TOKEN`, asking for the PR environment's domain;
   - (b) read the Railway bot's PR comment (no secret, but brittle to wording changes);
   - (c) a predictable domain pattern, if Railway's PR domains turn out to follow one.
   Settled in a short spike at the start of phase 2.
3. `scripts/smoke.sh "$URL" --live`.
4. `npm --prefix tests ci && BASE_URL="$URL" TEAM_ID=1 npm --prefix tests test` — the full Playwright suite (phone 390, desktop 1440, reduced motion, demo, leagues) against the **real deployed build with live FPL data**.
5. Upload `tests/screenshots/` as a workflow artifact, so reviewers see phone + desktop shots without running anything.

Why run e2e on the preview instead of on the runner: production already proves
Railway can reach the FPL API; whether GitHub's runners can is unverified, and
the suite needs live data for team 1. Testing the deployed artefact is also the
honest "it deploys and works" signal.

### Branch ruleset on `main` (owner applies in Settings → Rules)

Two rulesets, so the owner can still merge their own PRs without ever being
able to skip the checks:

**Ruleset 1 — "main: checks" (no bypass for anyone)**
- Require a pull request before merging
- Require status checks: `unit (py3.9)`, `unit (py3.12)`, `frontend`, `build`; add `preview e2e` in phase 2 (see rollout)
- Require branches to be up to date before merging
- Block force pushes; restrict deletions

**Ruleset 2 — "main: review" (bypass: repository admin, i.e. the owner)**
- Required approvals: **1**
- Dismiss stale approvals when new commits are pushed
- Require approval of the most recent reviewable push
- Require conversation resolution

Why two: GitHub won't let a PR author approve their own PR. The owner opens
most PRs, so a single ruleset with 1 required approval either blocks the owner
or needs a bypass that would also skip the checks. Split, the bypass only skips
the review.

### Railway settings (owner applies in the Railway dashboard)

- **Enable PR Environments** (Project Settings → Environments). Base environment
  stays `production` — the app has no database or secrets (`docs/DEPLOYMENT.md`
  lists only `PORT` and `FPL_CACHE_ONLY`), and `.cache/` is per-container, so a
  preview shares nothing stateful with production.
- **Invite contributors** (e.g. `rugvedj`) to the Railway project with the
  GitHub account they open PRs from — Railway won't build PRs from users outside
  the workspace, and their PRs would then never get a preview.
- **Wait for CI** on the production service: Railway holds each `main` deploy
  until GitHub Actions on that commit finishes and skips it if a workflow fails.
  This is the last net for anything that reaches `main` without the gate.

## 4. Edge cases and failure paths

| Case | Behaviour |
| --- | --- |
| FPL API down / slow | Phase 1 is fully offline — unaffected. Phase 2 e2e goes red; maintainer re-runs. This is why `preview e2e` starts non-required. |
| Railway build or deploy fails | Phase 1 `build` should already have failed. If only the preview fails, `preview e2e` fails at step 1 with Railway's status description in the log. |
| PR from a fork | No secrets for fork PRs and Railway won't deploy them, so phase 2 can't run. Maintainer pushes the branch into the repo to get a preview. (A skipped job may count as passing for a required check, so the job must **fail**, not skip, when it has no preview.) |
| Docs-only PR | All jobs still run (phase 1 takes minutes). No path filters, because a filtered-out required check would block the merge forever. |
| `main` moves after approval | "Up to date" rule → update the branch → checks re-run; "dismiss stale approvals" → re-approve. |
| Emergency hotfix | Owner bypasses review (ruleset 2) but still waits for checks. True break-glass: temporarily disable ruleset 1 (logged in the rules history), re-enable after. |
| `main` run cancelled | `main` runs are never cancelled (concurrency rule above), so Wait for CI isn't left on a cancelled run. |

## 5. Rollout

| Step | Who | Change |
| --- | --- | --- |
| 1 | contributor | **PR A `chore/ci-workflow`**: `ci.yml`, `scripts/smoke.sh`, `scripts/check_start_command.py`; docs: `docs/TESTING.md` (a "CI" section), `docs/DEPLOYMENT.md` ("Ship it" now points at the gate; smoke curls → `smoke.sh`), `CLAUDE.md` (one line under Git and deploy), `docs/CHANGELOG.md` (behind-the-scenes entry). |
| 2 | contributor | Prove PR A on throwaway PRs (§6) before merge. |
| 3 | owner | Merge PR A; create rulesets 1 + 2 with the four phase-1 checks; turn on **Wait for CI**. |
| 4 | owner | Enable Railway PR Environments; invite contributors; (option a) create a Railway project token → repo secret `RAILWAY_TOKEN`. |
| 5 | contributor | **PR B `chore/ci-preview-e2e`**: `preview.yml` + docs. Runs as a **non-required** check. |
| 6 | owner | After ~10 consecutive green `preview e2e` runs on real PRs, add it to ruleset 1. |

Every step is reversible: delete the workflow file, disable a ruleset, or
toggle the Railway setting. None of them deploys or changes production.

## 6. How we'll know it works (acceptance)

On throwaway PRs during step 2 (closed, never merged):

1. `node`-invalid line in `frontend/app.js` → `frontend` red, merge blocked.
2. A runtime `int | None` annotation in a backend module → `unit (py3.9)` red, `unit (py3.12)` green — proves the 3.9 guard.
3. A typo in `Procfile`'s start command → `build` red (mismatch check), and with both files broken the container never answers `/healthz`.
4. A failing unit test → both `unit` jobs red.
5. A clean PR → all green; merge button still disabled until a non-author approves; push one more commit → approval dismissed, checks re-run.
6. Phase 2: clean PR → Railway preview comes up, `preview e2e` green with screenshots attached; closing the PR removes the preview environment.

## 7. Decisions for the owner

1. **Approve the two-phase approach?** (Phase 1 alone already gives "built + booted + tested before merge".)
2. **Railway PR Environments** — OK with the usage cost of a preview per open PR?
3. **Required approvals = 1**, with the owner able to bypass *review only* (ruleset 2)?
4. **`preview e2e` required** immediately, or after ~10 green runs (recommended)?
5. **Wait for CI** on production — on?
6. **Preview URL lookup** — Railway token as a repo secret (recommended), or parse the bot comment to avoid storing a secret?

## 8. Not verified yet (resolved during implementation)

- Railpack CLI flags for naming/loading the built image into Docker on a GitHub runner — the docs show `railpack build <dir>` with BuildKit via `BUILDKIT_HOST`; exact output flags confirmed in PR A.
- That the CLI's build matches Railway's (Railway reads `railway.json`; the CLI reads the `Procfile` — hence the "same start command" check).
- The commit-status context name and domain Railway uses for PR environments.
- How long the Playwright suite takes against a preview (sets the job timeout).
- Whether classic branch protection is already set on `main` (I couldn't read it); if so, it moves into the rulesets.

## 9. Noticed along the way (separate follow-ups, not part of this plan)

- `CLAUDE.md`'s map lists `.claude/agents/` and `.claude/skills/`, but neither exists in the repo.
- Two different live URLs: `CLAUDE.md` says `paparanjeet.up.railway.app`, `docs/DEPLOYMENT.md` says `fpl-ai-production-966c.up.railway.app`.
- `CLAUDE.md`'s `node --check` loop skips `frontend/portrait.js` (the CI job checks every file).
- Known bug pinned by an expected failure in `tests/test_api.py`: `/api/meta` fails when the Elo prior can't be fetched.

## Sources

- [Railway — Preview deployments with PR environments](https://docs.railway.com/guides/preview-deployments-with-pr-environments)
- [Railway — GitHub autodeploys / Wait for CI](https://docs.railway.com/deployments/github-autodeploys)
- [Railpack — install and `railpack build`](https://railpack.com/llms-full.txt) · [Developing locally](https://railpack.com/guides/developing-locally)
