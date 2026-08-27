import os
import sqlite3
import json
from fastapi import FastAPI, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="RescueLink")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(BASE_DIR, "rescuelink.db")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- DATABASE INITIALIZATION ---
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                device_id TEXT PRIMARY KEY,
                passcode TEXT NOT NULL,
                name TEXT,
                age INTEGER,
                blood_group TEXT,
                emergency_contact TEXT,
                govt_id_type TEXT,
                govt_id_number TEXT,
                medical_conditions TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                trigger_type TEXT,
                latitude REAL,
                longitude REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

init_db()

def render_html(filename: str):
    file_path = os.path.join(STATIC_DIR, filename)
    if not os.path.exists(file_path):
        return HTMLResponse(content=f"<h1>404: {filename} Not Found</h1>", status_code=404)
    return FileResponse(file_path)

# --- WEBSOCKET CONNECTION MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- HTML PAGE ROUTES ---
@app.get("/")
@app.get("/dashboard")
async def serve_dashboard():
    return render_html("dashboard.html")

@app.get("/registration")
@app.get("/register")
async def serve_registration():
    return render_html("registration.html")

@app.get("/profile")
async def serve_profile():
    return render_html("profile.html")


# --- DATA & API SCHEMAS ---
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


# --- REST API ENDPOINTS ---
@app.post("/register")
@app.post("/api/register")
async def register_profile(data: ProfileSchema):
    profile_name = data.name or data.full_name or ""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO profiles 
            (device_id, passcode, name, age, blood_group, emergency_contact, govt_id_type, govt_id_number, medical_conditions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.device_id, 
            data.passcode, 
            profile_name, 
            data.age,
            data.blood_group, 
            data.emergency_contact, 
            data.govt_id_type,
            data.govt_id_number, 
            data.medical_conditions or "None listed"
        ))
        conn.commit()
    return {"status": "success", "message": "Hardware Profile saved successfully!"}


@app.post("/api/lookup")
@app.post("/login")
@app.post("/api/login")
async def lookup_profile(data: LookupSchema):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profiles WHERE device_id = ?", (data.device_id,))
        row = cursor.fetchone()
        
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Device ID not registered yet."
        )
    
    device = dict(row)
    if device["passcode"] != data.passcode:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid Passcode."
        )
        
    return device


# --- WEBSOCKET ENDPOINT (REAL-TIME HARDWARE TRANSMISSIONS) ---
@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            # Save telemetry to DB
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO alerts (device_id, trigger_type, latitude, longitude)
                    VALUES (?, ?, ?, ?)
                ''', (
                    payload.get("device_id"),
                    payload.get("trigger_type", "SOS"),
                    payload.get("latitude", 0.0),
                    payload.get("longitude", 0.0)
                ))
                conn.commit()
            
            # Broadcast live alert to connected Web Dashboards
            await manager.broadcast(json.dumps(payload))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)