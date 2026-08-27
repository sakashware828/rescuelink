import os
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="RescueLink API")

# Mount static files directory if you have local CSS/JS/Image assets
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Data Models ---

class LookupRequest(BaseModel):
    device_id: str
    passcode: str

class ProfileRegistration(BaseModel):
    device_id: str
    passcode: str
    name: str
    age: int
    blood_group: str
    emergency_contact: str
    govt_id_type: Optional[str] = "Aadhaar"
    govt_id_number: Optional[str] = ""
    medical_conditions: Optional[str] = "None listed"


# --- HTML Page Routes ---

@app.get("/", response_class=HTMLResponse)
@app.get("/register", response_class=HTMLResponse)
@app.get("/profile", response_class=HTMLResponse)
async def serve_profile_page():
    """Serves the main profile registration/linker UI."""
    file_path = os.path.join(os.path.dirname(__file__), "profile.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="profile.html file not found on server.")
    return FileResponse(file_path)

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard_page():
    """Serves the responder operations dashboard UI."""
    file_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="dashboard.html file not found on server.")
    return FileResponse(file_path)


# --- REST API Endpoints ---

# In-memory mock storage (replace with database query logic if using SQLite/PostgreSQL)
profiles_db = {}

@app.post("/api/lookup")
async def lookup_profile(payload: LookupRequest):
    """Authenticates a device ID and fetches registered metadata."""
    device = profiles_db.get(payload.device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Device ID not found"
        )
    
    if device.get("passcode") != payload.passcode:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid passcode for this device"
        )
        
    return device

@app.post("/api/register")
async def register_profile(payload: ProfileRegistration):
    """Registers or updates a hardware node profile."""
    profiles_db[payload.device_id] = payload.dict()
    return {"message": "Hardware Node Profile Saved!", "device_id": payload.device_id}


if __name__ == "__main__":
    import uvicorn
    # Runs server locally on port 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)