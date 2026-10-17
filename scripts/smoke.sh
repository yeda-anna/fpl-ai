#!/usr/bin/env bash
# Smoke-test a running Papa Ranjeet: is it up, serving the page it says it is,
# and serving that page's assets?
#
#   scripts/smoke.sh http://127.0.0.1:8000           # CI's built container, offline
#   scripts/smoke.sh https://<preview-or-live-url>   # a deploy
#   scripts/smoke.sh https://<url> --live            # also ask FPL (unknown team → 404)
#
# Checks, in order (the first failure stops it, exit 1):
#   1. /healthz → 200 with "ok": true, retried for up to SMOKE_TIMEOUT seconds
#      (default 60) while the server boots, every SMOKE_INTERVAL seconds (default 2)
#   2. /        → 200 and carries <meta name="app-build" …>
#   3. /version → its "build" equals that meta value
#   4. the first /static/…?v=<hash> asset in the page → 200
#   5. --live only: /api/entry/999999999 → 404 (needs real FPL data)
set -euo pipefail

usage() { echo "usage: $0 <base-url> [--live]" >&2; exit 2; }
[ $# -ge 1 ] || usage
BASE="${1%/}"
LIVE=0
case "${2:-}" in
  "") ;;
  --live) LIVE=1 ;;
  *) usage ;;
esac
TIMEOUT="${SMOKE_TIMEOUT:-60}"
INTERVAL="${SMOKE_INTERVAL:-2}"

pass() { echo "ok   $*"; }
fail() { echo "FAIL $*" >&2; exit 1; }

# GET a URL into $BODY and $CODE; never fails the script itself.
get() {
  local out
  out="$(curl -sS --max-time 15 -w $'\n%{http_code}' "$1" 2>/dev/null)" || out=$'\n000'
  CODE="${out##*$'\n'}"
  BODY="${out%$'\n'*}"
}

# 1. /healthz, retried while the server starts
deadline=$(( $(date +%s) + TIMEOUT ))
while :; do
  get "$BASE/healthz"
  if [ "$CODE" = 200 ] && printf '%s' "$BODY" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*true'; then
    pass "/healthz → 200 $BODY"
    break
  fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    fail "/healthz did not answer 200 with \"ok\": true within ${TIMEOUT}s (last: $CODE $BODY)"
  fi
  sleep "$INTERVAL"
done

# 2. the page and its build id
get "$BASE/"
[ "$CODE" = 200 ] || fail "/ → $CODE, expected 200"
PAGE="$BODY"
BUILD="$(printf '%s' "$PAGE" | sed -n 's/.*<meta name="app-build" content="\([^"]*\)".*/\1/p' | head -n 1 || true)"
[ -n "$BUILD" ] || fail "/ has no <meta name=\"app-build\"> (is index.html being served by the app?)"
pass "/ → 200, build $BUILD"

# 3. /version agrees with the page
get "$BASE/version"
[ "$CODE" = 200 ] || fail "/version → $CODE, expected 200"
VERSION="$(printf '%s' "$BODY" | sed -n 's/.*"build"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
[ "$VERSION" = "$BUILD" ] || fail "/version build \"$VERSION\" != page build \"$BUILD\""
pass "/version → $VERSION"

# 4. a fingerprinted asset from the page
ASSET="$(printf '%s' "$PAGE" | grep -oE '/static/[A-Za-z0-9._/-]+\?v=[A-Za-z0-9._-]+' | head -n 1 || true)"
[ -n "$ASSET" ] || fail "/ references no content-hashed /static/…?v= asset"
get "$BASE$ASSET"
[ "$CODE" = 200 ] || fail "$ASSET → $CODE, expected 200"
pass "$ASSET → 200"

# 5. live FPL: an unknown team is a readable 404, not a 500
if [ "$LIVE" = 1 ]; then
  get "$BASE/api/entry/999999999"
  [ "$CODE" = 404 ] || fail "/api/entry/999999999 → $CODE, expected 404"
  pass "/api/entry/999999999 → 404"
fi

echo "smoke: all checks passed for $BASE"
