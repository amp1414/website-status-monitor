from pathlib import Path
import json

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
STATUS_JSON = DATA_DIR / "status.json"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"

app = FastAPI(title="Zigma Site Monitor")

# Serve frontend files (index.html, app.js, styles.css)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Serve generated screenshots
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=SCREENSHOTS_DIR), name="screenshots")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/status")
def api_status():
    if not STATUS_JSON.exists():
        return JSONResponse(
            content={"generated_at": None, "window_days": 7, "sites": []},
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )