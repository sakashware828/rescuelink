from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os

from app.database import engine, Base, get_db, Alert

# Create database tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RescueLink API")

# Setup CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files folder
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configure Jinja2 templates (pointing to static directory where your HTML files reside)
templates = Jinja2Templates(directory="app/static")

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard")
def read_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/registration")
def read_registration(request: Request):
    return templates.TemplateResponse("registration.html", {"request": request})

@app.get("/profile")
def read_profile(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})

@app.get("/api/alerts")
def fetch_alerts(db: Session = Depends(get_db)):
    alerts = db.query(Alert).all()
    return {"status": "success", "data": alerts}

@app.post("/api/alerts")
def create_alert(payload: dict, db: Session = Depends(get_db)):
    new_alert = Alert(
        device_id=payload.get("device_id", "UNKNOWN"),
        latitude=payload.get("latitude", 0.0),
        longitude=payload.get("longitude", 0.0),
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    return {"status": "alert_created", "alert": new_alert}