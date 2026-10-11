import time
from typing import Dict
from fastapi import Request, HTTPException, status

# In-memory sliding window rate limiter
# Key: client_ip (or identifier) -> list of timestamp floats
# NOTE: Process-local in-memory state. In single-process development / demo deployments,
# this provides lightweight zero-dependency protection against basic flooding and brute-force attempts.
# PRODUCTION DEPLOYMENT LIMITATION:
# In multi-worker (e.g. Uvicorn with multiple workers) or horizontally autoscaled multi-container
# deployments, each process maintains an independent window memory. For distributed production clusters,
# this mechanism should be backed by a centralized key-value store (e.g., Redis or Valkey) using
# an atomic sliding-window script or token-bucket algorithm.
_request_records: Dict[str, list[float]] = {}

def check_rate_limit(
    request: Request,
    max_requests: int = 60,
    window_seconds: int = 60,
    action_key: str = "default",
) -> None:
    """
    Enforces in-memory sliding window rate limits based on client IP.
    Raises HTTPException(429) if exceeded.

    Single-process scope: Tracks request timestamps within local process memory.
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"{action_key}:{client_ip}"
    now = time.time()
    cutoff = now - window_seconds

    timestamps = _request_records.get(key, [])
    # Filter out entries outside current window
    valid_timestamps = [t for t in timestamps if t > cutoff]

    if len(valid_timestamps) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds}s.",
            headers={"Retry-After": str(int(window_seconds))},
        )

    valid_timestamps.append(now)
    _request_records[key] = valid_timestamps

def reset_rate_limits() -> None:
    """Utility to clear rate limiter records during testing."""
    _request_records.clear()
