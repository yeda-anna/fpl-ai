"""Structured logs: one JSON object per line on stdout, for Railway's log explorer.

Railway reads anything a service writes to stdout and treats a single-line JSON
object with `message` and `level` as a structured entry, so every extra field
can be searched as `@field:value` (`@status:>=500`, `@event:fpl.fetch_failed`).
No collector, no agent, no extra dependency - just the standard library.

    import telemetry
    log = telemetry.get_logger(__name__)
    telemetry.event(log, "engine.built", ms=812, players=690)

Rules for what goes in a log line:
  * Never a manager's Team ID, a league ID or a request body. Requests are logged
    by route template (`/api/entry/{team_id}`), FPL calls by endpoint kind
    (`entry`), never by URL or cache key - both carry IDs.
  * Everything goes to stdout. Railway marks stderr as an error, so routing
    uvicorn's own start-up chatter there made every boot look like a failure.

`LOG_LEVEL` (default INFO) sets how much is written.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Optional

# Railway understands debug / info / warn / error.
_LEVELS = {"DEBUG": "debug", "INFO": "info", "WARNING": "warn", "ERROR": "error", "CRITICAL": "error"}
# Attributes every LogRecord carries; anything else came from `extra` and is ours.
# uvicorn adds `color_message`, a copy of the message with terminal colour codes.
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message", "asctime", "taskName", "color_message"}
_FIELDS = "fields"


class JsonFormatter(logging.Formatter):
    """One line of JSON: time, level, logger, message, then the event's own fields."""

    def format(self, record: logging.LogRecord) -> str:
        out = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
                    + ".%03dZ" % int(record.msecs),
            "level": _LEVELS.get(record.levelname, "info"),
            "logger": record.name,
            "message": record.getMessage().strip(),
        }
        fields = getattr(record, _FIELDS, None)
        if isinstance(fields, dict):
            for key, value in fields.items():
                if key not in out:
                    out[key] = value
        for key, value in vars(record).items():
            if key not in _STANDARD and key != _FIELDS and key not in out:
                out[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            out["error"] = record.exc_info[0].__name__
            out["traceback"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str, separators=(",", ":"))


_handler: Optional[logging.Handler] = None


def setup(stream: Any = None) -> logging.Handler:
    """Send the app's and uvicorn's logs through one JSON handler on stdout. Safe to call twice."""
    global _handler
    if _handler is not None and stream is None:
        return _handler
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    level = os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    if level not in _LEVELS:
        level = "INFO"
    for name in ("papa", "uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        for old in list(lg.handlers):
            lg.removeHandler(old)
        lg.propagate = False
        lg.setLevel(level)
    logging.getLogger("papa").addHandler(handler)
    logging.getLogger("uvicorn").addHandler(handler)   # uvicorn.error propagates up to it
    logging.getLogger("uvicorn.error").propagate = True
    # The request line below replaces uvicorn's plain-text access log, which would
    # also record the raw path - Team IDs and all.
    logging.getLogger("uvicorn.access").disabled = True
    _handler = handler
    return handler


def get_logger(name: str) -> logging.Logger:
    """A logger under `papa`, so it shares the JSON handler: get_logger(__name__)."""
    return logging.getLogger("papa." + name.rsplit(".", 1)[-1])


def event(logger: logging.Logger, name: str, level: int = logging.INFO,
          exc_info: Any = None, **fields: Any) -> None:
    """Log a named event. `name` is the message and the searchable `event` field."""
    if not logger.isEnabledFor(level):
        return
    fields["event"] = name
    logger.log(level, name, exc_info=exc_info, extra={_FIELDS: fields})


def ms_since(start: float) -> int:
    """Whole milliseconds since a time.perf_counter() reading."""
    return int(round((time.perf_counter() - start) * 1000))


_http = get_logger("http")


def route_template(scope: Any, path: str) -> Optional[str]:
    """The matched route's template (`/api/entry/{team_id}`), never the raw path."""
    route = scope.get("route") if hasattr(scope, "get") else None
    template = getattr(route, "path", None)
    if template:
        return template
    if path.startswith("/static/"):
        return "/static"
    return None


def instrument(app: Any) -> None:
    """Log one line per request: method, route template, status and duration."""

    @app.middleware("http")
    async def _log_request(request, call_next):
        start = time.perf_counter()
        path = request.url.path
        try:
            response = await call_next(request)
        except Exception as exc:
            # uvicorn logs the traceback itself; this line keeps the request's shape.
            event(_http, "http.request", logging.ERROR, method=request.method,
                  route=route_template(request.scope, path), status=500,
                  ms=ms_since(start), error=type(exc).__name__)
            raise
        status = response.status_code
        if status >= 500:
            level = logging.ERROR
        elif path.startswith("/static/") or path == "/healthz":
            level = logging.DEBUG       # a page load pulls ~20 assets; keep them out of INFO
        else:
            level = logging.INFO
        event(_http, "http.request", level, method=request.method,
              route=route_template(request.scope, path), status=status, ms=ms_since(start))
        return response
