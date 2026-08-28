"""Run with: python -X utf8 -m unittest discover -s tests -v

UTF-8 mode matches the Linux deployment's locale without changing legacy code.
"""

import base64
import hashlib
from html.parser import HTMLParser
from http.client import HTTPConnection
from pathlib import Path
import re
from threading import Thread
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from attacked_archive import (
    ARCHIVE_FILES, HISTORY_CSP, HISTORY_ROUTES, PORTFOLIO_INIT_HASH,
    PREVIEW_IMAGE_ROUTE, PREVIEW_ROUTE, PREVIEW_STYLE_HASH, archive_headers,
)
from main import app
from preview_attacked import LocalPreviewServer, PREVIEW_TEMPLATES, load_public_pages

ROOT = Path(__file__).resolve().parents[1]


class PageAudit(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class ArchiveContentTests(unittest.TestCase):
    def test_archive_html_has_no_active_content_or_remote_references(self):
        for path in set(ARCHIVE_FILES.values()):
            with self.subTest(path=path):
                html = (ROOT / path).read_text(encoding="utf-8")
                parsed = PageAudit(html)
                ids = []
                for tag, attrs in parsed.elements:
                    self.assertNotIn(tag, {"script", "form", "input", "button", "object", "embed", "base", "audio", "video", "marquee"})
                    self.assertFalse(any(name.startswith("on") for name in attrs))
                    self.assertNotIn("srcdoc", attrs)
                    self.assertNotEqual(attrs.get("http-equiv", "").lower(), "refresh")
                    if "id" in attrs:
                        ids.append(attrs["id"])
                    for key in ("href", "src", "action", "poster", "srcset", "data", "background"):
                        if key in attrs:
                            self.assertTrue(attrs[key].startswith(("/", "#")), (key, attrs[key]))
                            self.assertFalse(attrs[key].startswith("//"))
                self.assertEqual(len(ids), len(set(ids)), "Duplicate anchors / accessible labels")
                for tag, attrs in parsed.elements:
                    if attrs.get("href", "").startswith("#"):
                        self.assertIn(attrs["href"][1:], ids)
                self.assertNotIn("<nav", html)
                self.assertNotIn("<header", html)
                self.assertIn('name="viewport"', html)

    def test_artifact_is_inert_and_its_style_hash_matches_both_policies(self):
        html = (ROOT / ARCHIVE_FILES[PREVIEW_ROUTE]).read_text(encoding="utf-8")
        style_blocks = re.findall(r"<style>(.*?)</style>", html, re.S)
        self.assertEqual(len(style_blocks), 1)
        digest = base64.b64encode(hashlib.sha256(style_blocks[0].encode()).digest()).decode()
        self.assertEqual(digest, PREVIEW_STYLE_HASH)
        self.assertIn(f"'sha256-{digest}'", html)
        response_policy = archive_headers(PREVIEW_ROUTE)["Content-Security-Policy"]
        self.assertIn(f"'sha256-{digest}'", response_policy)
        self.assertIn("sandbox", response_policy.split("; "))
        self.assertNotIn("unsafe-inline", response_policy)
        self.assertNotIn("allow-scripts", response_policy)
        self.assertNotIn("allow-same-origin", response_policy)
        self.assertFalse(any(tag in {"a", "iframe", "link"} for tag, _ in PageAudit(html).elements))
        images = [attrs for tag, attrs in PageAudit(html).elements if tag == "img"]
        self.assertEqual([attrs["src"] for attrs in images], [PREVIEW_IMAGE_ROUTE])
        self.assertNotRegex(style_blocks[0].lower(), r"url\s*\(|@import|expression\s*\(")

    def test_embed_has_empty_sandbox_and_local_target(self):
        html = load_public_pages()["/attacked"][0].decode("utf-8")
        frames = [attrs for tag, attrs in PageAudit(html).elements if tag == "iframe"]
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["sandbox"], "")
        self.assertEqual(frames[0]["src"], PREVIEW_ROUTE)
        self.assertEqual(frames[0]["referrerpolicy"], "no-referrer")
        self.assertTrue(frames[0]["title"])

    def test_all_archive_assets_and_links_resolve_without_external_services(self):
        pages = load_public_pages()
        for route in list(ARCHIVE_FILES) + list(HISTORY_ROUTES):
            html = pages[route][0].decode()
            for tag, attrs in PageAudit(html).elements:
                for key in ("src", "href"):
                    target = attrs.get(key, "")
                    if target.startswith("/"):
                        self.assertIn(target, pages)
        for stylesheet in ("attacked.css",):
            css = (ROOT / "assets" / stylesheet).read_text(encoding="utf-8")
            self.assertNotRegex(css.lower(), r"@import|url\s*\(|expression\s*\(")

    def test_preview_keeps_shared_header_scripts_but_not_service_scripts(self):
        pages = load_public_pages()
        for route in PREVIEW_TEMPLATES:
            html = pages[route][0].decode()
            scripts = [(attrs, content) for attrs, content in re.findall(r"<script([^>]*)>(.*?)</script>", html, re.S)]
            self.assertEqual(len(scripts), 3)
            for attrs, content in scripts:
                if 'src="/static/i18n.js"' in attrs or 'type="application/json"' in attrs:
                    continue
                digest = base64.b64encode(hashlib.sha256(content.encode()).digest()).decode()
                self.assertEqual(digest, PORTFOLIO_INIT_HASH)
        self.assertNotIn("setInterval(fetchResource", pages["/demo"][0].decode())
        self.assertNotIn("async function loadDiary", pages["/"][0].decode())

    def test_demo_entry_reuses_original_glow_button_without_extra_labels(self):
        html = load_public_pages()["/demo"][0].decode()
        entry = re.search(r'<section[^>]*aria-labelledby="attacker-showcase-title".*?</section>', html, re.S).group(0)
        self.assertIn("Pain is the greatest teacher. Learn from it!", entry)
        self.assertIn('<div class="domain-label">misbahwork.my.id/attacked</div>', entry)
        self.assertLess(entry.index("Pain is the greatest teacher."), entry.index("misbahwork.my.id/attacked"))
        self.assertIn('<a href="/attacked" class="demo-btn">Show History</a>', entry)
        for extra in ("INCIDENT ARCHIVE", "001", "22.08.2026", "↗", "showcase-kicker", "showcase-path"):
            self.assertNotIn(extra, entry)

    def test_history_reuses_shared_header_and_contains_two_simple_entries(self):
        pages = load_public_pages()
        history = pages["/attacked"][0].decode()
        header = re.search(r"<nav>.*?</nav>", history, re.S).group(0)
        for route in ("/", "/demo", "/contact"):
            self.assertEqual(header, re.search(r"<nav>.*?</nav>", pages[route][0].decode(), re.S).group(0))
        self.assertIn('href="/static/style.css"', history)
        content = re.search(r'<main class="container".*?</main>', history, re.S).group(0)
        entries = re.findall(r"<article\b.*?</article>", content, re.S)
        self.assertEqual(len(entries), 2)
        for entry in entries:
            self.assertEqual(re.findall(r"<h2[^>]*>(.*?)</h2>", entry), ["Preview Hack", "Jam attack dan penjelasan"])
        self.assertIn("22 Agustus 2026 - Deface diary.misbahwork.my.id dan full root compromise container", entries[0])
        self.assertIn("Shutdown + Rebuild VM", entries[0])
        self.assertIn("20 Agustus 2026 - XSS luck.misbahwork.my.id", entries[1])
        self.assertIn('<time datetime="2026-08-20T17:00:00+07:00">17:00 WIB</time>', entries[1])
        self.assertIn("<strong>Solusi:</strong> Quick fix sanitize field", entries[1])
        self.assertIn("<strong>Future:</strong> Semua files akan disanitize ke S3 storage sebelum saved ke server", entries[1])
        images = [attrs for tag, attrs in PageAudit(entries[1]).elements if tag == "img"]
        self.assertEqual([attrs["src"] for attrs in images], ["/static/attacked/wowoksec.jpg"])
        self.assertTrue(images[0]["alt"])
        for tag, attrs in PageAudit(content).elements:
            self.assertFalse(any(name.startswith("on") for name in attrs))
        for extra in ("<script", "<form", "<object", "<embed", "<nav", "<aside", "<footer", "<details", "CASE FILE", "EXHIBIT", "Showcase."):
            self.assertNotIn(extra, content)

    def test_header_csp_allows_only_the_exact_shared_inline_initializer(self):
        base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
        init = re.search(r"<script>(.*?)</script>", base, re.S).group(1)
        digest = base64.b64encode(hashlib.sha256(init.encode()).digest()).decode()
        self.assertEqual(digest, PORTFOLIO_INIT_HASH)
        script_policy = next(part for part in HISTORY_CSP.split("; ") if part.startswith("script-src "))
        self.assertIn(digest, script_policy)
        self.assertNotIn("unsafe-inline", script_policy)
        self.assertIn("connect-src 'none'", HISTORY_CSP)

    def test_downloaded_raster_is_local_and_can_load_in_opaque_sandbox(self):
        data, mime = load_public_pages()[PREVIEW_IMAGE_ROUTE]
        self.assertEqual(mime, "image/png")
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"))
        self.assertEqual(archive_headers(PREVIEW_IMAGE_ROUTE)["Cross-Origin-Resource-Policy"], "cross-origin")


class PreviewHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalPreviewServer(port=0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, path, method="GET", headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_bound_only_to_loopback(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_pages_and_assets_are_exact_allowlisted_bytes(self):
        for path, (expected, media_type) in self.server.pages.items():
            with self.subTest(path=path):
                status, headers, body = self.request(path, headers={"Host": f"127.0.0.1:{self.server.server_port}"})
                self.assertEqual(status, 200)
                self.assertEqual(body, expected)
                self.assertEqual(headers["Content-Type"], media_type)
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                if path in PREVIEW_TEMPLATES:
                    self.assertEqual(headers["Content-Security-Policy"], HISTORY_CSP)
                else:
                    self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                self.assertNotIn("Set-Cookie", headers)

    def test_head_returns_headers_but_no_body(self):
        status, headers, body = self.request("/attacked", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(int(headers["Content-Length"]), len(self.server.pages["/attacked"][0]))

    def test_no_filesystem_access_during_requests(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("runtime file access")):
            self.assertEqual(self.request("/attacked")[0], 200)

    def test_traversal_secrets_source_and_services_are_unreachable(self):
        probes = (
            "/.env", "/.git/config", "/main.py", "/attacked_archive.py",
            "/museum/index.html", "/templates/base.html", "/static/../main.py",
            "/attacked/../../.env", "/attacked/%2e%2e/.env", "/%252e%252e/.env",
            "/..%5c..%5cWindows/win.ini", "/attacked%00", "/attacked;file=.env",
            "/attacked?config=../../.env", "/attacked#fragment", "/attacked\\..\\.env",
            "/attacked/exhibit-001", "/attacked/exhibit-001.html", "/static/", "/content/en.json",
            "/resource", "/api/media/test.gif", "/docs", "/openapi.json",
            "http://evil.invalid/attacked",
        )
        for path in probes:
            with self.subTest(path=path):
                status, headers, body = self.request(path, headers={"Host": f"127.0.0.1:{self.server.server_port}"})
                self.assertEqual(status, 404)
                self.assertEqual(body, b"Request rejected.\n")
                self.assertIn("script-src 'none'", headers["Content-Security-Policy"])

    def test_mutating_and_proxy_methods_rejected(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
            with self.subTest(method=method):
                status, headers, _ = self.request("/attacked", method=method)
                self.assertEqual(status, 405)
                self.assertEqual(headers["Allow"], "GET, HEAD")

    def test_opaque_sandbox_can_fetch_only_the_fixed_public_png_as_an_image(self):
        sandbox_headers = {
            "Sec-Fetch-Site": "cross-site", "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
        }
        for origin_headers in ({}, {"Origin": "null"}):
            status, headers, body = self.request(PREVIEW_IMAGE_ROUTE, headers={**sandbox_headers, **origin_headers})
            self.assertEqual(status, 200)
            self.assertEqual(headers["Content-Type"], "image/png")
            self.assertEqual(body, self.server.pages[PREVIEW_IMAGE_ROUTE][0])
            self.assertNotIn("Access-Control-Allow-Origin", headers)
        for path in ("/attacked", PREVIEW_ROUTE, "/static/style.css", "/static/i18n.js", "/static/attacked/wowoksec.jpg", "/.env", PREVIEW_IMAGE_ROUTE + "?x=1"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path, headers=sandbox_headers)[0], 403)
        for overrides in (
            {"Sec-Fetch-Dest": "script"}, {"Sec-Fetch-Mode": "cors"},
            {"Sec-Fetch-Dest": "document"}, {"Origin": "https://evil.invalid"},
            {"Host": "evil.invalid"},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(self.request(PREVIEW_IMAGE_ROUTE, headers={**sandbox_headers, **overrides})[0], 403)

    def test_host_origin_and_cross_site_access_rejected(self):
        for headers in (
            {"Host": "evil.invalid"}, {"Host": "localhost.evil.invalid"},
            {"Host": "127.0.0.1:1"}, {"Origin": "https://evil.invalid"},
            {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"},
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.request("/attacked", headers=headers)[0], 403)
        port = self.server.server_port
        for host in (f"localhost:{port}", f"127.0.0.1:{port}"):
            self.assertEqual(self.request("/attacked", headers={"Host": host})[0], 200)

    def test_duplicate_host_headers_rejected(self):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.putrequest("GET", "/attacked", skip_host=True)
            connection.putheader("Host", f"localhost:{self.server.server_port}")
            connection.putheader("Host", "evil.invalid")
            connection.endheaders()
            self.assertEqual(connection.getresponse().status, 403)
        finally:
            connection.close()


class PortfolioIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_archive_routes_use_exact_html_and_strict_headers(self):
        for route, relative_path in ARCHIVE_FILES.items():
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, (ROOT / relative_path).read_bytes())
                self.assertEqual(response.headers["content-security-policy"], archive_headers(route)["Content-Security-Policy"])
                self.assertEqual(response.headers["x-frame-options"], "SAMEORIGIN")

    def test_history_routes_render_shared_layout_with_scoped_headers(self):
        for route in HISTORY_ROUTES:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertIn("<nav>", response.text)
            self.assertIn('href="/static/style.css"', response.text)
            self.assertIn("Shutdown + Rebuild VM", response.text)
            self.assertIn("Quick fix sanitize field", response.text)
            self.assertEqual(response.headers["content-security-policy"], HISTORY_CSP)
            self.assertEqual(response.headers["x-frame-options"], "DENY")

    def test_xss_screenshot_is_served_as_the_original_local_jpeg(self):
        response = self.client.get("/static/attacked/wowoksec.jpg")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.content, (ROOT / "assets/attacked/wowoksec.jpg").read_bytes())
        self.assertTrue(response.content.startswith(b"\xff\xd8\xff"))

    def test_existing_pages_and_their_security_policy_stay_unchanged(self):
        for route in ("/", "/demo", "/contact", "/phone"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn("script-src 'self' 'unsafe-inline'", response.headers["content-security-policy"])
                self.assertIn("frame-src https://www.youtube.com", response.headers["content-security-policy"])
                self.assertEqual(response.headers["referrer-policy"], "strict-origin-when-cross-origin")
                self.assertEqual(response.headers["x-frame-options"], "DENY")
        demo = self.client.get("/demo").text
        self.assertIn("Show History", demo)
        self.assertIn('href="/attacked"', demo)
        self.assertIn("setInterval(fetchResource, 1000)", demo)
        self.assertIn('src="/static/i18n.js"', demo)

    def test_archive_routes_do_not_accept_user_file_selection(self):
        response = self.client.get("/attacked?config=../../.env&file=main.py")
        self.assertEqual(response.content, self.client.get("/attacked").content)
        for path in ("/attacked/secret", "/attacked/.env", "/attacked/%2e%2e/main.py", "/museum/exhibit-001.html"):
            self.assertEqual(self.client.get(path).status_code, 404)
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertEqual(self.client.request(method, "/attacked").status_code, 405)


if __name__ == "__main__":
    unittest.main()
