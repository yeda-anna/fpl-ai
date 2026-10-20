# AGENTS.md

Guidance for AI coding agents working on **Papa Ranjeet**, a Fantasy Premier
League planner (FastAPI + PuLP backend, no-build vanilla-JS frontend).

The full instructions live in [`CLAUDE.md`](CLAUDE.md). The essentials:

- **Run:** `python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt && ./run.sh`
  → http://127.0.0.1:8787. Offline: `FPL_CACHE_ONLY=1 ./run.sh`.
- **Test:** start the server, then `npm --prefix tests ci && npm --prefix tests test`.
  Keep it at 0 failures.
- **Python 3.9-compatible** backend code. Game rules come from `backend/rules.py`,
  never hardcoded.
- **Frontend:** no build step, no CDN. Animation is GSAP, anime.js, Motion and AutoAnimate, vendored in `frontend/vendor/` and wrapped by `frontend/motion.js` (`FX`); there is no opening film; Magic UI's effects are rebuilt in plain JS in `frontend/magic.js` (no React). One race-day look (dark teal, italic Chakra Petch, slanted lime buttons), six tabs, the Team ID asked once per device. Cache-busting is automatic (content-hashed `?v=` added by the server); don't add version numbers by hand.
- **Brand:** original artwork only; light British humour and Indian dark humour (`QUIPS` in `app.js`) on the landing screen and loaders, never in errors or numbers, never at anyone's expense but the manager's own.
- **Deploy:** pushing `main` deploys to Railway; check `/healthz` afterwards.

Specialist roles are described in `.claude/agents/`, procedures in
`.claude/skills/`, and the design, model, solver and API in `docs/`.
