from dotenv import load_dotenv
load_dotenv()  # Must load before importing routers

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import uvicorn
import logging

from app.routers import upload, scripts, voiceover, video, projects, transcripts, avatar, zoom

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="Trupeer Clone API",
    description="Backend API for AI-powered video creation platform",
    version="1.0.0"
)

# CORS Configuration
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(scripts.router, prefix="/api/scripts", tags=["scripts"])
app.include_router(voiceover.router, prefix="/api/voiceover", tags=["voiceover"])
app.include_router(video.router, prefix="/api/video", tags=["video"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(transcripts.router, prefix="/api/transcripts", tags=["transcripts"])
app.include_router(avatar.router, prefix="/api/avatar", tags=["avatar"])
app.include_router(zoom.router, prefix="/api/zoom", tags=["zoom"])


@app.get("/")
async def root():
    return {"message": "Trupeer Clone API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8000))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)

