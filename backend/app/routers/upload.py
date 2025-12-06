from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import uuid
from pathlib import Path
from typing import Optional

router = APIRouter()

# Get upload directory from environment or use default
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../public/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/")
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video file and create a new project.
    """
    try:
        # Generate unique project ID
        project_id = str(uuid.uuid4())
        project_dir = UPLOAD_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        # Save the uploaded file
        file_path = project_dir / "original.webm"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Create project metadata
        project = {
            "id": project_id,
            "name": f"Project {project_id[:8]}",
            "videoUrl": f"/uploads/{project_id}/original.webm",
            "status": "uploaded",
            "createdAt": str(Path(file_path).stat().st_mtime),
        }

        return JSONResponse(content=project)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

