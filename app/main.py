from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db

BASE_DIR = Path(__file__).resolve().parent

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
    trigger_type = Column(String, default="manual")
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
# 5. HTML PAGE ROUTING (Fixes 404 Page Loading Issues)
# ----------------------------------------------------
# Adjust path lookup depending on whether files live in app/static or app/templates
def get_html_path(filename: str) -> Path:
    static_path = BASE_DIR / "static" / filename
    templates_path = BASE_DIR / "templates" / filename
    if static_path.exists():
        return static_path
    elif templates_path.exists():
        return templates_path
    return BASE_DIR / filename

@app.get("/")
def read_root():
    return FileResponse(get_html_path("registration.html"))

@app.get("/registration")
def read_registration():
    return FileResponse(get_html_path("registration.html"))

@app.get("/dashboard")
def read_dashboard():
    return FileResponse(get_html_path("dashboard.html"))

@app.get("/profile")
def read_profile():
    return FileResponse(get_html_path("profile.html"))

# ----------------------------------------------------
# 6. API ENDPOINTS
# ----------------------------------------------------
@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    return {"status": "ok", "database": "connected"}

@app.post("/api/register")
def register_profile(profile: ProfileCreate, db: Session = Depends(get_db)):
    existing = db.query(Profile).filter(Profile.device_id == profile.device_id).first()
    if existing:
        for key, value in profile.model_dump().items():
            setattr(existing, key, value)
    else:
        db.add(Profile(**profile.model_dump()))
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
        "device_id": profile.device_id,
        "name": profile.name,
        "age": profile.age,
        "blood_group": profile.blood_group,
        "emergency_contact": profile.emergency_contact,
        "medical_conditions": profile.medical_conditions,
    }

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

@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)