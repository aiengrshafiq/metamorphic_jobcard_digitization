# app/api/endpoints/material_receipts.py
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import uuid

from app.api import deps
from app import models
from app.core.config import settings
from azure.storage.blob import BlobServiceClient
from app.utils import generate_sas_url

router = APIRouter()

@router.get("/pending-mrs/{project_id}", tags=["Material Receipts"])
def get_pending_mrs_for_project(project_id: int, db: Session = Depends(deps.get_db)):
    """Fetches pending Material Requisitions for a given project."""
    mrs = db.query(models.MaterialRequisition).filter(
        models.MaterialRequisition.project_id == project_id,
        models.MaterialRequisition.status.in_(['Pending', 'Partial Delivered'])
    ).all()
    return mrs

@router.get("/mr-details/{req_id}", tags=["Material Receipts"])
def get_mr_details(req_id: int, db: Session = Depends(deps.get_db)):
    """Fetches specific details for a single Material Requisition."""
    req = db.query(models.MaterialRequisition).options(
        # CORRECTED: Each joinedload is a separate argument to .options()
        joinedload(models.MaterialRequisition.supplier),
        joinedload(models.MaterialRequisition.items).joinedload(models.RequisitionItem.material)
    ).filter(models.MaterialRequisition.id == req_id).first()

    if not req:
        raise HTTPException(status_code=404, detail="Requisition not found")
        
    return {
        "material_type": req.material_type,
        "supplier": req.supplier.name if req.supplier else "N/A",
        "lpo_number": req.lpo_number or "N/A",
        "items": [
            {
                "name": item.material.name,
                "quantity": item.quantity,
                "unit": item.material.unit
            }
            for item in req.items
        ]
    }

@router.post("/upload-image", response_class=JSONResponse, tags=["Material Receipts"])
async def upload_receipt_image(file: UploadFile = File(...), db: Session = Depends(deps.get_db)):
    """Uploads an image to Azure Blob and creates a temporary record."""
    blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
    container_name = "material-receipts"
    try:
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")

    file_contents = await file.read()
    blob_name = f"{uuid.uuid4()}-{file.filename}"
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    blob_client.upload_blob(file_contents, overwrite=True)

    new_image = models.MaterialReceiptImage(blob_url=blob_client.url, file_name=file.filename)
    db.add(new_image)
    db.commit()
    db.refresh(new_image)
    return {
    "image_id": new_image.id,
    "blob_url": generate_sas_url(new_image.blob_url)
    }

@router.post("/", response_class=JSONResponse, tags=["Material Receipts"])
async def create_material_receipt(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    requisition_id: int = Form(...),
    delivery_status: str = Form(...),
    notes: Optional[str] = Form(None),
    image_ids: Optional[str] = Form(None),
    acknowledged: bool = Form(...)
):
    """Creates the final Material Receipt record and links the images."""
    # 1. Create the receipt
    new_receipt = models.MaterialReceipt(
        requisition_id=requisition_id,
        delivery_status=delivery_status,
        notes=notes,
        acknowledged_by_receiver=acknowledged,
        received_by_id=current_user.id
    )
    db.add(new_receipt)
    db.flush() # Flush to get the new_receipt.id

    # 2. Update the original Material Requisition's status
    requisition = db.query(models.MaterialRequisition).filter(models.MaterialRequisition.id == requisition_id).first()
    if requisition:
        requisition.status = delivery_status
    
    # 3. Link the uploaded images
    if image_ids:
        image_id_list = [int(id_str) for id_str in image_ids.split(',') if id_str.isdigit()]
        db.query(models.MaterialReceiptImage).filter(
            models.MaterialReceiptImage.id.in_(image_id_list)
        ).update({"receipt_id": new_receipt.id}, synchronize_session=False)

    db.commit()
    return JSONResponse(status_code=200, content={"message": "Material receipt recorded successfully!"})