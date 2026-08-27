import os
import re
from datetime import datetime
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Form, HTTPException, status, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# -------------------------------------------------------------------
# Database Setup
# -------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./rescuelink.db")

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Profile(Base):
    __tablename__ = "profiles"
    device_id = Column(String, primary_key=True)
    passcode = Column(String, nullable=False)  # Hardware PIN / Password to protect profile
    name = Column(String)
    age = Column(Integer)
    blood_group = Column(String)
    medical_conditions = Column(String)
    emergency_contact = Column(String)
    govt_id_type = Column(String)
    govt_id_number = Column(String)
    is_verified = Column(Boolean, default=False)

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("profiles.device_id"))
    trigger_type = Column(String)
    latitude = Column(String)
    longitude = Column(String)
    status = Column(String, default="new")
    received_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def validate_govt_id(id_type: str, id_number: str) -> bool:
    clean_id = id_number.replace(" ", "").strip()
    if id_type == "Aadhaar":
        return bool(re.match(r"^\d{12}$", clean_id))
    elif id_type == "PAN":
        return bool(re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", clean_id.upper()))
    elif id_type == "Passport":
        return bool(re.match(r"^[A-Z1-9][0-9]{7}$", clean_id.upper()))
    elif id_type == "Driver License":
        return len(clean_id) >= 8
    return len(clean_id) >= 5

# -------------------------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------------------------
class ProfileFetchSchema(BaseModel):
    passcode: str

class ProfileUpdateSchema(BaseModel):
    passcode: str
    name: str
    age: int
    blood_group: str
    emergency_contact: str
    medical_conditions: str = ""
    govt_id_type: str
    govt_id_number: str

# -------------------------------------------------------------------
# WebSocket Connection Manager
# -------------------------------------------------------------------
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
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# -------------------------------------------------------------------
# FastAPI App & Page Routes
# -------------------------------------------------------------------
app = FastAPI(title="RescueLink")

os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    with open("app/static/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/registration", response_class=HTMLResponse)
async def serve_registration():
    with open("app/static/registration.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/profile", response_class=HTMLResponse)
async def serve_profile():
    with open("app/static/profile.html", "r", encoding="utf-8") as f:
        return f.read()

# -------------------------------------------------------------------
# Authenticated API Endpoints
# -------------------------------------------------------------------
@app.post("/api/profile/{device_id}")
async def get_user_profile(device_id: str, payload: ProfileFetchSchema, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.device_id == device_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found for this Device ID.")
    
    # Authenticate Passcode
    if profile.passcode != payload.passcode:
        raise HTTPException(status_code=401, detail="Access Denied: Invalid Passcode.")
    
    raw_id = profile.govt_id_number or ""
    masked_id = "XXXX-XXXX-" + raw_id[-4:] if len(raw_id) >= 4 else "VERIFIED"

    return {
        "device_id": profile.device_id,
        "name": profile.name,
        "age": profile.age,
        "blood_group": profile.blood_group,
        "medical_conditions": profile.medical_conditions,
        "emergency_contact": profile.emergency_contact,
        "govt_id_type": profile.govt_id_type or "Aadhaar",
        "govt_id_number": masked_id,
        "is_verified": profile.is_verified
    }

@app.put("/api/profile/{device_id}")
async def update_user_profile(device_id: str, payload: ProfileUpdateSchema, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.device_id == device_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    
    # Authenticate Passcode
    if profile.passcode != payload.passcode:
        raise HTTPException(status_code=401, detail="Authentication Failed: Invalid Device Passcode.")

    if not validate_govt_id(payload.govt_id_type, payload.govt_id_number):
        raise HTTPException(status_code=400, detail=f"Invalid {payload.govt_id_type} format. Verification failed.")

    profile.name = payload.name
    profile.age = payload.age
    profile.blood_group = payload.blood_group
    profile.emergency_contact = payload.emergency_contact
    profile.medical_conditions = payload.medical_conditions
    profile.govt_id_type = payload.govt_id_type
    profile.govt_id_number = payload.govt_id_number
    profile.is_verified = True
    
    db.commit()
    return JSONResponse(content={"status": "success", "message": "Profile updated & identity verified."})

@app.post("/api/register")
async def register_node(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    
    if "application/json" in content_type:
        data = await request.json()
        device_id = data.get("device_id")
        passcode = data.get("passcode")
        name = data.get("name") or data.get("victim_name")
        age = int(data.get("age", 0))
        blood_group = data.get("blood_group")
        medical_conditions = data.get("medical_conditions") or data.get("critical_allergies")
        emergency_contact = data.get("emergency_contact")
        govt_id_type = data.get("govt_id_type", "Aadhaar")
        govt_id_number = data.get("govt_id_number", "")
    else:
        form = await request.form()
        device_id = form.get("device_id")
        passcode = form.get("passcode")
        name = form.get("name") or form.get("victim_name")
        age = int(form.get("age", 0)) if form.get("age") else 0
        blood_group = form.get("blood_group")
        medical_conditions = form.get("medical_conditions") or form.get("critical_allergies")
        emergency_contact = form.get("emergency_contact")
        govt_id_type = form.get("govt_id_type", "Aadhaar")
        govt_id_number = form.get("govt_id_number", "")

    if not device_id or not passcode or not name or not govt_id_number:
        raise HTTPException(status_code=400, detail="Missing required fields: device_id, passcode, name, and govt_id_number.")

    if not validate_govt_id(govt_id_type, govt_id_number):
        raise HTTPException(status_code=400, detail=f"Invalid {govt_id_type} format. Verification failed.")

    profile = db.query(Profile).filter(Profile.device_id == device_id).first()
    if profile:
        if profile.passcode != passcode:
            raise HTTPException(status_code=401, detail="Cannot overwrite existing node: Invalid Passcode.")
        profile.name = name
        profile.age = age
        profile.blood_group = blood_group
        profile.medical_conditions = medical_conditions
        profile.emergency_contact = emergency_contact
        profile.govt_id_type = govt_id_type
        profile.govt_id_number = govt_id_number
        profile.is_verified = True
    else:
        profile = Profile(
            device_id=device_id,
            passcode=passcode,
            name=name,
            age=age,
            blood_group=blood_group,
            medical_conditions=medical_conditions,
            emergency_contact=emergency_contact,
            govt_id_type=govt_id_type,
            govt_id_number=govt_id_number,
            is_verified=True
        )
        db.add(profile)

    db.commit()
    return JSONResponse(content={"status": "success", "device_id": device_id, "is_verified": True})

@app.get("/api/alerts")
async def get_alerts(db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.received_at.desc()).all()
    results = []
    for alert in alerts:
        profile = db.query(Profile).filter(Profile.device_id == alert.device_id).first()
        results.append({
            "id": alert.id,
            "device_id": alert.device_id,
            "trigger_type": alert.trigger_type,
            "latitude": alert.latitude,
            "longitude": alert.longitude,
            "status": alert.status,
            "received_at": alert.received_at.isoformat() if alert.received_at else None,
            "name": profile.name if profile else "Unknown User",
            "blood_group": profile.blood_group if profile else "N/A",
            "medical_conditions": profile.medical_conditions if profile else "None",
            "emergency_contact": profile.emergency_contact if profile else "N/A",
            "is_verified": profile.is_verified if profile else False
        })
    return results

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)