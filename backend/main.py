from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Import only essential routers
from backend.routes import auth, chat, ml 

app = FastAPI()

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(ml.router, prefix="/api")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

# Static files
app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")

# HTML routes
@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/admin-login")
def admin_login():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin-login.html"))

@app.get("/login")
def login():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

@app.get("/register")
def register():
    return FileResponse(os.path.join(FRONTEND_DIR, "register.html"))

@app.get("/admin")
def admin():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))

@app.get("/doctor")
def doctor():
    return FileResponse(os.path.join(FRONTEND_DIR, "doctor.html"))

@app.get("/researcher")
def researcher():
    return FileResponse(os.path.join(FRONTEND_DIR, "researcher.html"))

@app.get("/patient")
def patient():
    return FileResponse(os.path.join(FRONTEND_DIR, "patient.html"))



