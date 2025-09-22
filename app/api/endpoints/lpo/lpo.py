# app/api/endpoints/lpo/lpo.py
import json
from fastapi import APIRouter, Depends, Form, HTTPException, Body, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func
from typing import List, Optional
from datetime import date
import io
from weasyprint import HTML, CSS
from fastapi.templating import Jinja2Templates

from app.api import deps
from app import models

from pydantic import BaseModel



router = APIRouter()
# A local templates instance for PDF generation
pdf_templates = Jinja2Templates(directory="templates")

# --- Helper to get next LPO Number ---
def get_next_lpo_number(db: Session):
    last_lpo = db.query(models.LPO.lpo_number).order_by(models.LPO.id.desc()).first()
    if not last_lpo:
        return "LPO-0001"
    last_num = int(last_lpo[0].split('-')[1])
    return f"LPO-{last_num + 1:04d}"

# --- API Endpoints ---
@router.get("/", tags=["LPO"])
def get_lpos(db: Session = Depends(deps.get_db)):
    lpos = db.query(models.LPO).options(
        joinedload(models.LPO.supplier),
        joinedload(models.LPO.project),
        joinedload(models.LPO.created_by)
    ).order_by(models.LPO.lpo_date.desc()).all()
    return lpos

@router.get("/{lpo_id}", tags=["LPO"])
def get_lpo_details(lpo_id: int, db: Session = Depends(deps.get_db)):
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

# Define a Pydantic model for the line items for easier validation
class LPOItemData(BaseModel):
    material_id: int
    description: Optional[str] = None
    quantity: float
    rate: float
    tax_rate: float

# The main endpoint to create an LPO
@router.post("/", tags=["LPO"])
def create_lpo(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    supplier_id: int = Form(...),
    lpo_date: date = Form(...),
    project_id: int = Form(...),
    message_to_supplier: Optional[str] = Form(None),
    memo: Optional[str] = Form(None),
    # The items will be sent as a JSON-encoded string
    items_json: str = Form(...)
):
    try:
        # Parse the JSON string of items into a list of Pydantic models
        items_data = [LPOItemData.parse_obj(item) for item in json.loads(items_json)]

        new_lpo = models.LPO(
            lpo_number=get_next_lpo_number(db),
            supplier_id=supplier_id,
            lpo_date=lpo_date,
            project_id=project_id,
            message_to_supplier=message_to_supplier,
            memo=memo,
            created_by_id=current_user.id,
            status="Pending" # Default status
        )

        # Create LPOItem objects from the parsed data
        for item_data in items_data:
            lpo_item = models.LPOItem(
                material_id=item_data.material_id,
                description=item_data.description,
                quantity=item_data.quantity,
                rate=item_data.rate,
                tax_rate=item_data.tax_rate
            )
            new_lpo.items.append(lpo_item)
            
        db.add(new_lpo)
        db.commit()
        db.refresh(new_lpo)
        return new_lpo
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")