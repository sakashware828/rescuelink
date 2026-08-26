import json
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="RescueLink API")

# Mount static directory for CSS/JS assets if needed
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# --- In-Memory Data Storage ---
# Stores registered profile details indexed by device_id
registered_profiles = {}


# --- Pydantic Data Models ---
class RegistrationSchema(BaseModel):
    device_id: str
    full_name: str
    blood_group: str = "Not specified"
    allergies: str = "None reported"


class TelemetrySchema(BaseModel):
    device_id: str
    latitude: float
    longitude: float
    sos_triggered: bool = False
    fall_detected: bool = False


# --- WebSocket Manager for Live Telemetry ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()


# --- HTML Page Routes ---
@app.get("/")
async def root():
    return FileResponse("app/static/dashboard.html")

@app.get("/registration")
async def get_registration_page():
    return FileResponse("app/static/registration.html")

@app.get("/profile")
async def get_profile_page():
    return FileResponse("app/static/profile.html")

@app.get("/dashboard")
async def get_dashboard_page():
    return FileResponse("app/static/dashboard.html")


# --- REST API Endpoints ---
@app.post("/api/v1/register")
async def register_profile(data: RegistrationSchema):
    """Saves user profile and links it with their device ID."""
    registered_profiles[data.device_id] = data.dict()
    return {
        "status": "SUCCESS",
        "message": f"Device {data.device_id} registered successfully.",
        "data": data.dict()
    }


@app.post("/api/v1/telemetry")
async def receive_telemetry(data: TelemetrySchema):
    """
    Endpoint for hardware devices (ESP32) or simulation tools to POST telemetry data.
    Enriches incoming data with user profile information and broadcasts to the dashboard via WebSockets.
    """
    profile = registered_profiles.get(data.device_id, {})
    
    payload = {
        "device_id": data.device_id,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "sos_triggered": data.sos_triggered,
        "fall_detected": data.fall_detected,
        "victim_name": profile.get("full_name", "Unknown Victim"),
        "blood_group": profile.get("blood_group", "Unknown"),
        "critical_allergies": profile.get("allergies", "None")
    }

    # Broadcast enriched alert to all connected responder dashboards
    await manager.broadcast(payload)
    return {"status": "BROADCASTED", "payload": payload}


# --- WebSocket Endpoint for Dashboard ---
@app.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection open and listen for optional incoming client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)