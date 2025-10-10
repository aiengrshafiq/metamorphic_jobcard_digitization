# app/design_v3_models.py
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Text, Boolean, Numeric,
    ForeignKey, Enum as SQLAlchemyEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.models import Base, User
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

# --- Enums for the V3 Design Module ---
class CommitmentPackage(str, enum.Enum):
    DESIGN_BUILD = "Design & Build Commitment Fee"
    GUESSTIMATE = "Guesstimate Package"
    DESIGN_ONLY = "Design Fee Only"
    GOLD_VR = "Gold (VR) Package"

# class StageV3Name(str, enum.Enum):
#     FINANCE_CONFIRMATION = "Stage 0 - Finance Confirmation"
#     DEAL_CREATION = "Stage 1 - Deal Creation"
#     SITE_VISIT = "Stage 2A - Design Activation & Site Visit"
#     MEASUREMENT = "Stage 2B - Measurement Requisition"
#     INITIAL_DESIGN = "Stage 3 - Initial Design Development"
#     QS_HANDOVER = "Stage 4 - Forward to QS"
#     MANAGEMENT_OVERSIGHT = "Stage 5 - Management Oversight"

class StageV3Name(str, enum.Enum):
    FINANCE_CONFIRMATION = "Stage 0 - Finance Confirmation"
    DEAL_CREATION = "Stage 1 - Deal Creation"
    SITE_VISIT = "Stage 2A - Design Activation & Site Visit"
    MEASUREMENT = "Stage 2B - Measurement Requisition"
    INITIAL_DESIGN = "Stage 3 - Initial Design Development"
    QS_HANDOVER = "Stage 4 - Forward to QS"
    # Corrected and added missing stages based on CEO spec
    TECH_REVIEW = "Stage 5 - Technical Review & Coordination"
    AUTHORITY_PACKAGE = "Stage 6 - Authority Drawing Package"
    FINAL_DELIVERY = "Stage 7 - Final Package Delivery"
    EXECUTION_HANDOVER = "Stage 8 - Handover to Execution"


class StageV3Status(str, enum.Enum):
    LOCKED = "Locked"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"

class TaskStatusV3(str, enum.Enum):
    OPEN = "Open"
    SUBMITTED = "Submitted"
    REVISION = "Revision Required"
    APPROVED = "Approved"

# --- Main Models for the V3 Workflow ---
class Deal(Base):
    __tablename__ = 'deals'
    id = Column(Integer, primary_key=True)
    project_name = Column(String, nullable=False)
    client_name = Column(String, nullable=False)
    client_contact = Column(String)
    location = Column(String)
    contract_type = Column(SQLAlchemyEnum(CommitmentPackage, name="commitmentpackage"), nullable=False)
    budget = Column(Numeric(12, 2))
    payment_date = Column(Date)
    contract_date = Column(Date)
    initial_brief_link = Column(Text)
    floor_plan_link = Column(Text)
    as_built_link = Column(Text)
    created_at = Column(DateTime, default=func.now())
    sip_id = Column(Integer, ForeignKey('users.id'))
    
    sip = relationship("User")
    project = relationship("DesignProjectV3", back_populates="deal", uselist=False)


class DesignProjectV3(Base):
    __tablename__ = 'design_projects_v3'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    client = Column(String)
    status = Column(String, default="Active")
    created_at = Column(DateTime, default=func.now())
    created_by_id = Column(Integer, ForeignKey('users.id'))
    deal_id = Column(Integer, ForeignKey('deals.id'), unique=True)
    handover_design_head_signed_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    handover_design_head_signed_at = Column(DateTime, nullable=True)
    handover_ops_head_signed_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    handover_ops_head_signed_at = Column(DateTime, nullable=True)

    # --- THIS IS THE FIX ---
    # Specify the foreign_keys for each relationship to the User table
    created_by = relationship("User", foreign_keys=[created_by_id])
    handover_design_head_signed_by = relationship("User", foreign_keys=[handover_design_head_signed_by_id])
    handover_ops_head_signed_by = relationship("User", foreign_keys=[handover_ops_head_signed_by_id])
    # -----------------------

    deal = relationship("Deal", back_populates="project")
    stages = relationship(
        "DesignStageV3",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="DesignStageV3.order",
    )
