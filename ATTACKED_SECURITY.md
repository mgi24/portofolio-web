# Attacker Showcase: implementation and local preview

## Scope

- `/attacked` extends the existing `templates/base.html`, sharing its header, language switcher, fonts, colors, container, and card styles.
- The 22 August entry contains the incident title, isolated deface preview, attack times/explanation, and `Solusi: Shutdown + Rebuild VM`. The 20 August entry contains the user-reported XSS incident, local screenshot, 17:00 WIB timestamp, and the supplied Solusi/Future text.
- The new `/demo` card uses the existing `demo-grid`, `demo-title`, `demo-desc`, and glowing `demo-btn` classes. It has no archive label, sequence number, date, or arrow.
- Its domain label reads `misbahwork.my.id/attacked`. Timeline timestamps use decorative icons, colored emphasis, and connected dots; the incident text is unchanged.
- The original base/index/contact/phone templates, shared stylesheet, translations, service monitoring, dependencies, and existing route policies remain unchanged.
- The preview does not deploy the app, restart production services, or shut down/rebuild a VM. The Future text is a proposed plan; no S3 or sanitization pipeline is implemented by this change.

## Run the preview

```text
python preview_attacked.py
```

Open <http://127.0.0.1:8765/attacked> or <http://127.0.0.1:8765/demo>. Stop with Ctrl+C. An optional `--port` changes the unprivileged port, never the bind address.

The preview binds only to `127.0.0.1`. It preloads a fixed map of public assets and template exports into memory. It does not import the FastAPI application, run Diary, access a database, or expose service endpoints. There is no directory listing, upload, write method, proxy, or request-derived filesystem path.

The original portfolio pages are also exported for local navigation. Only the shared translation JSON, local `i18n.js`, and exact hash-approved initialization script are retained. Service/monitoring/contact-action scripts are omitted in these preview exports; CSP blocks external frames and all connections. The corresponding production templates are untouched. The existing language switcher works locally.

Host/Origin and Fetch Metadata checks reject foreign hosts and cross-site requests. The only exception is the exact public PNG path when requested as a `no-cors` image, including an opaque `null` origin. This is needed because a sandbox without `allow-same-origin` labels even its local image request as cross-site. Script/document requests, other paths, query variants, and foreign Host headers remain blocked. Connections time out after five seconds; worker concurrency is capped. No cookies or CORS permissions are added.

## Isolated deface preview

`/attacked/preview/2026-08-22` serves a fixed, manually reconstructed HTML file. It has no JavaScript, event handlers, forms, active links, remote resources, or template evaluation. The original application, `.env`, scripts, and database are never executed or copied.

Its iframe has an empty `sandbox`, without `allow-scripts` or `allow-same-origin`. The preview response additionally sets CSP `sandbox`; inline CSS requires its exact SHA-256 hash. `frame-ancestors 'self'` and `X-Frame-Options: SAMEORIGIN` allow only the intended embedding. The containing history page cannot itself be framed.

The history page allows the existing local language script and the exact hash of the base initialization script. It does not allow arbitrary inline JavaScript or inline event handlers, and `connect-src 'none'` blocks service calls. Existing inline portfolio styling is allowed; shared source files are not changed.

The downloaded PNG is served as `image/png` with `nosniff`. Only this public PNG has `Cross-Origin-Resource-Policy: cross-origin`, allowing the opaque sandbox origin to display it. That exception does not apply to HTML, scripts, or any private files. No CORS access is granted.

The 20 August screenshot is displayed directly as a local JPEG, not embedded attacker HTML. The preview allowlist adds only `/static/attacked/wowoksec.jpg`, served as `image/jpeg` with `nosniff` and `Cross-Origin-Resource-Policy: same-origin`; the sandbox exception is not expanded.

References: [MDN iframe sandbox](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe#sandbox), [MDN CSP sandbox](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/sandbox), [Python HTTP server security considerations](https://docs.python.org/3/library/http.server.html#security-considerations).

## Sources and missing media

- Timeline: the supplied forensic report, analyzed 26–27 August 2026. The raw report is not served.
- The separate XSS entry at 17:00 WIB on 20 August 2026 and its Solusi/Future text were supplied by the user. `assets/attacked/wowoksec.jpg` is the user-provided 820 × 956 JPEG; its original bytes are preserved. This entry is not presented as a conclusion from the 22 August forensic report.
- Source template SHA-256 remains `0cd07cc333c57669d121080c040fda27426d5ad7702e63da905e830ef4f47fe6`; this describes the original, not the reconstructed preview.
- The PNG referenced by the deface at `https://i.ibb.co.com/v6Fbn90D/00-Nksd989.png` was downloaded and inspected. Its PNG signature, dimensions (687 × 742), all chunk checksums, and end-of-file marker were validated before saving `assets/attacked/deface-2026-08-22.png`. It matches the appearance of the user-supplied Facebook screenshot.
- The separate GIF at the original Diary media endpoint could not be retrieved because DNS resolution timed out. It is omitted, not replaced with an unrelated image or fetched by visitors.
- ASCII art, alias, quotations, and selected terminal text are preserved; the account path is redacted, kernel details omitted, marquee made static, and scripts/telemetry removed.
- No intermediate deface versions, completed recovery, host compromise, or complete database integrity are asserted. Passwords, tokens, attacker IP/email identifiers, key material, and raw logs are not published.

## Checks and limits

```text
python -X utf8 -m unittest discover -s tests -v
python -m pip check
git diff --check
```

The tests cover shared-header reuse, minimal content, the original button class, script/CSS hash validity, local image references, sandbox isolation, fixed-file responses, blocked traversal/secret paths, Host/Origin checks, unsupported methods, and integration with existing FastAPI routes. UTF-8 mode matches the Linux deployment without modifying the legacy locale-dependent content loader.

This is not a guarantee of zero vulnerabilities or an audit of existing application code, unpinned dependencies, browser/OS, or infrastructure. The Python preview server is local-only: do not expose it using a tunnel, wildcard interface, or public reverse proxy. Any later production deployment must preserve and verify these scoped headers after its proxy/CDN layer.
