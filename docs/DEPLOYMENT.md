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
3. Commit and `git push origin main`.
4. Watch the deployment reach **SUCCESS** in Railway.
5. Smoke test the live site:
   ```bash
   U=https://fpl-ai-production-966c.up.railway.app
   curl -s $U/healthz
   curl -s $U/version                                          # build id
   curl -s $U/ | grep -o 'styles.css?v=[0-9a-f]*'               # content hash
   curl -s -o /dev/null -w '%{http_code}\n' $U/api/entry/1          # 200
   curl -s -o /dev/null -w '%{http_code}\n' $U/api/entry/999999999  # 404
   ```

### Rolling back

Redeploy the previous deployment from the Railway dashboard, or
`git revert <sha> && git push`. Never force-push `main`.

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
