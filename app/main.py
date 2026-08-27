import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI(title="RescueLink")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def render_html(filename: str):
    file_path = os.path.join(STATIC_DIR, filename)
    if not os.path.exists(file_path):
        return HTMLResponse(content=f"<h1>404: {filename} Not Found</h1>", status_code=404)
    return FileResponse(file_path)

@app.get("/")
async def serve_index():
    return render_html("index.html")

@app.get("/dashboard")
async def serve_dashboard():
    return render_html("dashboard.html")

@app.get("/profile")
async def serve_profile():
    return render_html("profile.html")

# Serves both /registration and /register to stop 404 errors
@app.get("/registration")
@app.get("/register")
async def serve_registration():
    return render_html("registration.html")