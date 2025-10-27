# app/api/endpoints/invoice/invoice.py
import json
import uuid
from fastapi import APIRouter, Depends, Form, HTTPException, Body, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func
from typing import List, Optional
from datetime import date, timedelta
from pydantic import BaseModel
from app.api import deps
from app import models, invoice_models
from app.core.config import settings
from azure.storage.blob.aio import BlobServiceClient # Use aio for async uploads
from sqlalchemy import or_
from app.utils import generate_sas_url, image_to_data_uri
from weasyprint import HTML, CSS
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
import io

pdf_templates = Jinja2Templates(directory="templates")

router = APIRouter()

def get_next_invoice_number(db: Session):
    last_invoice = db.query(invoice_models.Invoice.invoice_number).order_by(invoice_models.Invoice.id.desc()).first()
    if not last_invoice:
        return "INV-0001"
    last_num = int(last_invoice[0].split('-')[1])
    return f"INV-{last_num + 1:04d}"

class InvoiceItemData(BaseModel):
    material_id: int
    description: Optional[str] = ""
    quantity: float
    rate: float
    tax_rate: float
    item_class: Optional[str] = None
    customer_project: Optional[str] = None

@router.post("/", tags=["Invoices"])
async def create_invoice(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    lpo_id: Optional[int] = Form(None),
    invoice_date: date = Form(...),
    invoice_due_date: date = Form(...),
    supplier_id: int = Form(...),
    project_id: int = Form(...),
    payment_mode: Optional[str] = Form(None),
    message_to_customer: Optional[str] = Form(None),
    memo: Optional[str] = Form(None),
    items_json: str = Form(...),
    subtotal: float = Form(...),
    tax_total: float = Form(...),
    grand_total: float = Form(...),
    attachments: List[UploadFile] = File(None)
):
    try:
        invoice_number = get_next_invoice_number(db)
        new_invoice = invoice_models.Invoice(
            invoice_number=invoice_number,
            lpo_id=lpo_id,
            invoice_date=invoice_date,
            invoice_due_date=invoice_due_date,
            supplier_id=supplier_id,
            project_id=project_id,
            payment_mode=payment_mode,
            message_to_customer=message_to_customer,
            memo=memo,
            subtotal=subtotal,
            tax_total=tax_total,
            grand_total=grand_total,
            created_by_id=current_user.id
        )

        items_data = [InvoiceItemData.parse_obj(item) for item in json.loads(items_json)]
        for item_data in items_data:
            new_invoice.items.append(invoice_models.InvoiceItem(**item_data.dict()))

        db.add(new_invoice)
        db.flush()

        # Handle file uploads
        if attachments:
            blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
            container_name = "invoice-attachments"
            async with blob_service_client:
                container_client = blob_service_client.get_container_client(container_name)
                if not await container_client.exists():
                    await container_client.create_container()

                for file in attachments:
                    blob_name = f"{uuid.uuid4()}-{file.filename}"
                    blob_client = container_client.get_blob_client(blob_name)
                    file_contents = await file.read()
                    await blob_client.upload_blob(file_contents, overwrite=True)
                    
                    new_att = invoice_models.InvoiceAttachment(
                        blob_url=blob_client.url,
                        file_name=file.filename,
                        invoice_id=new_invoice.id
                    )
                    db.add(new_att)

        db.commit()
        return {"message": "Invoice created successfully!", "invoice_id": new_invoice.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")



@router.get("/", tags=["Invoices"])
def get_invoices(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None
):
    """Fetches a paginated and searchable list of all Invoices."""
    query = db.query(invoice_models.Invoice).options(
        joinedload(invoice_models.Invoice.supplier),
        joinedload(invoice_models.Invoice.project)
    )

    if search:
        search_term = f"%{search}%"
        query = query.join(models.Supplier).join(models.Project).filter(
            or_(
                invoice_models.Invoice.invoice_number.ilike(search_term),
                models.Supplier.name.ilike(search_term),
                models.Project.name.ilike(search_term)
            )
        )

    total_count = query.count()
    invoices = query.order_by(invoice_models.Invoice.invoice_date.desc()).offset(skip).limit(limit).all()
    
    return {"total_count": total_count, "invoices": invoices}


@router.get("/{invoice_id}", tags=["Invoices"])
def get_invoice_details(invoice_id: int, db: Session = Depends(deps.get_db)):
    """Fetches all details for a single Invoice."""
    invoice = db.query(invoice_models.Invoice).options(
        joinedload(invoice_models.Invoice.supplier),
        joinedload(invoice_models.Invoice.project),
        joinedload(invoice_models.Invoice.created_by),
        selectinload(invoice_models.Invoice.items).joinedload(invoice_models.InvoiceItem.material),
        selectinload(invoice_models.Invoice.attachments)
    ).filter(invoice_models.Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    for attachment in invoice.attachments:
        attachment.blob_url = generate_sas_url(attachment.blob_url)
        
    return invoice


@router.get("/{invoice_id}/pdf", tags=["Invoices"], response_class=StreamingResponse)
def generate_invoice_pdf(invoice_id: int, db: Session = Depends(deps.get_db)):
    """Generates and returns a PDF for a given Invoice."""
    invoice = db.query(invoice_models.Invoice).options(
        joinedload(invoice_models.Invoice.supplier),
        joinedload(invoice_models.Invoice.project),
        joinedload(invoice_models.Invoice.created_by),
        selectinload(invoice_models.Invoice.items).joinedload(invoice_models.InvoiceItem.material)
    ).filter(invoice_models.Invoice.id == invoice_id).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    logo_data_uri = image_to_data_uri("static/img/logo.png")
    
    # --- REUSE THE LPO PDF TEMPLATE ---
    # We pass the 'invoice' object but alias it as 'lpo' for the template
    # We also change the title
    context = {
        "lpo": invoice, 
        "logo_data_uri": logo_data_uri,
        "document_title": "INVOICE" # Add a title variable
    }
    html_string = pdf_templates.get_template("invoice/invoice_pdf.html").render(context)

    pdf_bytes = HTML(string=html_string).write_pdf()
    headers = {'Content-Disposition': f'inline; filename="{invoice.invoice_number}.pdf"'}
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)