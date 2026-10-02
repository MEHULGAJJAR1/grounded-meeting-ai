"""Bounded single-process sliding-window limiter for auth and AI endpoints.

Deploy behind a gateway/Redis-backed limiter when horizontally scaling.
"""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from fastapi import HTTPException, Request

_windows: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def rate_limit(request: Request, group: str, count: int, seconds: int = 60):
    key = f"{group}:{request.client.host if request.client else 'unknown'}"
    now = monotonic()
    with _lock:
        if len(_windows) > 10000:
            stale = [k for k, v in _windows.items() if not v or now - v[-1] > 3600]
            for item in stale:
                _windows.pop(item, None)
        entries = _windows[key]
        while entries and entries[0] <= now - seconds:
            entries.popleft()
        if len(entries) >= count:
            raise HTTPException(
                429,
                "Too many requests; please try again shortly",
                headers={"Retry-After": str(seconds)},
            )
        entries.append(now)
