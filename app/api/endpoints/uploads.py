# app/api/endpoints/uploads.py
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from azure.storage.blob import BlobServiceClient
import uuid
from typing import List

from app.api import deps
from app import models
from app.core.config import settings
from app.services.video_processing import process_video_and_update_db

router = APIRouter()

@router.post("/api/images/upload", response_class=JSONResponse, tags=["Uploads"])
async def upload_images(
    files: List[UploadFile] = File(...),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        raise HTTPException(status_code=500, detail="Azure Storage not configured on the server.")

    blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
    container_name = "site-images"
    try:
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not access storage container: {e}")

    image_ids = []
    for file in files:
        try:
            file_contents = await file.read()
            safe_filename = "".join(c for c in file.filename if c.isalnum() or c in ('.', '_')).rstrip()
            blob_name = f"{uuid.uuid4()}-{safe_filename}"
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            blob_client.upload_blob(file_contents, overwrite=True)

            new_image = models.SiteImage(blob_url=blob_client.url, file_name=file.filename)
            db.add(new_image)
            db.commit()
            db.refresh(new_image)
            image_ids.append(new_image.id)
        except Exception as e:
            db.rollback()
            return JSONResponse(status_code=500, content={"message": f"Failed to upload {file.filename}: {e}"})
    return {"message": "Images uploaded successfully", "image_ids": image_ids}


@router.post("/api/videos/upload", response_class=JSONResponse, tags=["Uploads"])
async def upload_video(
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    video: UploadFile = File(...)
):
    if not settings.AZURE_STORAGE_CONNECTION_STRING or not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="Server is not configured for video processing.")

    file_contents = await video.read()
    new_video_record = models.ToolboxVideo()
    db.add(new_video_record)
    db.commit()
    db.refresh(new_video_record)

    background_tasks.add_task(
        process_video_and_update_db,
        new_video_record.id,
        file_contents,
        settings.AZURE_STORAGE_CONNECTION_STRING,
        settings.OPENAI_API_KEY
    )
    return {"message": "Video upload started. Processing in the background.", "video_id": new_video_record.id}