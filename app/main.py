import os
import json
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, status, WebSocket, WebSocketDisconnect, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import engine, Base, get_db
from .models import Profile, Alert

# Create database tables
Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rescuelink")

app = FastAPI(
    title="RescueLink API",
    description="IoT Emergency Response & Hardware Profile Management Portal",
    version="2.0.0"
)

# Enable CORS for cross-origin frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Mount static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def render_html(filename: str):
    file_path = os.path.join(STATIC_DIR, filename)
    if not os.path.exists(file_path):
        return HTMLResponse(
            content=f"<!DOCTYPE html><html><body style='background:#0b0f19;color:white;text-align:center;padding:50px;font-family:sans-serif;'>"
                    f"<h1>404: {filename} Not Found</h1><p><a href='/' style='color:#38bdf8'>Return to Home</a></p></body></html>",
            status_code=404
        )
    return FileResponse(file_path)


# --- WEBSOCKET CONNECTION MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send to a websocket: {e}")
                disconnected.append(connection)
        for dead_conn in disconnected:
            self.disconnect(dead_conn)


manager = ConnectionManager()


# --- HTML PAGE ROUTES ---
@app.get("/")
async def serve_index():
    return render_html("index.html")

@app.get("/dashboard")
async def serve_dashboard():
    return render_html("dashboard.html")

@app.get("/profile")
async def serve_profile():
    return render_html("profile.html")

@app.get("/registration")
@app.get("/register")
async def serve_registration():
    return render_html("registration.html")


# --- PYDANTIC SCHEMAS ---
class ProfileSchema(BaseModel):
    device_id: str
    passcode: str
    name: Optional[str] = None
    full_name: Optional[str] = None
    age: Optional[int] = None
    blood_group: Optional[str] = None
    emergency_contact: Optional[str] = None
    govt_id_type: Optional[str] = None
    govt_id_number: Optional[str] = None
    medical_conditions: Optional[str] = None

class LookupSchema(BaseModel):
    device_id: str
    passcode: str

class AlertSchema(BaseModel):
    device_id: Optional[str] = "ESP32_NODE"
    trigger_type: Optional[str] = "EMERGENCY"
    status: Optional[str] = None
    latitude: Optional[float] = 19.0760
    longitude: Optional[float] = 72.8777
    speed: Optional[float] = 0.0
    battery: Optional[int] = 100
    message: Optional[str] = None


# --- HELPER TO ENRICH ALERT DATA WITH PROFILE ---
def build_enriched_alert(alert_obj: Alert, db: Session) -> dict:
    profile = db.query(Profile).filter(Profile.device_id == alert_obj.device_id).first()
    return {
        "id": alert_obj.id,
        "device_id": alert_obj.device_id,
        "trigger_type": alert_obj.trigger_type or "EMERGENCY",
        "latitude": alert_obj.latitude,
        "longitude": alert_obj.longitude,
        "speed": alert_obj.speed,
        "battery": alert_obj.battery,
        "message": alert_obj.message,
        "timestamp": alert_obj.timestamp.strftime("%Y-%m-%d %H:%M:%S") if alert_obj.timestamp else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "name": profile.name if profile and profile.name else "Unregistered Node",
        "age": profile.age if profile else None,
        "blood_group": profile.blood_group if profile and profile.blood_group else "N/A",
        "emergency_contact": profile.emergency_contact if profile and profile.emergency_contact else "N/A",
        "govt_id_type": profile.govt_id_type if profile else "",
        "govt_id_number": profile.govt_id_number if profile else "",
        "medical_conditions": profile.medical_conditions if profile and profile.medical_conditions else "None listed"
    }


# --- REST API ENDPOINTS ---

@app.post("/register")
@app.post("/api/register")
async def register_profile(data: ProfileSchema, db: Session = Depends(get_db)):
    profile_name = data.name or data.full_name or ""
    
    existing = db.query(Profile).filter(Profile.device_id == data.device_id).first()
    if existing:
        # Update existing profile
        existing.passcode = data.passcode
        existing.name = profile_name
        existing.age = data.age
        existing.blood_group = data.blood_group
        existing.emergency_contact = data.emergency_contact
        existing.govt_id_type = data.govt_id_type
        existing.govt_id_number = data.govt_id_number
        existing.medical_conditions = data.medical_conditions or "None listed"
        existing.updated_at = datetime.utcnow()
    else:
        # Create new profile
        new_profile = Profile(
            device_id=data.device_id,
            passcode=data.passcode,
            name=profile_name,
            age=data.age,
            blood_group=data.blood_group,
            emergency_contact=data.emergency_contact,
            govt_id_type=data.govt_id_type,
            govt_id_number=data.govt_id_number,
            medical_conditions=data.medical_conditions or "None listed"
        )
        db.add(new_profile)

    db.commit()
    return {
        "status": "success",
        "message": "Hardware profile saved successfully!",
        "device_id": data.device_id
    }


