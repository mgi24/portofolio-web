"""Local-only, static portfolio preview. Run: python preview_attacked.py

Does not import main.py, connect to services, or serve a filesystem directory.
Only explicitly listed public files are read, once, before accepting requests.
Exports retain only the trusted shared language switcher; service scripts are omitted.
This preview server is not intended for public or production deployment.
"""

import argparse
import base64
import hashlib
import json
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape

from attacked_archive import (
    ARCHIVE_FILES, HISTORY_CSP, PORTFOLIO_INIT_HASH, PREVIEW_IMAGE_ROUTE,
    STATIC_CSP, archive_headers,
)

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_ASSETS = {
    "/static/attacked.css": ("assets/attacked.css", "text/css; charset=utf-8"),
    PREVIEW_IMAGE_ROUTE: ("assets/attacked/deface-2026-08-22.png", "image/png"),
    "/static/attacked/wowoksec.jpg": ("assets/attacked/wowoksec.jpg", "image/jpeg"),
    "/static/style.css": ("assets/style.css", "text/css; charset=utf-8"),
    "/static/i18n.js": ("assets/i18n.js", "text/javascript; charset=utf-8"),
    "/static/mmvlogo.png": ("assets/mmvlogo.png", "image/png"),
    "/static/profile.jpg": ("assets/profile.jpg", "image/jpeg"),
    "/static/oracle_logo.png": ("assets/oracle_logo.png", "image/png"),
    "/static/cloudflare_logo.png": ("assets/cloudflare_logo.png", "image/png"),
    "/static/wa.svg": ("assets/wa.svg", "image/svg+xml"),
    "/static/fb.svg": ("assets/fb.svg", "image/svg+xml"),
    "/static/discord.svg": ("assets/discord.svg", "image/svg+xml"),
    "/static/email.svg": ("assets/email.svg", "image/svg+xml"),
    "/static/copy.svg": ("assets/copy.svg", "image/svg+xml"),
    "/static/tg.svg": ("assets/tg.svg", "image/svg+xml"),
    "/static/yt.svg": ("assets/yt.svg", "image/svg+xml"),
    "/static/linkedin.svg": ("assets/linkedin.svg", "image/svg+xml"),
    "/static/ig.svg": ("assets/ig.svg", "image/svg+xml"),
}
PREVIEW_TEMPLATES = {
    "/": "index.html", "/demo": "demo.html", "/contact": "contact.html",
    "/phone": "phone.html", "/attacked": "attacked.html", "/attacked/": "attacked.html",
}


