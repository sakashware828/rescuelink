import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.database import engine, Base

# Initialize Database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RescueLink API")

# Setup absolute pathing for static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Mount static folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# HTML Page Routes
@app.get("/")
async def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/dashboard")
async def read_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "dashboard.html"))

@app.get("/profile")
async def read_profile():
    return FileResponse(os.path.join(STATIC_DIR, "profile.html"))

@app.get("/registration")
async def read_registration():
    return FileResponse(os.path.join(STATIC_DIR, "registration.html"))

# Catch-all exception handler to convert 500 errors into readable JSON
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": f"Internal Server Error: {str(exc)}"}
    )