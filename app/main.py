import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, shiii, couple

STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../static"))
try:
    os.makedirs(os.path.join(STATIC_DIR, "audio"), exist_ok=True)
except OSError:
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables on startup (convenient for local dev & serverless)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"[Notice] Database auto-migration deferred or skipped: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# Enable CORS for Android / Web testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for audio playback (if available)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(couple.router, prefix=settings.API_V1_STR)
app.include_router(shiii.router, prefix=settings.API_V1_STR)

@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "Shiii AI Emissary",
        "voice": settings.TTS_VOICE,
        "model": settings.GEMINI_MODEL
    }
