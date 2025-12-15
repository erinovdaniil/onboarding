from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json

from app.database import get_project, update_project

router = APIRouter()


class ZoomConfig(BaseModel):
    enabled: bool
    startTime: float
    endTime: float
    zoomLevel: float
    centerX: Optional[float] = None
    centerY: Optional[float] = None


class ZoomConfigRequest(BaseModel):
    zoomConfig: Optional[ZoomConfig] = None


@router.get("/{project_id}")
async def get_zoom_config(project_id: str):
    """
    Get zoom configuration for a project.
    """
    try:
        project = await get_project(project_id)
        if not project:
            return {"zoomConfig": None}

        zoom_config = project.get("zoom_config")
        if zoom_config:
            if isinstance(zoom_config, str):
                zoom_config = json.loads(zoom_config)
            return {"zoomConfig": zoom_config}

        return {"zoomConfig": None}
    except Exception as e:
        print(f"Error getting zoom config: {e}")
        return {"zoomConfig": None}


@router.post("/{project_id}")
async def save_zoom_config(project_id: str, request: ZoomConfigRequest):
    """
    Save zoom configuration for a project.
    """
    try:
        # Convert to JSON string for storage
        zoom_config_json = None
        if request.zoomConfig:
            zoom_config_json = json.dumps(request.zoomConfig.model_dump())

        # Update project with zoom config
        result = await update_project(project_id, {"zoom_config": zoom_config_json})

        if result:
            return {"success": True, "zoomConfig": request.zoomConfig}
        else:
            raise HTTPException(status_code=500, detail="Failed to save zoom config")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving zoom config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save zoom config: {str(e)}")
