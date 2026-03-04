from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import json
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
STATUS_JSON = DATA_DIR / "status.json"

app = FastAPI(title="Zigma Site Monitor")

# Serve frontend
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/api/status")
def api_status():
    data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )