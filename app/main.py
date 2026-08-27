from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import sqlite3

app = FastAPI(title="RescueLink Emergency Network")

# Static files & Jinja2 Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/static")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

def init_db():
    conn = sqlite3.connect("rescuelink.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            device_id TEXT PRIMARY KEY,
            passcode TEXT NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            blood_group TEXT,
            emergency_contact TEXT,
            medical_conditions TEXT,
            govt_id_type TEXT,
            govt_id_number TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            trigger_type TEXT,
            latitude TEXT,
            longitude TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

class ProfileSchema(BaseModel):
    device_id: str
    passcode: str
    name: str
    age: int
    blood_group: str
    emergency_contact: str
    medical_conditions: Optional[str] = "None listed"
    govt_id_type: str
    govt_id_number: str

class AlertSchema(BaseModel):
    device_id: str
    trigger_type: str
    latitude: str
    longitude: str

class AuthSchema(BaseModel):
    device_id: str
    passcode: str

# --- Page Routes ---
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def responder_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/profile", response_class=HTMLResponse)
async def user_profile_linker(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})

# --- APIs ---
@app.post("/api/register")
async def register_profile(profile: ProfileSchema):
    conn = sqlite3.connect("rescuelink.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            passcode=excluded.passcode,
            name=excluded.name,
            age=excluded.age,
            blood_group=excluded.blood_group,
            emergency_contact=excluded.emergency_contact,
            medical_conditions=excluded.medical_conditions,
            govt_id_type=excluded.govt_id_type,
            govt_id_number=excluded.govt_id_number
    """, (
        profile.device_id, profile.passcode, profile.name, profile.age,
        profile.blood_group, profile.emergency_contact, profile.medical_conditions,
        profile.govt_id_type, profile.govt_id_number
    ))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Profile saved."}

@app.post("/api/lookup")
async def lookup_profile(auth: AuthSchema):
    conn = sqlite3.connect("rescuelink.db")
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, name, age, blood_group, emergency_contact, medical_conditions, govt_id_type, govt_id_number FROM profiles WHERE device_id = ? AND passcode = ?", (auth.device_id, auth.passcode))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid Device ID or Passcode.")
    return {
        "device_id": row[0], "name": row[1], "age": row[2], "blood_group": row[3],
        "emergency_contact": row[4], "medical_conditions": row[5],
        "govt_id_type": row[6], "govt_id_number": row[7]
    }

@app.post("/api/alerts")
async def receive_alert(alert: AlertSchema):
    conn = sqlite3.connect("rescuelink.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO alerts (device_id, trigger_type, latitude, longitude) VALUES (?, ?, ?, ?)",
                   (alert.device_id, alert.trigger_type, alert.latitude, alert.longitude))
    conn.commit()
    
    cursor.execute("SELECT name, age, blood_group, emergency_contact, medical_conditions FROM profiles WHERE device_id = ?", (alert.device_id,))
    profile = cursor.fetchone()
    conn.close()

    payload = {
        "device_id": alert.device_id,
        "trigger_type": alert.trigger_type,
        "latitude": alert.latitude,
        "longitude": alert.longitude,
        "name": profile[0] if profile else "UNREGISTERED DEVICE",
        "age": profile[1] if profile else "N/A",
        "blood_group": profile[2] if profile else "N/A",
        "emergency_contact": profile[3] if profile else "N/A",
        "medical_conditions": profile[4] if profile else "N/A"
    }

    await manager.broadcast(payload)
    return {"status": "broadcasted", "data": payload}

@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)