# app/api/endpoints/lpo/lpo.py
import json
import uuid
from fastapi import APIRouter, Depends, Form, HTTPException, Body, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func
from typing import List, Optional
from datetime import date
import io
from sqlalchemy import or_
from weasyprint import HTML, CSS
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.api import deps
from app import models
from app.core.config import settings
from azure.storage.blob import BlobServiceClient

router = APIRouter()
pdf_templates = Jinja2Templates(directory="templates")

def get_next_lpo_number(db: Session):
    last_lpo = db.query(models.LPO.lpo_number).order_by(models.LPO.id.desc()).first()
    if not last_lpo:
        return "LPO-0001"
    last_num = int(last_lpo[0].split('-')[1])
    return f"LPO-{last_num + 1:04d}"

class LPOItemData(BaseModel):
    material_id: int
    description: Optional[str] = ""
    quantity: float
    rate: float
    tax_rate: float

@router.post("/", tags=["LPO"])
def create_lpo(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    supplier_id: int = Form(...),
    lpo_date: date = Form(...),
    project_id: int = Form(...),
    message_to_supplier: Optional[str] = Form(None),
    memo: Optional[str] = Form(None),
    items_json: str = Form(...),
    subtotal: float = Form(...),
    tax_total: float = Form(...),
    grand_total: float = Form(...),
    attachment_ids: Optional[str] = Form(None)
):
    try:
        items_data = [LPOItemData.parse_obj(item) for item in json.loads(items_json)]

        new_lpo = models.LPO(
            lpo_number=get_next_lpo_number(db),
            supplier_id=supplier_id, lpo_date=lpo_date, project_id=project_id,
            message_to_supplier=message_to_supplier, memo=memo,
            created_by_id=current_user.id, status="Pending",
            subtotal=subtotal, tax_total=tax_total, grand_total=grand_total
        )

        for item_data in items_data:
            lpo_item = models.LPOItem(
                material_id=item_data.material_id, description=item_data.description,
                quantity=item_data.quantity, rate=item_data.rate, tax_rate=item_data.tax_rate
            )
            new_lpo.items.append(lpo_item)
            
        db.add(new_lpo)
        db.flush() # Flush to get the new_lpo.id

        if attachment_ids:
            id_list = [int(id_str) for id_str in attachment_ids.split(',') if id_str.isdigit()]
            db.query(models.LPOAttachment).filter(models.LPOAttachment.id.in_(id_list)).update(
                {"lpo_id": new_lpo.id}, synchronize_session=False
            )

        db.commit()
        db.refresh(new_lpo)
        return new_lpo
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@router.post("/attachments", response_class=JSONResponse, tags=["LPO"])
async def upload_lpo_attachment(file: UploadFile = File(...), db: Session = Depends(deps.get_db)):
    """Uploads an attachment to Azure Blob and creates a temporary record."""
    blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
    container_name = "lpo-attachments"
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

    new_attachment = models.LPOAttachment(blob_url=blob_client.url, file_name=file.filename)
    db.add(new_attachment)
    db.commit()
    db.refresh(new_attachment)
    return {"attachment_id": new_attachment.id}


@router.get("/", tags=["LPO"])
def get_lpos(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None
):
    """
    Fetches a paginated and searchable list of all LPOs.
    """
    query = db.query(models.LPO).options(
        joinedload(models.LPO.supplier),
        joinedload(models.LPO.project),
        joinedload(models.LPO.created_by)
    )

    if search:
        search_term = f"%{search}%"
        # Join with supplier and project to search their names
        query = query.join(models.Supplier).join(models.Project).filter(
            or_(
                models.LPO.lpo_number.ilike(search_term),
                models.Supplier.name.ilike(search_term),
                models.Project.name.ilike(search_term)
            )
        )

    total_count = query.count()
    lpos = query.order_by(models.LPO.id.desc()).offset(skip).limit(limit).all()

    return {"total_count": total_count, "lpos": lpos}

def _check_finance_role(current_user: models.User):
    """Helper to check if the current user has the Finance role."""
    user_roles = {role.name for role in current_user.roles}
    if "Finance" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized for this action.")

@router.post("/{lpo_id}/approve", tags=["LPO"])
def approve_lpo(
    lpo_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    _check_finance_role(current_user)
    lpo = db.query(models.LPO).filter(models.LPO.id == lpo_id).first()
    if not lpo:
        raise HTTPException(status_code=404, detail="LPO not found")
    lpo.status = "Approved"
    db.commit()
    return {"message": f"{lpo.lpo_number} has been approved."}

@router.post("/{lpo_id}/reject", tags=["LPO"])
def reject_lpo(
    lpo_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    _check_finance_role(current_user)
    lpo = db.query(models.LPO).filter(models.LPO.id == lpo_id).first()
    if not lpo:
        raise HTTPException(status_code=404, detail="LPO not found")
    lpo.status = "Rejected"
    db.commit()
    return {"message": f"{lpo.lpo_number} has been rejected."}

@router.get("/{lpo_id}/pdf", tags=["LPO"], response_class=StreamingResponse)
def generate_lpo_pdf(lpo_id: int, db: Session = Depends(deps.get_db)):
    """Generates and returns a PDF for a given LPO."""
    lpo = db.query(models.LPO).options(
        joinedload(models.LPO.supplier),
        joinedload(models.LPO.project),
        joinedload(models.LPO.created_by),
        selectinload(models.LPO.items).joinedload(models.LPOItem.material)
    ).filter(models.LPO.id == lpo_id).first()

    if not lpo:
        raise HTTPException(status_code=404, detail="LPO not found")

    # Render an HTML template with the LPO data
    # Note: We use a separate template designed specifically for the PDF layout
    html_string = pdf_templates.get_template("lpo/lpo_pdf.html").render({"lpo": lpo})

    # Use WeasyPrint to convert the HTML to a PDF in memory
    pdf_bytes = HTML(string=html_string).write_pdf()

    # Create headers to prompt a download
    headers = {
        'Content-Disposition': f'inline; filename="{lpo.lpo_number}.pdf"'
    }

    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/{lpo_id}", tags=["LPO"])
def get_lpo_details(lpo_id: int, db: Session = Depends(deps.get_db)):
    """Fetches all details for a single LPO."""
    lpo = db.query(models.LPO).options(
        joinedload(models.LPO.supplier),
        joinedload(models.LPO.project),
        joinedload(models.LPO.created_by),
        selectinload(models.LPO.items).joinedload(models.LPOItem.material),
        selectinload(models.LPO.attachments)
    ).filter(models.LPO.id == lpo_id).first()
    if not lpo:
        raise HTTPException(status_code=404, detail="LPO not found")
    return lpo