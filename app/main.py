import os
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="RescueLink")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def render_html(filename: str):
    file_path = os.path.join(STATIC_DIR, filename)
    if not os.path.exists(file_path):
        return HTMLResponse(content=f"<h1>404: {filename} Not Found</h1>", status_code=404)
    return FileResponse(file_path)


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


# --- DATA / API SCHEMAS ---
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

# In-memory database storage
profiles_db = {}


# --- POST ENDPOINTS ---
@app.post("/register")
@app.post("/api/register")
async def register_profile(data: ProfileSchema):
    # Standardize name field
    profile_name = data.name or data.full_name or ""
    
    profiles_db[data.device_id] = {
        "device_id": data.device_id,
        "passcode": data.passcode,
        "name": profile_name,
        "age": data.age,
        "blood_group": data.blood_group,
        "emergency_contact": data.emergency_contact,
        "govt_id_type": data.govt_id_type,
        "govt_id_number": data.govt_id_number,
        "medical_conditions": data.medical_conditions or "None listed"
    }
    return {"status": "success", "message": "Hardware Profile registered successfully!"}


@app.post("/api/lookup")
@app.post("/login")
@app.post("/api/login")
@app.post("/auth")
@app.post("/api/auth")
@app.post("/authenticate")
@app.post("/api/authenticate")
async def lookup_profile(data: LookupSchema):
    device = profiles_db.get(data.device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Device ID not registered yet."
        )
        
    if device["passcode"] != data.passcode:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid Passcode."
        )
        
    return device