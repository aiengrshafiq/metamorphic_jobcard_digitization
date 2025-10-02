# app/design_models.py
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Text, Boolean, Numeric,
    ForeignKey, Enum as SQLAlchemyEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
import enum

# Import the Base from your existing models file
from app.models import Base, User
from sqlalchemy.sql import func

# --- Enums for the Design Module ---
class DesignPhaseName(str, enum.Enum):
    PHASE_2 = "Phase 2 - Initial Design"
    PHASE_4 = "Phase 4 - Technical & Authority"
    PHASE_5 = "Phase 5 - Final Package"

class DesignTaskStatus(str, enum.Enum):
    OPEN = "Open"
    SUBMITTED = "Submitted"
    REVISION_REQUESTED = "Revision Requested"
    VERIFIED = "Verified"
    DONE = "Done"

# --- Main Models for the Design Workflow ---

class DesignProject(Base):
    __tablename__ = 'design_projects'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    client = Column(String, nullable=True)
    status = Column(String, default="Active")
    created_at = Column(DateTime, default=func.now())
    closed_at = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey('users.id'))
    
    created_by = relationship("User")
    phases = relationship("DesignPhase", back_populates="project", cascade="all, delete-orphan")

class DesignPhase(Base):
    __tablename__ = 'design_phases'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(SQLAlchemyEnum(DesignPhaseName), nullable=False)
    status = Column(String, default="In Progress")
    due_date = Column(Date, nullable=True)
    
    project_id = Column(Integer, ForeignKey('design_projects.id'), nullable=False)
    
    project = relationship("DesignProject", back_populates="phases")
    tasks = relationship("DesignTask", back_populates="phase", cascade="all, delete-orphan")

class DesignTask(Base):
    __tablename__ = 'design_tasks'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False) # e.g., "2D Layout", "DM QA Review"
    status = Column(SQLAlchemyEnum(DesignTaskStatus), default=DesignTaskStatus.OPEN, nullable=False)
    due_date = Column(Date, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    file_link = Column(Text, nullable=True)

    verified_at = Column(DateTime, nullable=True)
    verified_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)

    signed_off_at = Column(DateTime, nullable=True)
    sign_off_notes = Column(Text, nullable=True)
    signed_off_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    phase_id = Column(Integer, ForeignKey('design_phases.id'), nullable=False)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    phase = relationship("DesignPhase", back_populates="tasks")
    
    owner = relationship("User", back_populates="design_tasks", foreign_keys=[owner_id])
    #verified_by = relationship("User", foreign_keys=[verified_by_id])
    verified_by = relationship("User", back_populates="verified_tasks", foreign_keys=[verified_by_id])
    signed_off_by = relationship("User", foreign_keys=[signed_off_by_id])
    score = relationship("DesignScore", back_populates="task", uselist=False, cascade="all, delete-orphan")
    comments = relationship("DesignTaskComment", back_populates="task", cascade="all, delete-orphan")

class DesignScore(Base):
    __tablename__ = 'design_scores'
    id = Column(Integer, primary_key=True, index=True)
    score = Column(Integer, default=100)
    lateness_days = Column(Integer, default=0)
    
    task_id = Column(Integer, ForeignKey('design_tasks.id'), nullable=False, unique=True)
    task = relationship("DesignTask", back_populates="score")

class DesignTaskComment(Base):
    __tablename__ = 'design_task_comments'
    id = Column(Integer, primary_key=True, index=True)
    comment_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    task_id = Column(Integer, ForeignKey('design_tasks.id'), nullable=False)
    comment_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    task = relationship("DesignTask", back_populates="comments")
    comment_by = relationship("User")