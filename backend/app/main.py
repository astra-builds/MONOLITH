from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import db
from .routers import projects, tasks, commitments, schedule, settings, ai, demo

app = FastAPI(title="MONOLITH")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    db.init_db()

app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(commitments.router)
app.include_router(schedule.router)
app.include_router(settings.router)
app.include_router(ai.router)
app.include_router(demo.router)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/export")
def export_data():
    return db.export_all()