@app.post("/api/lookup")
@app.post("/lookup")
@app.post("/login")
@app.post("/api/login")
@app.post("/auth")
@app.post("/api/auth")
@app.post("/authenticate")
@app.post("/api/authenticate")
async def lookup_profile(data: LookupSchema, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.device_id == data.device_id).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device ID '{data.device_id}' is not registered yet."
        )
    
    if profile.passcode != data.passcode:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid passcode entered for this Device ID."
        )
        
    return profile.to_dict()


@app.get("/api/profiles")
async def list_profiles(db: Session = Depends(get_db)):
    profiles = db.query(Profile).all()
    sanitized = []
    for p in profiles:
        d = p.to_dict()
        d.pop("passcode", None)
        sanitized.append(d)
    return {"profiles": sanitized, "count": len(sanitized)}


@app.get("/api/profile/{device_id}")
async def get_single_profile(device_id: str, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.device_id == device_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Device not found")
    d = profile.to_dict()
    d.pop("passcode", None)
    return d


# --- ALERT INGESTION & BROADCAST ENDPOINTS ---

@app.post("/api/alerts")
@app.post("/api/alert")
@app.post("/alert")
@app.post("/api/trigger")
async def receive_alert(data: AlertSchema, db: Session = Depends(get_db)):
    """
    Receives alerts from hardware nodes, IoT devices, or simulation scripts,
    saves the alert in DB, enriches it with patient profile data, and broadcasts
    it to all active responders connected via WebSockets.
    """
    trigger_type = data.trigger_type or data.status or "EMERGENCY"
    
    alert = Alert(
        device_id=data.device_id,
        trigger_type=trigger_type,
        latitude=data.latitude,
        longitude=data.longitude,
        speed=data.speed,
        battery=data.battery,
        message=data.message,
        timestamp=datetime.utcnow()
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Enrich with profile details and broadcast
    enriched = build_enriched_alert(alert, db)
    await manager.broadcast(json.dumps(enriched))
    logger.info(f"Broadcasted alert {alert.id} from {alert.device_id}: {trigger_type}")

    return {
        "status": "success",
        "message": "Emergency alert received and dispatched to responders.",
        "alert": enriched
    }


@app.get("/api/alerts")
async def get_recent_alerts(limit: int = 50, db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.id.desc()).limit(limit).all()
    results = [build_enriched_alert(a, db) for a in alerts]
    return {"alerts": results, "count": len(results)}


@app.post("/api/test-alert")
async def trigger_test_alert(db: Session = Depends(get_db)):
    """Convenience endpoint to simulate a test emergency alert."""
    test_device_id = "001"
    
    # Ensure a sample profile exists for device 001 if empty
    sample = db.query(Profile).filter(Profile.device_id == test_device_id).first()
    if not sample:
        sample = Profile(
            device_id=test_device_id,
            passcode="1234",
            name="Aarav Sharma",
            age=34,
            blood_group="O+",
            emergency_contact="+91 98765 43210",
            govt_id_type="Aadhaar",
            govt_id_number="XXXX-XXXX-4521",
            medical_conditions="Penicillin Allergy, Asthmatic"
        )
        db.add(sample)
        db.commit()

    test_alert = Alert(
        device_id=test_device_id,
        trigger_type="FALL_DETECTED",
        latitude=19.0760 + (0.005 * (datetime.utcnow().second % 5 - 2)),
        longitude=72.8777 + (0.005 * (datetime.utcnow().second % 4 - 2)),
        speed=0.0,
        battery=78,
        message="Simulated rapid deceleration / fall detected by hardware accelerometer.",
        timestamp=datetime.utcnow()
    )
    db.add(test_alert)
    db.commit()
    db.refresh(test_alert)

    enriched = build_enriched_alert(test_alert, db)
    await manager.broadcast(json.dumps(enriched))
    return {
        "status": "success",
        "message": "Simulated test alert triggered successfully!",
        "alert": enriched
    }


# --- WEBSOCKET ENDPOINT FOR LIVE RESPONDER STREAM ---
@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(websocket)
    try:
        while True:
            # Responders receive broadcasts. If hardware nodes send over WS:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                device_id = payload.get("device_id", "UNKNOWN_WS_NODE")
                trigger_type = payload.get("trigger_type") or payload.get("status") or "EMERGENCY"
                
                alert = Alert(
                    device_id=device_id,
                    trigger_type=trigger_type,
                    latitude=payload.get("latitude", 19.0760),
                    longitude=payload.get("longitude", 72.8777),
                    speed=payload.get("speed"),
                    battery=payload.get("battery"),
                    message=payload.get("message"),
                    timestamp=datetime.utcnow()
                )
                db.add(alert)
                db.commit()
                db.refresh(alert)
                
                enriched = build_enriched_alert(alert, db)
                await manager.broadcast(json.dumps(enriched))
            except json.JSONDecodeError:
                logger.warning(f"Non-JSON message received on WS: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)