from sqlalchemy import (
    Column, Integer, String, Date, Numeric, ForeignKey, DateTime, func, Text, Boolean
)
from sqlalchemy.orm import relationship, declarative_base
from passlib.context import CryptContext
import enum
from sqlalchemy import Table, Enum as SQLAlchemyEnum

Base = declarative_base()

# Define the user roles
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "Super Admin"
    ADMIN = "Admin"
    OPERATION_MANAGER = "Operation Mananger"
    PROJECT_MANAGER = "Project Manager"
    SITE_ENGINEER = "Site Engineer"
    SUPERVISOR = "Supervisor/Site Officer"
    FOREMAN = "Foreman/Duty Officer"
    PROCUREMENT = "Procurement"
    QS = "QS"
    USER = "User"

# Association table for the many-to-many relationship between users and roles
user_role_association = Table(
    'user_role_association',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('role_id', Integer, ForeignKey('roles.id'))
)

class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(SQLAlchemyEnum(UserRole), unique=True, nullable=False)

    def __str__(self) -> str:
        return self.name.value

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True) 
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    roles = relationship("Role", secondary=user_role_association, backref="users")
    material_requisitions = relationship("MaterialRequisition", back_populates="requested_by")
    mr_comments = relationship("MaterialRequisitionComment", back_populates="comment_by")

    def verify_password(self, plain_password: str) -> bool:
        return pwd_context.verify(plain_password, self.hashed_password)
    
    def set_password(self, plain_password: str):
        self.hashed_password = pwd_context.hash(plain_password)
        
    def __str__(self) -> str:
        return self.email

# --- NEW Model for Site Images ---
class SiteImage(Base):
    __tablename__ = 'site_images'
    id = Column(Integer, primary_key=True, index=True)
    
    # Links to parent forms (one of these will be populated)
    duty_officer_progress_id = Column(Integer, ForeignKey('duty_officer_progress.id'), nullable=True)
    site_officer_report_id = Column(Integer, ForeignKey('site_officer_reports.id'), nullable=True)

    blob_url = Column(String, nullable=False) # URL of the image in Azure Blob
    file_name = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=func.now())

    def __str__(self) -> str:
        return self.file_name or f"Image #{self.id}"


# --- EXISTING Models (with new relationships added) ---

class DutyOfficerProgress(Base):
    __tablename__ = 'duty_officer_progress'
    # ... (all existing columns are the same)
    id = Column(Integer, primary_key=True, index=True)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    foreman_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    job_card_id = Column(Integer, ForeignKey('job_cards.id'), nullable=False)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    date_of_work = Column(Date, nullable=False)
    actual_output = Column(Text, nullable=False)
    issues_delays = Column(Text, nullable=False)
    tbt_attendance = Column(Text, nullable=False)
    tbt_topic_discussed = Column(String)
    tbt_key_points = Column(Text, nullable=False)
    sm_equipment_inventory = Column(Text, nullable=False)
    sm_equipment_condition = Column(String)
    sm_equipment_transfer = Column(String)
    sm_remarks = Column(Text)
    sm_sub_contractor_coordination = Column(String)
    sm_coordination_issues = Column(Text)
    sm_ppe_check = Column(Boolean, default=False)
    sm_safety_hazards = Column(Text, nullable=False)
    sm_photos_on_whatsapp = Column(Boolean, default=False)
    sm_foreman_signature_id = Column(Integer, ForeignKey('foremen.id'), nullable=False)
    mm_deliveries_received = Column(String, nullable=False)
    mm_rejection_reason = Column(Text)
    mm_stock_balance = Column(Text, nullable=False)
    mm_material_transfers = Column(String)
    kt_sops_explained = Column(String)
    kt_help_required_details = Column(Text)
    kt_critical_actions_required = Column(Text)
    created_at = Column(DateTime, default=func.now())
    
    job_card = relationship("JobCard", back_populates="progress_reports")
    foreman_signature = relationship("Foreman", back_populates="progress_reports")
    toolbox_videos = relationship("ToolboxVideo")

    # ADDED: Relationship to images
    site_images = relationship("SiteImage")

    def __str__(self) -> str: return f"Report for JC-{self.job_card_id} on {self.date_of_work}"