# class DesignProjectV3(Base):
#     __tablename__ = 'design_projects_v3'
#     id = Column(Integer, primary_key=True)
#     name = Column(String, nullable=False)
#     client = Column(String)
#     status = Column(String, default="Active")
#     created_at = Column(DateTime, default=func.now())
#     created_by_id = Column(Integer, ForeignKey('users.id'))
#     deal_id = Column(Integer, ForeignKey('deals.id'), unique=True)

#     # --- ADD THESE NEW COLUMNS ---
#     handover_design_head_signed_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
#     handover_design_head_signed_at = Column(DateTime, nullable=True)
#     handover_ops_head_signed_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
#     handover_ops_head_signed_at = Column(DateTime, nullable=True)
#     # -----------------------------

#     created_by = relationship("User")
#     deal = relationship("Deal", back_populates="project")
#     stages = relationship(
#         "DesignStageV3",
#         back_populates="project",
#         cascade="all, delete-orphan",
#         order_by="DesignStageV3.order",
#     )
#     # --- ADD THESE NEW RELATIONSHIPS ---
#     handover_design_head_signed_by = relationship("User", foreign_keys=[handover_design_head_signed_by_id])
#     handover_ops_head_signed_by = relationship("User", foreign_keys=[handover_ops_head_signed_by_id])
#     # ---------------------------------

# class DesignStageV3(Base):
#     __tablename__ = 'design_stages_v3'
#     id = Column(Integer, primary_key=True)
#     # name = Column(SQLAlchemyEnum(StageV3Name, name="stagename"), nullable=False)
#     # status = Column(SQLAlchemyEnum(StageV3Status, name="stagev3status"), nullable=False)
#     name = Column(
#         PGEnum(StageV3Name, name="stagename", native_enum=True,
#                create_type=False, validate_strings=True),
#         nullable=False
#     )
#     status = Column(
#         PGEnum(StageV3Status, name="stagev3status", native_enum=True,
#                create_type=False, validate_strings=True),
#         nullable=False
#     )
#     order = Column(Integer, nullable=False)
#     project_id = Column(Integer, ForeignKey('design_projects_v3.id'), nullable=False)

#     project = relationship("DesignProjectV3", back_populates="stages")
#     site_visit_log = relationship("SiteVisitLog", back_populates="stage", uselist=False, cascade="all, delete-orphan")
#     tasks = relationship("DesignTaskV3", back_populates="stage", cascade="all, delete-orphan")
#     qs_validation = relationship("QSValidation", back_populates="stage", uselist=False, cascade="all, delete-orphan")
#     measurement_requisition = relationship("MeasurementRequisition", back_populates="stage", uselist=False, cascade="all, delete-orphan")
#     interdisciplinary_signoffs = relationship("InterdisciplinarySignoff", back_populates="stage", cascade="all, delete-orphan")


