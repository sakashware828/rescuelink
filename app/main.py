from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db

# ----------------------------------------------------
# 1. DATABASE MODELS
# ----------------------------------------------------
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String, default="Active")
    timestamp = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)

# ----------------------------------------------------
# 2. PYDANTIC SCHEMAS
# ----------------------------------------------------
class AlertCreate(BaseModel):
    device_id: str
    latitude: float
    longitude: float

class AlertResponse(BaseModel):
    id: int
    device_id: str
    latitude: float
    longitude: float
    status: str
    timestamp: datetime

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]

    class Config:
        from_attributes = True

# ----------------------------------------------------
# 3. FASTAPI APP INITIALIZATION
# ----------------------------------------------------
app = FastAPI(title="RescueLink API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
# 4. API ENDPOINTS
# ----------------------------------------------------
@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    return {"status": "ok", "database": "connected"}

# --- ALERTS ---
@app.post("/api/alerts", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
def create_alert(alert: AlertCreate, db: Session = Depends(get_db)):
    new_alert = Alert(
        device_id=alert.device_id,
        latitude=alert.latitude,
        longitude=alert.longitude,
        status="Active"
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    return new_alert

@app.get("/api/alerts", response_model=List[AlertResponse])
def get_alerts(db: Session = Depends(get_db)):
    return db.query(Alert).order_by(Alert.timestamp.desc()).all()

# --- USERS ---
@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(name=user.name, email=user.email, phone=user.phone)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/api/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# ----------------------------------------------------
# 5. STATIC FILES MOUNT (Keep at bottom)
# ----------------------------------------------------
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")