class StaticPortfolio(HTMLParser):
    """Keep only the exact shared language scripts in trusted template exports.

    This is not an untrusted-HTML sanitizer. The deface source is never input.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self.in_script = False
        self.script_parts = []
        self.script_attrs = {}
        self.script_open = ""

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True
            self.script_parts = []
            self.script_attrs = dict(attrs)
            self.script_open = self.get_starttag_text()
        elif not self.in_script:
            self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag == "script":
            content = "".join(self.script_parts)
            digest = base64.b64encode(hashlib.sha256(content.encode("utf-8")).digest()).decode()
            attrs = self.script_attrs
            if (attrs.get("src") == "/static/i18n.js"
                    or (attrs.get("type") == "application/json" and attrs.get("id") == "i18n-translations")
                    or ("src" not in attrs and digest == PORTFOLIO_INIT_HASH)):
                self.parts.extend((self.script_open, content, "</script>"))
            self.in_script = False
        elif not self.in_script:
            self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        if not self.in_script and tag != "script":
            self.parts.append(self.get_starttag_text())

    def handle_data(self, data):
        if self.in_script:
            self.script_parts.append(data)
        else:
            self.parts.append(data)

    def handle_entityref(self, name):
        if not self.in_script:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if not self.in_script:
            self.parts.append(f"&#{name};")

    def handle_decl(self, decl):
        if not self.in_script:
            self.parts.append(f"<!{decl}>")


def load_public_pages():
    pages = {}
    for route, relative_path in ARCHIVE_FILES.items():
        pages[route] = ((BASE_DIR / relative_path).read_bytes(), "text/html; charset=utf-8")
    for route, (relative_path, media_type) in PUBLIC_ASSETS.items():
        pages[route] = ((BASE_DIR / relative_path).read_bytes(), media_type)
    env = Environment(
        loader=FileSystemLoader(BASE_DIR / "templates"),
        autoescape=select_autoescape(("html", "xml")),
    )
    contents = {
        lang: json.loads((BASE_DIR / "content" / f"{lang}.json").read_text(encoding="utf-8"))
        for lang in ("en", "id")
    }
    for route, template in PREVIEW_TEMPLATES.items():
        export = StaticPortfolio()
        export.feed(env.get_template(template).render(contents=contents))
        export.close()
        pages[route] = ("".join(export.parts).encode("utf-8"), "text/html; charset=utf-8")
    return pages


class LocalPreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8
    allow_reuse_address = False

    def __init__(self, port=8765):
        self.pages = load_public_pages()
        self.slots = BoundedSemaphore(16)
        # Deliberately no configurable host / wildcard bind.
        super().__init__(("127.0.0.1", port), PreviewHandler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class PreviewHandler(BaseHTTPRequestHandler):
    server_version = "StaticArchivePreview"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        # No query strings, arbitrary headers, or terminal control input in logs.
        pass

    def send_error(self, code, message=None, explain=None):
        # Even parse errors use fixed text and restrictive headers.
        self.respond(code, b"Request rejected.\n", "text/plain; charset=utf-8")

    def respond(self, status, body, media_type, route=""):
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        policy = archive_headers(route) or {
            "Content-Security-Policy": HISTORY_CSP if route in PREVIEW_TEMPLATES else STATIC_CSP,
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
            "Cross-Origin-Resource-Policy": "same-origin",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cache-Control": "no-store",
        }
        for name, value in policy.items():
            self.send_header(name, value)
        if status == 405:
            self.send_header("Allow", "GET, HEAD")
        self.end_headers()
        self.close_connection = True
        if getattr(self, "command", None) != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self):
        port = self.server.server_port
        allowed_hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0] not in allowed_hosts:
            self.send_error(403)
            return
        # An opaque sandbox sends cross-site Fetch Metadata even for this local
        # image. Exempt only this exact, public raster used as a no-cors image.
        sandbox_image = (
            self.path == PREVIEW_IMAGE_ROUTE
            and self.headers.get("Sec-Fetch-Dest") == "image"
            and self.headers.get("Sec-Fetch-Mode") == "no-cors"
        )
        origins = self.headers.get_all("Origin", [])
        allowed_origins = {f"http://{host}" for host in allowed_hosts}
        if sandbox_image:
            allowed_origins.add("null")
        if len(origins) > 1 or (origins and origins[0] not in allowed_origins):
            self.send_error(403)
            return
        if self.headers.get("Sec-Fetch-Site") == "cross-site" and not sandbox_image:
            self.send_error(403)
            return
        try:
            target = urlsplit(self.path)
        except ValueError:
            self.send_error(400)
            return
        # Reject encodings, alternate path spellings, query input and proxies.
        # There is deliberately no URL-to-filesystem path resolution here.
        if (not self.path.startswith("/") or self.path.startswith("//")
                or target.scheme or target.netloc or "?" in self.path or "#" in self.path
                or "%" in self.path or "\\" in self.path):
            self.send_error(404)
            return
        page = self.server.pages.get(target.path)
        if page is None:
            self.send_error(404)
            return
        self.respond(200, *page, route=target.path)

    do_HEAD = do_GET

    def reject_method(self):
        self.send_error(405)

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = do_CONNECT = reject_method


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose an unprivileged port between 1024 and 65535.")
    with LocalPreviewServer(args.port) as server:
        print(f"History: http://127.0.0.1:{server.server_port}/attacked", flush=True)
        print(f"Demo:   http://127.0.0.1:{server.server_port}/demo", flush=True)
        print("Loopback only. Static files only. Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
