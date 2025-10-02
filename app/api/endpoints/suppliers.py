# app/api/endpoints/suppliers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.api import deps
from app import models

router = APIRouter()

class SupplierCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

@router.post("/", tags=["Suppliers"])
def create_supplier(
    supplier_data: SupplierCreate,
    db: Session = Depends(deps.get_db)
):
    """Creates a new supplier in the database."""
    # Check for duplicates (case-insensitive)
    existing_supplier = db.query(models.Supplier).filter(
        func.lower(models.Supplier.name) == func.lower(supplier_data.name.strip())
    ).first()
    
    if existing_supplier:
        raise HTTPException(
            status_code=400, 
            detail=f"A supplier with the name '{supplier_data.name}' already exists."
        )

    new_supplier = models.Supplier(
        name=supplier_data.name.strip(),
        email=supplier_data.email,
        phone=supplier_data.phone
    )
    db.add(new_supplier)
    db.commit()
    db.refresh(new_supplier)
    
    # Return the newly created supplier object so the frontend can use it
    return new_supplier