import time
import threading
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status
from app.core.config import settings

# Thread-safe in-memory sliding window rate limiter
# Key: client_ip (or identifier) -> list of timestamp floats
# NOTE: Process-local in-memory state. In single-process development / demo deployments,
# this provides lightweight zero-dependency protection against basic flooding and brute-force attempts.
# PRODUCTION DEPLOYMENT LIMITATION:
# In multi-worker (e.g. Uvicorn with multiple workers) or horizontally autoscaled multi-container
# deployments, each process maintains an independent window memory. For distributed production clusters,
# this mechanism should be backed by a centralized key-value store (e.g., Redis or Valkey) using
# an atomic sliding-window script or token-bucket algorithm.
_request_records: Dict[str, List[float]] = {}
_records_lock = threading.Lock()
MAX_TRACKED_KEYS = 5000


def get_client_ip(request: Request) -> str:
    """
    Safely resolves the client IP address.
    Does NOT trust client-supplied X-Forwarded-For headers by default.
    Only inspects X-Forwarded-For if settings.BEHIND_PROXY is True AND
    the direct client connection originates from a configured trusted proxy.
    """
    if not request or not request.client:
        return "unknown"

    direct_ip = request.client.host
    if settings.BEHIND_PROXY and direct_ip in settings.TRUSTED_PROXIES:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First element is the client IP
            client_candidate = forwarded.split(",")[0].strip()
            if client_candidate:
                return client_candidate

    return direct_ip


def _cleanup_expired_keys(now: float) -> None:
    """Internal helper to prune keys with no active timestamps."""
    expired_keys = [
        k
        for k, timestamps in _request_records.items()
        if not timestamps or timestamps[-1] < (now - 300)
    ]
    for k in expired_keys:
        _request_records.pop(k, None)


def check_rate_limit(
    request: Request,
    max_requests: int = 60,
    window_seconds: int = 60,
    action_key: str = "default",
    current_time: Optional[float] = None,
) -> None:
    """
    Enforces in-memory sliding window rate limits based on client IP.
    Raises HTTPException(429) if exceeded. Includes Retry-After header.

    Single-process scope: Tracks request timestamps within local process memory.
    Supports deterministic unit testing via optional current_time parameter.
    """
    client_ip = get_client_ip(request)
    key = f"{action_key}:{client_ip}"
    now = current_time if current_time is not None else time.time()
    cutoff = now - window_seconds

    with _records_lock:
        # Periodic memory bounding cleanup
        if len(_request_records) > MAX_TRACKED_KEYS:
            _cleanup_expired_keys(now)

        timestamps = _request_records.get(key, [])
        valid_timestamps = [t for t in timestamps if t > cutoff]

        if len(valid_timestamps) >= max_requests:
            # Earliest request within window expires at valid_timestamps[0] + window_seconds
            # Remaining wait time until a request slot becomes available:
            remaining_cooldown = (valid_timestamps[0] + window_seconds) - now
            retry_after = max(1, int(remaining_cooldown) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds}s.",
                headers={"Retry-After": str(retry_after)},
            )

        valid_timestamps.append(now)
        _request_records[key] = valid_timestamps


def reset_rate_limits() -> None:
    """Utility to clear rate limiter records during testing."""
    with _records_lock:
        _request_records.clear()
