import json
from typing import List
from fastapi import FastAPI, Depends, Form, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import init_db, get_db, VictimProfile, IncidentLog

app = FastAPI(title="RescueLink System")

# Mount static directory for CSS, JS, and static HTML files
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Initialize database tables on application startup
@app.on_event("startup")
def startup_event():
    init_db()


# -----------------------------------------------------------------------------
# WebSocket Connection Manager for Real-Time Telemetry Broadcasting
# -----------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


manager = ConnectionManager()


# -----------------------------------------------------------------------------
# Frontend Page Routes
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard():
    with open("app/static/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/registration", response_class=HTMLResponse)
async def read_registration():
    with open("app/static/registration.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/profile", response_class=HTMLResponse)
async def read_profile():
    with open("app/static/profile.html", "r", encoding="utf-8") as f:
        return f.read()


# -----------------------------------------------------------------------------
# API Endpoints & Registration Handler
# -----------------------------------------------------------------------------
@app.post("/api/register")
async def register_victim(
    device_id: str = Form(...),
    victim_name: str = Form(...),
    blood_group: str = Form(...),
    critical_allergies: str = Form("None"),
    emergency_contact: str = Form(...),
    db: Session = Depends(get_db)
):
    existing = db.query(VictimProfile).filter(VictimProfile.device_id == device_id).first()
    if existing:
        existing.victim_name = victim_name
        existing.blood_group = blood_group
        existing.critical_allergies = critical_allergies
        existing.emergency_contact = emergency_contact
    else:
        new_profile = VictimProfile(
            device_id=device_id,
            victim_name=victim_name,
            blood_group=blood_group,
            critical_allergies=critical_allergies,
            emergency_contact=emergency_contact
        )
        db.add(new_profile)
    
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/api/telemetry")
async def receive_telemetry(payload: dict, db: Session = Depends(get_db)):
    """
    HTTP POST endpoint for hardware nodes (ESP32 / LoRa gateway) or simulation scripts.
    It links incoming telemetry to registered database profiles and broadcasts live alerts.
    """
    device_id = payload.get("device_id", "UNKNOWN")
    latitude = payload.get("latitude", 0.0)
    longitude = payload.get("longitude", 0.0)
    sos_triggered = payload.get("sos_triggered", False)

    # 1. Save Incident to Database
    incident = IncidentLog(
        device_id=device_id,
        latitude=str(latitude),
        longitude=str(longitude),
        sos_triggered=sos_triggered
    )
    db.add(incident)
    db.commit()

    # 2. Enrich with Victim Profile from DB if available
    profile = db.query(VictimProfile).filter(VictimProfile.device_id == device_id).first()
    enriched_data = {
        "device_id": device_id,
        "latitude": latitude,
        "longitude": longitude,
        "sos_triggered": sos_triggered,
        "victim_name": profile.victim_name if profile else "Unregistered Node",
        "blood_group": profile.blood_group if profile else "N/A",
        "critical_allergies": profile.critical_allergies if profile else "None",
        "emergency_contact": profile.emergency_contact if profile else "N/A"
    }

    # 3. Broadcast to all active WebSocket connected dashboards
    await manager.broadcast(json.dumps(enriched_data))
    return {"status": "success", "data": enriched_data}


# -----------------------------------------------------------------------------
# WebSocket Stream Endpoint
# -----------------------------------------------------------------------------
@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection open to listen or send periodic heartbeats
            data = await websocket.receive_text()
            # If clients send messages, echo back or process accordingly
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/profile/{device_id}")
async def get_victim_profile(device_id: str, db: Session = Depends(get_db)):
    profile = db.query(VictimProfile).filter(VictimProfile.device_id == device_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile