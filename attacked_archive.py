"""Fixed public history assets and route-specific security headers."""

HISTORY_ROUTES = {"/attacked", "/attacked/"}
PREVIEW_ROUTE = "/attacked/preview/2026-08-22"
ARCHIVE_FILES = {PREVIEW_ROUTE: "attacked/diary-2026-08-22.html"}
PREVIEW_IMAGE_ROUTE = "/static/attacked/deface-2026-08-22.png"
PORTFOLIO_INIT_HASH = "GDVS5E1cn7ByK5DSZ8e3pdPJW8f/fCcGWxESCqa4BVg="
PREVIEW_STYLE_HASH = "AYTmfU4BdWByDGGywoCL6afH2j9UX6LqiVIyKD24Knc="

HISTORY_CSP = (
    "default-src 'none'; "
    f"script-src 'self' 'sha256-{PORTFOLIO_INIT_HASH}'; script-src-attr 'none'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self'; frame-src 'self'; "
    "connect-src 'none'; base-uri 'none'; form-action 'none'; "
    "object-src 'none'; frame-ancestors 'none'"
)
PREVIEW_CSP = (
    "default-src 'none'; script-src 'none'; "
    f"style-src 'sha256-{PREVIEW_STYLE_HASH}'; img-src 'self'; "
    "base-uri 'none'; form-action 'none'; object-src 'none'; connect-src 'none'; "
    "frame-ancestors 'self'; sandbox"
)
STATIC_CSP = (
    "default-src 'none'; script-src 'none'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self'; frame-src 'self'; connect-src 'none'; base-uri 'none'; "
    "form-action 'none'; object-src 'none'; frame-ancestors 'none'"
)


def archive_headers(path):
    """Do not change policies for existing portfolio pages or shared assets."""
    if path not in HISTORY_ROUTES and path not in ARCHIVE_FILES and path != PREVIEW_IMAGE_ROUTE:
        return {}
    preview = path == PREVIEW_ROUTE
    image = path == PREVIEW_IMAGE_ROUTE
    return {
        "Content-Security-Policy": PREVIEW_CSP if preview else STATIC_CSP if image else HISTORY_CSP,
        "X-Frame-Options": "SAMEORIGIN" if preview else "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
            "serial=(), bluetooth=(), fullscreen=()"
        ),
        # The public PNG must also be loadable inside the opaque sandbox origin.
        "Cross-Origin-Resource-Policy": "cross-origin" if image else "same-origin",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cache-Control": "no-store",
    }
