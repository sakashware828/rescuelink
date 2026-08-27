import os
from datetime import datetime
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Form, HTTPException, status, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, String, Integer, DateTime, ForeignKey
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
    name = Column(String)
    age = Column(Integer)
    blood_group = Column(String)
    medical_conditions = Column(String)
    emergency_contact = Column(String)

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
# API Endpoints
# -------------------------------------------------------------------
@app.post("/api/login")
async def responder_login(username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "rescue123":
        return JSONResponse(content={"status": "success", "message": "Authenticated"})
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid responder credentials"
    )

@app.get("/api/profile/{device_id}")
async def get_user_profile(device_id: str, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.device_id == device_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found for this Device ID.")
    return {
        "device_id": profile.device_id,
        "name": profile.name,
        "age": profile.age,
        "blood_group": profile.blood_group,
        "medical_conditions": profile.medical_conditions,
        "emergency_contact": profile.emergency_contact
    }

@app.post("/api/register")
async def register_node(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    
    if "application/json" in content_type:
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name") or data.get("victim_name")
        age = int(data.get("age", 0))
        blood_group = data.get("blood_group")
        medical_conditions = data.get("medical_conditions") or data.get("critical_allergies")
        emergency_contact = data.get("emergency_contact")
    else:
        form = await request.form()
        device_id = form.get("device_id")
        name = form.get("name") or form.get("victim_name")
        age = int(form.get("age", 0)) if form.get("age") else 0
        blood_group = form.get("blood_group")
        medical_conditions = form.get("medical_conditions") or form.get("critical_allergies")
        emergency_contact = form.get("emergency_contact")

    if not device_id or not name:
        raise HTTPException(status_code=400, detail="Missing required fields: device_id and name.")

    profile = db.query(Profile).filter(Profile.device_id == device_id).first()
    if profile:
        profile.name = name
        profile.age = age
        profile.blood_group = blood_group
        profile.medical_conditions = medical_conditions
        profile.emergency_contact = emergency_contact
    else:
        profile = Profile(
            device_id=device_id,
            name=name,
            age=age,
            blood_group=blood_group,
            medical_conditions=medical_conditions,
            emergency_contact=emergency_contact
        )
        db.add(profile)

    db.commit()
    return JSONResponse(content={"status": "success", "device_id": device_id})

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
            "emergency_contact": profile.emergency_contact if profile else "N/A"
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