import os
from fastapi import FastAPI
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


# --- DATA / API POST ENDPOINTS ---
class ProfileSchema(BaseModel):
    device_id: Optional[str] = None
    passcode: Optional[str] = None
    full_name: Optional[str] = None
    age: Optional[int] = None
    blood_group: Optional[str] = None
    emergency_contact: Optional[str] = None
    medical_conditions: Optional[str] = None

# In-memory storage placeholder (Replace with DB model later)
profiles_db = {}

@app.post("/register")
@app.post("/api/register")
async def register_profile(data: ProfileSchema):
    profiles_db[data.device_id] = data
    return {"status": "success", "message": "Profile registered successfully!"}

@app.post("/login")
@app.post("/api/login")
async def login_profile(data: ProfileSchema):
    return {"status": "success", "message": "Authenticated successfully!"}