class DesignStageV3(Base):
    __tablename__ = 'design_stages_v3'
    id = Column(Integer, primary_key=True)

    # For 'name' we must store the Enum .value (long human label) to match DB labels
    name = Column(
        PGEnum(
            StageV3Name,
            name="stagename",
            native_enum=True,
            create_type=False,
            validate_strings=True,
            values_callable=lambda E: [e.value for e in E],  # <<< IMPORTANT
        ),
        nullable=False,
    )

    # For 'status' we keep storing the Enum .name (UPPERCASE) to match DB labels
    status = Column(
        PGEnum(
            StageV3Status,
            name="stagev3status",
            native_enum=True,
            create_type=False,
            validate_strings=True,
            # (default behavior uses .name; being explicit is fine too:)
            values_callable=lambda E: [e.name for e in E],
        ),
        nullable=False,
    )

    order = Column(Integer, nullable=False)
    project_id = Column(Integer, ForeignKey('design_projects_v3.id'), nullable=False)

    project = relationship("DesignProjectV3", back_populates="stages")
    site_visit_log = relationship("SiteVisitLog", back_populates="stage", uselist=False, cascade="all, delete-orphan")
    tasks = relationship("DesignTaskV3", back_populates="stage", cascade="all, delete-orphan")
    qs_validation = relationship("QSValidation", back_populates="stage", uselist=False, cascade="all, delete-orphan")
    measurement_requisition = relationship("MeasurementRequisition", back_populates="stage", uselist=False, cascade="all, delete-orphan")
    interdisciplinary_signoffs = relationship("InterdisciplinarySignoff", back_populates="stage", cascade="all, delete-orphan")


class DesignTaskV3(Base):
    __tablename__ = 'design_tasks_v3'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    status = Column(SQLAlchemyEnum(TaskStatusV3, name="taskstatusv3"), default=TaskStatusV3.OPEN, nullable=False)
    due_date = Column(Date)
    submitted_at = Column(DateTime)
    file_link = Column(Text)
    
    stage_id = Column(Integer, ForeignKey('design_stages_v3.id'), nullable=False)
    owner_id = Column(Integer, ForeignKey('users.id'))
    
    stage = relationship("DesignStageV3")
    owner = relationship("User")
    

class SiteVisitLog(Base):
    __tablename__ = 'site_visit_logs'
    id = Column(Integer, primary_key=True)
    
    meeting_held_at = Column(DateTime, nullable=True)
    mom_link = Column(Text, nullable=True)
    site_photos_link = Column(Text, nullable=True)
    updated_brief_link = Column(Text, nullable=True)
    
    # This creates a one-to-one relationship with the stage
    stage_id = Column(Integer, ForeignKey('design_stages_v3.id'), nullable=False, unique=True)
    
    stage = relationship("DesignStageV3", back_populates="site_visit_log")


class QSValidation(Base):
    __tablename__ = 'qs_validations'
    id = Column(Integer, primary_key=True)
    cost_estimation_sheet_link = Column(Text, nullable=False)
    validated_boq_link = Column(Text, nullable=False)
    validated_at = Column(DateTime, default=func.now())
    
    stage_id = Column(Integer, ForeignKey('design_stages_v3.id'), nullable=False, unique=True)
    validated_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    validated_by = relationship("User")
    stage = relationship("DesignStageV3", back_populates="qs_validation")

class Vendor(Base):
    __tablename__ = 'vendors'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    contact_email = Column(String)
    
    def __str__(self) -> str:
        return self.name

class MeasurementRequisition(Base):
    __tablename__ = 'measurement_requisitions'
    id = Column(Integer, primary_key=True)
    status = Column(String, default="Pending Vendor Upload") # e.g., Pending, Uploaded, Approved
    requested_at = Column(DateTime, default=func.now())
    
    stage_id = Column(Integer, ForeignKey('design_stages_v3.id'), nullable=False, unique=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    
    vendor = relationship("Vendor")
    stage = relationship("DesignStageV3", back_populates="measurement_requisition")


class InterdisciplinarySignoff(Base):
    __tablename__ = 'interdisciplinary_signoffs_v3'
    id = Column(Integer, primary_key=True)
    discipline = Column(String, nullable=False) # e.g., "Structural", "MEP"
    is_approved = Column(Boolean, default=False)
    signed_off_at = Column(DateTime, default=func.now())
    notes = Column(Text)
    
    stage_id = Column(Integer, ForeignKey('design_stages_v3.id'), nullable=False)
    signed_off_by_id = Column(Integer, ForeignKey('users.id'))
    
    signed_off_by = relationship("User")
    stage = relationship("DesignStageV3", back_populates="interdisciplinary_signoffs")