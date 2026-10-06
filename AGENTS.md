# AGENTS.md

Guidance for AI coding agents working on **Mug's Game FC**, a Fantasy Premier
League planner (FastAPI + PuLP backend, no-build vanilla-JS frontend).

The full instructions live in [`CLAUDE.md`](CLAUDE.md). The essentials:

- **Run:** `python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt && ./run.sh`
  → http://127.0.0.1:8787. Offline: `FPL_CACHE_ONLY=1 ./run.sh`.
- **Test:** start the server, then `npm --prefix tests ci && npm --prefix tests test`.
  Keep it at 0 failures.
- **Python 3.9-compatible** backend code. Game rules come from `backend/rules.py`,
  never hardcoded.
- **Frontend:** no build step. Bump `?v=N` in `frontend/index.html` after editing
  CSS/JS. Colours from tokens only, 60:30:10 (forest / mint / lime). Text on
  highlights is forest, never white.
- **Brand:** original artwork only; light British humour, never in errors or numbers.
- **Deploy:** pushing `main` deploys to Railway; check `/healthz` afterwards.

Specialist roles are described in `.claude/agents/`, procedures in
`.claude/skills/`, and the design, model, solver and API in `docs/`.
