"""
Small, dependency-free security helpers shared across apps.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("edukenya.security")


class SecurityHeadersMiddleware:
    """Adds headers Django 5.2 does not set on its own."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", settings.CONTENT_SECURITY_POLICY)
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
        )
        # Authenticated pages must never be stored by shared caches/proxies.
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            response.setdefault("Cache-Control", "no-store, private")
        return response


def client_ip(request):
    """
    Best-effort client IP. Only reads X-Forwarded-For when we know how many
    trusted proxies sit in front of us; otherwise it is trivially spoofable.
    """
    hops = settings.TRUSTED_PROXY_COUNT
    if hops > 0:
        forwarded = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _bucket_key(scope, identity):
    digest = hashlib.sha256(str(identity).lower().encode()).hexdigest()[:32]
    return f"rl:{scope}:{digest}"


def rate_limited(scope, identity, *, increment=True):
    """
    Fixed-window rate limiter backed by the shared cache.
    Returns True when `identity` has exceeded the limit for `scope`.
    """
    limit, window = settings.RATE_LIMITS[scope]
    key = _bucket_key(scope, identity)
    if not increment:
        return cache.get(key, 0) >= limit
    if cache.add(key, 1, timeout=window):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:  # expired between add() and incr()
            cache.set(key, 1, timeout=window)
            count = 1
    if count > limit:
        logger.warning("rate limit hit scope=%s count=%s", scope, count)
        return True
    return False


def reset_rate_limit(scope, identity):
    cache.delete(_bucket_key(scope, identity))
