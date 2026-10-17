"""US-011 / SEC-022, SEC-024: Content-Security-Policy z nonce i Permissions-Policy (ADR-0004).

Każde żądanie dostaje losowy `request.csp_nonce`; szablony oznaczają nim swoje
skrypty inline (`<script nonce="{{ csp_nonce }}">`). Atrybuty `on*=` są zakazane —
zachowania podpina `static/warehouse/ui.js` po atrybutach `data-*`.
"""

import secrets

from django.conf import settings

PERMISSIONS_POLICY = (
    "camera=(self), geolocation=(), microphone=(), payment=(), usb=(), "
    "magnetometer=(), gyroscope=(), accelerometer=()"
)


def build_policy(nonce: str) -> str:
    return "; ".join(
        (
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}'",
            # Atrybuty style="…" w szablonach — poza zakresem US-011 (kradzież sesji
            # wymaga wykonania skryptu, nie stylu).
            "style-src 'self' 'unsafe-inline'",
            # Etykiety QR jako data:, podgląd kamery skanera jako blob:/MediaStream.
            "img-src 'self' data: blob:",
            "media-src 'self' blob:",
            "font-src 'self'",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        )
    )


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        if response.get("Content-Type", "").startswith("text/html"):
            header = (
                "Content-Security-Policy-Report-Only"
                if settings.CSP_REPORT_ONLY
                else "Content-Security-Policy"
            )
            response.setdefault(header, build_policy(request.csp_nonce))
        return response


def csp_context(request):
    """Context processor: `{{ csp_nonce }}` w szablonach."""
    return {"csp_nonce": getattr(request, "csp_nonce", "")}