class SiteOfficerReport(Base):
    __tablename__ = 'site_officer_reports'
    # ... (all existing columns are the same)
    id = Column(Integer, primary_key=True, index=True)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    # --- ADD THESE TWO LINES ---
    site_officer_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    duty_officer_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    # --------------------------
    date = Column(Date, nullable=False)
    site_location = Column(String, nullable=False)
    site_officer_id = Column(Integer, ForeignKey('supervisors.id'), nullable=False)
    duty_officer_id = Column(Integer, ForeignKey('foremen.id'), nullable=False)
    tbt_attendance = Column(Text)
    tbt_topic_discussed = Column(String)
    tbt_key_points = Column(Text)
    job_card_id = Column(Integer, ForeignKey('job_cards.id'), nullable=False)
    form_b_completed_check = Column(Boolean, default=False)
    dependency_notes = Column(Text)
    progress_pictures_check = Column(Boolean, default=False)
    sm_manpower_availability = Column(Text)
    sm_subcontractor_coordination = Column(String)
    sm_coordination_issues = Column(Text)
    sm_other_notes = Column(Text)
    material_requisition_project_id = Column(Integer, ForeignKey('projects.id'))
    commercial_delivery_check = Column(Boolean, default=False)
    delivery_comments = Column(Text)
    qc_steps_explained = Column(Boolean, default=False)
    qc_steps_details = Column(Text)
    qc_drawing_mismatches = Column(Text)
    re_delays_flagged_reason = Column(Text)
    re_support_needed = Column(Text)
    hs_waste_management = Column(String)
    hs_waste_management_comments = Column(Text)
    hs_walkways_clear = Column(String)
    hs_material_storage = Column(String)
    hs_ppe_compliance = Column(Boolean, default=False)
    hs_incidents_near_misses = Column(Text)
    hs_safety_comments = Column(Text)
    sa_overall_site_health = Column(String)
    sa_immediate_actions = Column(Text)
    sa_responsible_person = Column(String)
    sa_action_deadline = Column(Date)
    sa_critical_actions = Column(Text)
    sa_approved_drawings_check = Column(String)
    sa_drawing_help_details = Column(Text)
    created_at = Column(DateTime, default=func.now())
    
    site_officer = relationship("Supervisor", back_populates="site_officer_reports")
    duty_officer = relationship("Foreman", back_populates="site_officer_reports")
    job_card = relationship("JobCard", back_populates="site_officer_reports")
    material_requisition_project = relationship("Project", back_populates="site_officer_reports")
    toolbox_videos = relationship("ToolboxVideo")

    # ADDED: Relationship to images
    site_images = relationship("SiteImage")
    
    def __str__(self) -> str: return f"Site Officer Report for {self.site_location} on {self.date}"

# ... (rest of models like Project, Supervisor, Task, etc., are unchanged) ...
class ToolboxVideo(Base):
    __tablename__ = 'toolbox_videos'
    id = Column(Integer, primary_key=True, index=True)
    duty_officer_progress_id = Column(Integer, ForeignKey('duty_officer_progress.id'), nullable=True)
    site_officer_report_id = Column(Integer, ForeignKey('site_officer_reports.id'), nullable=True)
    blob_url = Column(String, nullable=True)
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    processing_status = Column(String, nullable=False, default='pending')
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    def __str__(self) -> str: return f"Video #{self.id} ({self.processing_status})"

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    job_cards = relationship("JobCard", back_populates="project")
    site_officer_reports = relationship("SiteOfficerReport", back_populates="material_requisition_project")
    material_requisitions = relationship("MaterialRequisition", back_populates="project")
    def __str__(self) -> str: return self.name

class SiteEngineer(Base):
    __tablename__ = 'site_engineers'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    job_cards = relationship("JobCard", back_populates="site_engineer")
    def __str__(self) -> str: return self.name

class Supervisor(Base):
    __tablename__ = 'supervisors'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    job_cards = relationship("JobCard", back_populates="supervisor")
    site_officer_reports = relationship("SiteOfficerReport", back_populates="site_officer")
    
    def __str__(self) -> str: return self.name

class Foreman(Base):
    __tablename__ = 'foremen'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    job_cards = relationship("JobCard", back_populates="foreman")
    progress_reports = relationship("DutyOfficerProgress", back_populates="foreman_signature")
    site_officer_reports = relationship("SiteOfficerReport", back_populates="duty_officer")
    def __str__(self) -> str: return self.name

