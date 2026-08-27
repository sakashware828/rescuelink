import os
import json
from fastapi import FastAPI, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RescueLink API")

# Resolve absolute path to project directories
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Mount static files (CSS, JS, Images)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Configure Jinja2 Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR if os.path.exists(TEMPLATES_DIR) else BASE_DIR)

# Active WebSocket connections for live telemetry
active_connections: list[WebSocket] = []

@app.get("/")
async def serve_home(request: Request):
    """Serves the main website with updated HTML appearance."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/profile")
async def get_profile():
    return {"message": "Profile GET endpoint active"}

@app.post("/profile")
async def update_profile(data: dict):
    return {"status": "success", "received": data}

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast incoming updates to connected clients
            for connection in active_connections:
                await connection.send_text(data)
    except WebSocketDisconnect:
        active_connections.remove(websocket)