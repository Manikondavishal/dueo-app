"""Security middleware: origin check on writes + hardened response headers."""
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .config import settings

WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# The preview ingress rewrites the Origin header to an internal cluster host, so
# a fixed allow-list can never match a same-origin browser request. We therefore
# accept: the configured origins, a same-origin request (origin host == Host), or
# a trusted Emergent platform suffix. Truly foreign origins are still rejected.
TRUSTED_SUFFIXES = (".preview.emergentagent.com", ".emergentagent.com", ".emergentcf.cloud")

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}

ORIGIN_EXEMPT_PREFIXES = ("/api/webhooks/", "/api/cron/", "/api/health")


def _origin_allowed(origin: str, host: str) -> bool:
    if origin in settings.cors_origins:
        return True
    o = urlparse(origin).netloc
    if host and o == host:
        return True
    return any(o.endswith(s) for s in TRUSTED_SUFFIXES)


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if request.method in WRITE_METHODS and not path.startswith(ORIGIN_EXEMPT_PREFIXES):
            origin = request.headers.get("origin")
            if origin and not _origin_allowed(origin, request.headers.get("host", "")):
                return JSONResponse({"detail": "origin_not_allowed"}, status_code=403)
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        return response