class JobCard(Base):
    __tablename__ = 'job_cards'
    id = Column(Integer, primary_key=True, index=True)
    job_card_no = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, nullable=False, default='Pending', index=True)
    date_issued = Column(Date, nullable=False)
    site_location = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    site_engineer_id = Column(Integer, ForeignKey('site_engineers.id'), nullable=False)
    supervisor_id = Column(Integer, ForeignKey('supervisors.id'), nullable=False)
    foreman_id = Column(Integer, ForeignKey('foremen.id'), nullable=False)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    site_engineer_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    supervisor_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    foreman_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    project = relationship("Project", back_populates="job_cards")
    site_engineer = relationship("SiteEngineer", back_populates="job_cards")
    supervisor = relationship("Supervisor", back_populates="job_cards")
    foreman = relationship("Foreman", back_populates="job_cards")
    tasks = relationship("Task", back_populates="job_card", cascade="all, delete-orphan")
    progress_reports = relationship("DutyOfficerProgress", back_populates="job_card", cascade="all, delete-orphan")
    site_officer_reports = relationship("SiteOfficerReport", back_populates="job_card", cascade="all, delete-orphan")
    def __str__(self) -> str: return self.job_card_no

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True, index=True)
    task_details = Column(String)
    status = Column(String, nullable=False, default='Pending', index=True)
    quantity = Column(Numeric(10, 2))
    units = Column(String)
    priority = Column(Integer, default=3)
    start_date = Column(Date)
    end_date = Column(Date)
    assigned_crew = Column(String)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    job_card_id = Column(Integer, ForeignKey('job_cards.id'), nullable=False)
    job_card = relationship("JobCard", back_populates="tasks")
    def __str__(self) -> str: return f"Task #{self.id}: {self.task_details[:50]}" if self.task_details else f"Task #{self.id}"

class MaterialRequisition(Base):
    __tablename__ = 'material_requisitions'
    id = Column(Integer, primary_key=True, index=True)
    request_date = Column(Date, nullable=False, default=func.current_date())
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    requested_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    material_type = Column(String, nullable=False)
    material_with_quantity = Column(Text, nullable=False)
    urgency = Column(String, nullable=False)
    required_delivery_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    mr_number = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False, default='Pending')
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=True)
    lpo_number = Column(String, nullable=True)
    pm_approval = Column(String, nullable=True, default='Pending')
    qs_approval = Column(String, nullable=True, default='Pending')
    mr_approval = Column(String, nullable=True, default='Pending')
    payment_status = Column(String, nullable=True)
    remarks = Column(Text, nullable=True)
    project = relationship("Project", back_populates="material_requisitions")
    requested_by = relationship("User", back_populates="material_requisitions")
    supplier = relationship("Supplier", back_populates="requisitions")
    comments = relationship("MaterialRequisitionComment", back_populates="requisition", cascade="all, delete-orphan")
    def __str__(self) -> str:
        p_name = self.project.name if self.project else f"Project ID {self.project_id}"
        return f"Req #{self.id} ({self.mr_number or 'N/A'}) for {p_name}"

class Supplier(Base):
    __tablename__ = 'suppliers'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    requisitions = relationship("MaterialRequisition", back_populates="supplier")
    def __str__(self) -> str: return self.name


class NannyLog(Base):
    __tablename__ = 'nanny_logs'
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to the user who is the nanny
    nanny_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    # Foreign key to the user who created the log (can be the same or an admin)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=func.now())
    log_date = Column(Date, nullable=False)

    # Hygiene & Safety
    handwashing_checks = Column(String, nullable=True) # Stored as comma-separated string
    environment_checks = Column(String, nullable=True) # Stored as comma-separated string

    # Meals & Hydration
    breakfast_details = Column(Text, nullable=True)
    breakfast_amount = Column(String, nullable=True)
    lunch_details = Column(Text, nullable=True)
    lunch_amount = Column(String, nullable=True)
    snack_details = Column(Text, nullable=True)
    snack_amount = Column(String, nullable=True)
    dinner_details = Column(Text, nullable=True)
    dinner_amount = Column(String, nullable=True)
    hydration_morning_cups = Column(String, nullable=True)
    hydration_afternoon_cups = Column(String, nullable=True)
    hydration_evening_cups = Column(String, nullable=True)
    restricted_foods_given = Column(Boolean, default=False)
    restricted_foods_details = Column(Text, nullable=True)

    # Routine & Rest
    nap_duration_minutes = Column(Integer, nullable=True)
    bedtime_by_830pm = Column(Boolean, default=False)
    total_sleep_hours = Column(String, nullable=True)

    # Play & Activities
    outdoor_play_completed = Column(Boolean, default=False)
    outdoor_play_minutes = Column(Integer, nullable=True)
    screen_time_minutes = Column(Integer, nullable=True)

    # Health & Observation
    temperature_celsius = Column(Numeric(4, 1), nullable=True)
    appetite = Column(String, nullable=True)
    behavior = Column(String, nullable=True)
    signs_of_illness = Column(Text, nullable=True)
    nanny_notes = Column(Text, nullable=True)

    # Relationships
    nanny = relationship("User", foreign_keys=[nanny_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class MaterialRequisitionComment(Base):
    __tablename__ = 'mr_comments'
    id = Column(Integer, primary_key=True, index=True)
    comment_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())

    requisition_id = Column(Integer, ForeignKey('material_requisitions.id'), nullable=False)
    comment_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    requisition = relationship("MaterialRequisition", back_populates="comments")
    comment_by = relationship("User", back_populates="mr_comments")