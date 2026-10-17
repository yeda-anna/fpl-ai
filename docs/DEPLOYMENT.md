# Deployment

## Railway (production)

Live: https://fpl-ai-production-966c.up.railway.app

Railway builds with **Railpack** and redeploys on every push to `main` of
`yeda-anna/fpl-ai`. Configuration is in `railway.json`:

```json
{
  "build":  { "builder": "RAILPACK" },
  "deploy": {
    "startCommand": "uvicorn main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}",
    "healthcheckPath": "/healthz",
    "healthcheckTimeout": 120,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 5
  }
}
```

- Python version comes from `.python-version` (3.12). Dependencies from
  `requirements.txt` (FastAPI, uvicorn, httpx, pydantic, PuLP — PuLP bundles
  the CBC binary).
- The start command is required: the app lives in `backend/main.py`, so
  Railpack can't find an entry point on its own.
- `/healthz` answers instantly; the engine warms up in a background thread.
- `.cache/` is ephemeral on Railway — it rebuilds from the FPL API after each
  deploy.

### Ship it

1. `npm --prefix tests test` against a local server — 0 failures.
2. Nothing to bump: CSS/JS URLs are content-hashed by the server, and open apps
   reload themselves when they notice the new build.
3. Open a pull request into `main` from a branch. **CI** (`.github/workflows/ci.yml`)
   builds it with Railpack as Railway does, boots it, smoke-tests it and runs
   the unit and frontend checks — `unit (py3.9)`, `unit (py3.12)`, `frontend`,
   `build` must all be green (`docs/TESTING.md` → CI).
4. Merge the pull request; Railway deploys the merge commit.
5. Watch the deployment reach **SUCCESS** in Railway.
6. Smoke test the live site:
   ```bash
   U=https://fpl-ai-production-966c.up.railway.app
   scripts/smoke.sh $U --live                                  # health, page, build id, assets, unknown team → 404
   curl -s -o /dev/null -w '%{http_code}\n' $U/api/entry/1     # 200
   ```

### Rolling back

Redeploy the previous deployment from the Railway dashboard (instant, no CI),
or `git revert <sha>` on a branch and merge it as a pull request. Never
force-push `main`.

## Other hosts

`Procfile` carries the same command (`web: uvicorn main:app --app-dir backend
--host 0.0.0.0 --port ${PORT:-8000}`) for Heroku-style platforms.

## Local

```bash
./run.sh                # 127.0.0.1:8787
PORT=9000 ./run.sh
FPL_CACHE_ONLY=1 ./run.sh
```

## Environment variables

| Name | Default | Effect |
| --- | --- | --- |
| `PORT` | 8787 local / platform-set | listen port |
| `FPL_CACHE_ONLY` | off | `1` = never call the FPL API; serve `.cache/` only |
| `LOG_LEVEL` | `INFO` | `DEBUG` adds static files, `/healthz` and offline cache misses; `WARNING` keeps only problems |

## Logs

`backend/telemetry.py` writes one JSON object per line to **stdout** (nothing to
stderr, which Railway marks as an error). Railway keeps them for the plan's log
retention (3 days free, 7 Hobby, 30 Pro) and lets you search any field in the
Log Explorer or with `railway logs`:

```
@event:http.request @status:>=500          # server errors
@event:http.request @route:/api/solve @ms:>5000
@event:fpl.fetch_failed                    # FPL outages; served_stale says if users still got data
@event:engine.warmup_failed                # a bad boot
@event:solver.solved @feasible:false
```

| Event | Level | Fields |
| --- | --- | --- |
| `http.request` | info (debug for `/static/*`, `/healthz`; error for 5xx) | `method`, `route` (template, `null` if unmatched), `status`, `ms`, `error` on an unhandled exception |
| `fpl.fetch` | info | `endpoint` (kind: `entry`, `picks`, `live` …), `status`, `ms` — only on a cache miss |
| `fpl.fetch_failed` | warn if a stale copy was served, error if not, info for a 404 | `endpoint`, `status`, `error`, `ms`, `served_stale` |
| `fpl.cache_only_miss` | debug | `endpoint` |
| `engine.built` | info | `ms`, `current_gw`, `next_gw`, `players`, `elo_prior`, `recent_gws` |
| `engine.elo_prior_unavailable`, `engine.recent_live_unavailable` | warn | `error`, `detail` |
| `engine.warmup_failed` | error | `error`, `traceback` |
| `solver.solved` | info, warn if not feasible | `ms` (CBC time), `status`, `feasible`, `horizon`, `pool_size`, `time_limit`, `hit_time_limit`, `alternative` |

uvicorn's own messages arrive as `logger: uvicorn.error` lines (with a
`traceback` for an unhandled exception); its plain-text access log is turned off
because the `http.request` line replaces it without the raw path.

**Never log a Team ID, a league ID or a request body.** Log routes by template and
FPL calls by endpoint kind; add new events with `telemetry.event(log, "area.what", **fields)`.

Railway has no built-in log drain. For retention beyond the plan's window,
forward stdout with a collector (Vector, Fluent Bit) or an OpenTelemetry exporter.

