# app/design_v2_models.py
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Text, Boolean,
    ForeignKey, Enum as SQLAlchemyEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.models import Base, User

# --- Enums for V2 ---
class StageName(str, enum.Enum):
    STAGE_2A = "Project Initiation & Site Visit"
    STAGE_3 = "Initial Design Development"
    STAGE_4 = "Revision & Refinement"
    STAGE_5 = "Technical Review & Coordination"
    STAGE_6 = "Authority Drawing Package"
    STAGE_7 = "Final Package Delivery"
    STAGE_8 = "Handover to Execution"

class StageStatus(str, enum.Enum):
    LOCKED = "Locked"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"

class TaskStatusV2(str, enum.Enum):
    OPEN = "Open"
    SUBMITTED = "Submitted"
    REVISION = "Revision Required"
    APPROVED = "Approved"
    VERIFIED = "Verified"

# --- New & Updated Models for V2 ---

class DesignProjectV2(Base):
    __tablename__ = 'design_projects_v2'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    client = Column(String)
    status = Column(String, default="Active")
    finance_confirmed_at = Column(DateTime, default=func.now())
    created_by_id = Column(Integer, ForeignKey('users.id'))
    
    created_by = relationship("User")
    stages = relationship("DesignStage", back_populates="project", cascade="all, delete-orphan", order_by="DesignStage.order")

class DesignStage(Base):
    __tablename__ = 'design_stages'
    id = Column(Integer, primary_key=True)
    name = Column(SQLAlchemyEnum(StageName), nullable=False)
    status = Column(SQLAlchemyEnum(StageStatus), default=StageStatus.LOCKED, nullable=False)
    order = Column(Integer, nullable=False) # To enforce the 1-8 sequence
    
    project_id = Column(Integer, ForeignKey('design_projects_v2.id'), nullable=False)
    
    project = relationship("DesignProjectV2", back_populates="stages")
    tasks = relationship("DesignTaskV2", back_populates="stage", cascade="all, delete-orphan")

class DesignTaskV2(Base):
    __tablename__ = 'design_tasks_v2'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    status = Column(SQLAlchemyEnum(TaskStatusV2), default=TaskStatusV2.OPEN, nullable=False)
    due_date = Column(Date)
    submitted_at = Column(DateTime)
    file_link = Column(Text)
    
    stage_id = Column(Integer, ForeignKey('design_stages.id'), nullable=False)
    owner_id = Column(Integer, ForeignKey('users.id'))
    
    stage = relationship("DesignStage", back_populates="tasks")
    owner = relationship("User")

# --- New Compliance Models ---

class SiteVisitLog(Base):
    __tablename__ = 'site_visit_logs'
    id = Column(Integer, primary_key=True)
    stage_id = Column(Integer, ForeignKey('design_stages.id'), nullable=False, unique=True)
    meeting_held_at = Column(DateTime)
    mom_link = Column(Text)
    site_photos_link = Column(Text)
    updated_brief_link = Column(Text)

class InterdisciplinarySignoff(Base):
    __tablename__ = 'interdisciplinary_signoffs'
    id = Column(Integer, primary_key=True)
    discipline = Column(String, nullable=False) # e.g., "Structural", "MEP"
    is_approved = Column(Boolean, default=False)
    signed_off_at = Column(DateTime)
    notes = Column(Text)
    
    stage_id = Column(Integer, ForeignKey('design_stages.id'), nullable=False)
    signed_off_by_id = Column(Integer, ForeignKey('users.id'))
    
    signed_off_by = relationship("User")