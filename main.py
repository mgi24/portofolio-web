import json
import time
from pathlib import Path

from fastapi import FastAPI, Request, Cookie, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "assets")), name="static")

def load_content(lang: str) -> dict:
    file_path = BASE_DIR / "content" / f"{lang}.json"
    if not file_path.exists():
        file_path = BASE_DIR / "content" / "en.json"
    with open(file_path, "r") as f:
        return json.load(f)

# --- Resource monitoring ---

_prev_cpu = None

def _read_cpu():
    with open("/proc/stat") as f:
        parts = f.readline().split()
    vals = [int(v) for v in parts[1:]]
    idle = vals[3] + vals[4]
    total = sum(vals)
    return total, idle

def _read_ram():
    mem = {}
    with open("/proc/meminfo") as f:
        for line in f:
            parts = line.split()
            key = parts[0].rstrip(":")
            if key in ("MemTotal", "MemAvailable"):
                mem[key] = int(parts[1])  # kB
    return mem

_prev_net = None

def _read_net(iface):
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                line_s = line.strip()
                if line_s.startswith(iface + ":"):
                    parts = line_s.split()
                    return int(parts[1]), int(parts[9])
    except:
        pass
    return 0, 0

@app.get("/resource")
async def get_resource(request: Request):
    global _prev_cpu, _prev_net

    total, idle = _read_cpu()
    cpu = 0.0
    if _prev_cpu is not None:
        td = total - _prev_cpu[0]
        id = idle - _prev_cpu[1]
        if td > 0:
            cpu = round((td - id) / td * 100, 1)
    _prev_cpu = (total, idle)

    ram = _read_ram()
    total_kb = ram.get("MemTotal", 0)
    avail_kb = ram.get("MemAvailable", 0)
    used_kb = total_kb - avail_kb
    ram_pct = round(used_kb / total_kb * 100, 1) if total_kb > 0 else 0

    iface = "eth0"
    rx, tx = _read_net(iface)
    now = time.time()
    rx_mbps = tx_mbps = 0.0
    if _prev_net is not None:
        dt = now - _prev_net["time"]
        if dt > 0:
            rx_mbps = max(0, (rx - _prev_net["rx"]) * 8 / 1_000_000 / dt)
            tx_mbps = max(0, (tx - _prev_net["tx"]) * 8 / 1_000_000 / dt)
    _prev_net = {"rx": rx, "tx": tx, "time": now}
    max_mbps = 3000

    return {
        "cpu": cpu,
        "ram_percent": ram_pct,
        "ram_used_gb": round(used_kb / 1_048_576, 1),
        "ram_total_gb": round(total_kb / 1_048_576, 1),
        "cores": 4,
        "arch": "arm64",
        "rx_mbps": round(rx_mbps, 2),
        "tx_mbps": round(tx_mbps, 2),
        "rx_pct": min(round(rx_mbps / max_mbps * 100, 2), 100),
        "tx_pct": min(round(tx_mbps / max_mbps * 100, 2), 100),
        "usage_pct": min(round((rx_mbps + tx_mbps) / max_mbps * 100, 2), 100),
        "max_mbps": max_mbps,
    }

# --- Pages ---

@app.get("/")
async def index(request: Request, lang: str = Cookie(default="en")):
    # Sanitize lang parameter to prevent XSS
    if lang not in ("en", "id"):
        lang = "en"
    content = load_content(lang)
    return templates.TemplateResponse(request, "index.html", {"content": content, "lang": lang})

@app.get("/demo")
async def demo(request: Request, lang: str = Cookie(default="en")):
    # Sanitize lang parameter to prevent XSS
    if lang not in ("en", "id"):
        lang = "en"
    content = load_content(lang)
    return templates.TemplateResponse(request, "demo.html", {"content": content, "lang": lang})

@app.get("/contact")
async def contact(request: Request, lang: str = Cookie(default="en")):
    # Sanitize lang parameter to prevent XSS
    if lang not in ("en", "id"):
        lang = "en"
    content = load_content(lang)
    return templates.TemplateResponse(request, "contact.html", {"content": content, "lang": lang})

@app.get("/phone")
async def phone(request: Request, lang: str = Cookie(default="en")):
    # Sanitize lang parameter to prevent XSS
    if lang not in ("en", "id"):
        lang = "en"
    content = load_content(lang)
    return templates.TemplateResponse(request, "phone.html", {"content": content, "lang": lang})

# --- Safe redirect paths (whitelist) ---
_SAFE_PATHS = {"", "/", "/demo", "/contact", "/phone"}

@app.get("/set-language/{lang}")
async def set_language(lang: str, request: Request, next: str = "/"):
    if lang not in ("en", "id"):
        raise HTTPException(status_code=400, detail="Invalid language")
    # Validate next is a known safe path to prevent open redirect
    clean_next = next.rstrip("/") or "/"
    if clean_next not in _SAFE_PATHS and clean_next != "/":
        clean_next = "/"
    response = RedirectResponse(url=clean_next)
    response.set_cookie(key="lang", value=lang)
    return response
