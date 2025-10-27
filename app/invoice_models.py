# app/invoice_models.py
from sqlalchemy import Column, Integer, String, Date, DateTime, Text, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import date, timedelta

from app.models import Base, LPO, Project, User, Material

class Invoice(Base):
    __tablename__ = 'invoices'
    id = Column(Integer, primary_key=True, index=True)
    
    # New Invoice-specific fields
    invoice_number = Column(String, unique=True, nullable=False)
    invoice_date = Column(Date, nullable=False, default=func.current_date())
    invoice_due_date = Column(Date, nullable=False, default=lambda: date.today() + timedelta(days=30))
    lpo_id = Column(Integer, ForeignKey('lpos.id'), nullable=True) # Link to LPO
    
    # Fields copied from LPO
    status = Column(String, nullable=False, default='Pending') # e.g., Pending, Paid
    subtotal = Column(Numeric(12, 2), nullable=True)
    tax_total = Column(Numeric(12, 2), nullable=True)
    grand_total = Column(Numeric(12, 2), nullable=True)
    message_to_customer = Column(Text, nullable=True) # Renamed from message_to_supplier
    memo = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    payment_mode = Column(String, nullable=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    lpo = relationship("LPO")
    supplier = relationship("Supplier")
    project = relationship("Project")
    created_by = relationship("User")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    attachments = relationship("InvoiceAttachment", back_populates="invoice", cascade="all, delete-orphan")

class InvoiceItem(Base):
    __tablename__ = 'invoice_items'
    id = Column(Integer, primary_key=True, index=True)
    
    # Copied from LPOItem
    description = Column(Text, nullable=True)
    quantity = Column(Numeric(10, 2), nullable=False)
    rate = Column(Numeric(10, 2), nullable=False)
    tax_rate = Column(Numeric(4, 2), default=0.00)
    
    # New Invoice-specific fields
    item_class = Column(String, nullable=True)
    customer_project = Column(String, nullable=True) # For "project or customer"

    # Relationships
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=False)
    material_id = Column(Integer, ForeignKey('materials.id'), nullable=False)
    
    invoice = relationship("Invoice", back_populates="items")
    material = relationship("Material")

class InvoiceAttachment(Base):
    __tablename__ = 'invoice_attachments'
    id = Column(Integer, primary_key=True, index=True)
    blob_url = Column(String, nullable=False)
    file_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=True)
    invoice = relationship("Invoice", back_populates="attachments")