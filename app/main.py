from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db

BASE_DIR = Path(__file__).resolve().parent  # FIX: was missing, caused NameError on startup

# ----------------------------------------------------
# 1. DATABASE MODELS
# ----------------------------------------------------
class Profile(Base):
    __tablename__ = "profiles"
    device_id = Column(String, primary_key=True, index=True)
    passcode = Column(String, nullable=False)
    name = Column(String, nullable=False)
    age = Column(Integer)
    blood_group = Column(String)
    emergency_contact = Column(String)
    medical_conditions = Column(String, default="None listed")

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True)
    trigger_type = Column(String, default="manual")  # "manual" or "auto_fall"
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String, default="Active")
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ----------------------------------------------------
# 2. PYDANTIC SCHEMAS
# ----------------------------------------------------
class ProfileCreate(BaseModel):
    device_id: str
    passcode: str
    name: str
    age: int
    blood_group: str
    emergency_contact: str
    medical_conditions: Optional[str] = "None listed"

class LookupRequest(BaseModel):
    device_id: str
    passcode: str

class AlertCreate(BaseModel):
    device_id: str
    trigger_type: str = "manual"
    latitude: float
    longitude: float

class AlertResponse(BaseModel):
    id: int
    device_id: str
    trigger_type: str
    latitude: float
    longitude: float
    status: str
    timestamp: datetime

    class Config:
        from_attributes = True

# ----------------------------------------------------
# 3. WEBSOCKET CONNECTION MANAGER
# ----------------------------------------------------
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
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# ----------------------------------------------------
# 4. FASTAPI APP INITIALIZATION
# ----------------------------------------------------
app = FastAPI(title="RescueLink API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
# 5. API ENDPOINTS
# ----------------------------------------------------
@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    return {"status": "ok", "database": "connected"}

# --- PROFILE REGISTRATION / LOOKUP (fixes the missing endpoints) ---
@app.post("/api/register")
def register_profile(profile: ProfileCreate, db: Session = Depends(get_db)):
    existing = db.query(Profile).filter(Profile.device_id == profile.device_id).first()
    if existing:
        for key, value in profile.dict().items():
            setattr(existing, key, value)
    else:
        db.add(Profile(**profile.dict()))
    db.commit()
    return {"status": "saved", "device_id": profile.device_id}

@app.post("/api/lookup")
def lookup_profile(req: LookupRequest, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(
        Profile.device_id == req.device_id,
        Profile.passcode == req.passcode
    ).first()
    if not profile:
        raise HTTPException(status_code=401, detail="Invalid device ID or passcode")
    return {
        "device_id": profile.device_id, "name": profile.name, "age": profile.age,
        "blood_group": profile.blood_group, "emergency_contact": profile.emergency_contact,
        "medical_conditions": profile.medical_conditions,
    }

# --- ALERTS (now merges profile data and broadcasts over WebSocket) ---
@app.post("/api/alerts", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(alert: AlertCreate, db: Session = Depends(get_db)):
    new_alert = Alert(
        device_id=alert.device_id,
        trigger_type=alert.trigger_type,
        latitude=alert.latitude,
        longitude=alert.longitude,
        status="Active"
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)

    # Look up the profile so the dashboard gets full victim details, not just coordinates
    profile = db.query(Profile).filter(Profile.device_id == alert.device_id).first()

    await manager.broadcast({
        "device_id": new_alert.device_id,
        "trigger_type": new_alert.trigger_type,
        "latitude": new_alert.latitude,
        "longitude": new_alert.longitude,
        "name": profile.name if profile else "Unknown (unregistered device)",
        "age": profile.age if profile else "?",
        "blood_group": profile.blood_group if profile else "?",
        "emergency_contact": profile.emergency_contact if profile else "?",
        "medical_conditions": profile.medical_conditions if profile else "No profile linked",
    })

    return new_alert

@app.get("/api/alerts", response_model=List[AlertResponse])
def get_alerts(db: Session = Depends(get_db)):
    return db.query(Alert).order_by(Alert.timestamp.desc()).all()

# --- WEBSOCKET (this was completely missing before) ---
@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep connection alive; dashboard doesn't send anything
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ----------------------------------------------------
# 6. STATIC FILES MOUNT (Keep at bottom)
# ----------------------------------------------------
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")