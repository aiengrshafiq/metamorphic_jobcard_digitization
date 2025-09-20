# app/admin.py
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from sqlalchemy.orm import joinedload


from app.models import (
    User, Role, UserRole, JobCard, Task, Project, SiteEngineer, Supervisor, Foreman,
    DutyOfficerProgress, SiteOfficerReport, MaterialRequisition, Supplier, ToolboxVideo, SiteImage, NannyLog,Material
)
from app.auth.security import verify_password
from app.core.database import SessionLocal

class MyAuthBackend(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email, password = form.get("username"), form.get("password")

        db = SessionLocal()
        try:
            user = db.query(User).options(
                joinedload(User.roles)
            ).filter(User.email == email).first()

            if user and user.is_active and verify_password(password, user.hashed_password):
                user_roles = {role.name for role in user.roles}
                
                allowed_roles = {
                    UserRole.SUPER_ADMIN, 
                    UserRole.ADMIN, 
                    UserRole.OPERATION_MANAGER, 
                    UserRole.PROJECT_MANAGER
                }

                if user_roles.intersection(allowed_roles):
                    request.session.update({"user_email": user.email})
                    return True
        finally:
            db.close()
                
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "user_email" in request.session

# --- Define all your ModelViews here ---

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.name, User.email, User.is_active, User.roles]
    # Add the new 'material_requisitions' relationship here for viewing
    column_details_list = [User.id, User.name, User.email, User.is_active, User.roles, User.material_requisitions]
    form_columns = [User.name, User.email, User.is_active, User.roles]
    name_plural = "Users"

class RoleAdmin(ModelView, model=Role):
    column_list = [Role.id, Role.name]
    name_plural = "Roles"

class SiteImageAdmin(ModelView, model=SiteImage):
    column_list = [SiteImage.id, SiteImage.file_name, "duty_officer_progress_id", "site_officer_report_id"]
    column_formatters = {"blob_url": lambda m, a: f'<a href="{m.blob_url}" target="_blank"><img src="{m.blob_url}" width="100"></a>' if m.blob_url else "No image"}
    name_plural = "Site Images"

class ToolboxVideoAdmin(ModelView, model=ToolboxVideo):
    column_list = [ToolboxVideo.id, "duty_officer_progress_id", "site_officer_report_id", ToolboxVideo.processing_status]
    column_details_list = [c.name for c in ToolboxVideo.__table__.c]
    column_formatters = {"blob_url": lambda m, a: f'<a href="{m.blob_url}" target="_blank">Watch Video</a>' if m.blob_url else "No video"}
    name_plural = "Toolbox Videos"

class DutyOfficerProgressAdmin(ModelView, model=DutyOfficerProgress):
    column_list = [DutyOfficerProgress.id, "job_card", DutyOfficerProgress.date_of_work]
    column_formatters = {"job_card": lambda m, a: m.job_card.job_card_no if m.job_card else ""}
    column_details_list = [c.name for c in DutyOfficerProgress.__table__.c] + [DutyOfficerProgress.job_card, DutyOfficerProgress.foreman_signature, DutyOfficerProgress.toolbox_videos, DutyOfficerProgress.site_images]
    name_plural = "Progress Reports (Form B)"

class SiteOfficerReportAdmin(ModelView, model=SiteOfficerReport):
    column_list = [SiteOfficerReport.id, SiteOfficerReport.date, "job_card"]
    column_formatters = {"job_card": lambda m, a: m.job_card.job_card_no if m.job_card else ""}
    column_details_list = [c.name for c in SiteOfficerReport.__table__.c] + [SiteOfficerReport.site_officer, SiteOfficerReport.duty_officer, SiteOfficerReport.job_card, SiteOfficerReport.material_requisition_project, SiteOfficerReport.toolbox_videos, SiteOfficerReport.site_images]
    name_plural = "Site Officer Reports (Form C)"

class JobCardAdmin(ModelView, model=JobCard):
    column_list = [JobCard.id, JobCard.job_card_no, JobCard.project]
    column_details_list = [c.name for c in JobCard.__table__.c] + [JobCard.project, JobCard.site_engineer, JobCard.supervisor, JobCard.foreman, JobCard.tasks, JobCard.progress_reports, JobCard.site_officer_reports]
    name_plural = "Job Cards (Form A)"

class MaterialRequisitionAdmin(ModelView, model=MaterialRequisition):
    # Updated to show the user's name
    column_list = [MaterialRequisition.id, MaterialRequisition.mr_number, "requested_by", "project", "status"]
    column_formatters = {"project": lambda m, a: m.project.name if m.project else "", "requested_by": lambda m, a: m.requested_by.name if m.requested_by else ""}
    name_plural = "Material Requisitions"

class SupplierAdmin(ModelView, model=Supplier):
    column_list = [Supplier.id, Supplier.name, Supplier.email, Supplier.phone]
    name_plural = "Suppliers"

class ProjectAdmin(ModelView, model=Project):
    column_list = [Project.id, Project.name]
    column_details_list = [Project.id, Project.name, Project.job_cards, Project.site_officer_reports, Project.material_requisitions]

class SupervisorAdmin(ModelView, model=Supervisor):
    column_list = [Supervisor.id, Supervisor.name]
    # --- THIS IS THE FIX ---
    # Removed Supervisor.material_requisitions because it no longer exists on the model
    column_details_list = [Supervisor.id, Supervisor.name, Supervisor.job_cards, Supervisor.site_officer_reports]
    # -----------------------

class ForemanAdmin(ModelView, model=Foreman):
    column_list = [Foreman.id, Foreman.name]
    column_details_list = [Foreman.id, Foreman.name, Foreman.job_cards, Foreman.progress_reports, Foreman.site_officer_reports]

class SiteEngineerAdmin(ModelView, model=SiteEngineer):
    column_list = [SiteEngineer.id, SiteEngineer.name]
    column_details_list = [SiteEngineer.id, SiteEngineer.name, SiteEngineer.job_cards]

class NannyLogAdmin(ModelView, model=NannyLog):
    column_list = [NannyLog.id, NannyLog.nanny_id, NannyLog.log_date, NannyLog.created_by]
    column_details_list = [NannyLog.id, NannyLog.nanny_id, NannyLog.log_date, NannyLog.created_by]

class MaterialAdmin(ModelView, model=Material):
    column_list = [Material.id, Material.name, Material.unit]
    form_columns = [Material.name, Material.unit]
    name_plural = "Master Materials"

# --- Function to add all views to the admin instance ---
def create_admin_views(admin: Admin):
    admin.add_view(MaterialAdmin)
    admin.add_view(UserAdmin)
    admin.add_view(RoleAdmin)
    admin.add_view(SiteImageAdmin)
    admin.add_view(ToolboxVideoAdmin)
    admin.add_view(JobCardAdmin)
    admin.add_view(DutyOfficerProgressAdmin)
    admin.add_view(SiteOfficerReportAdmin)
    admin.add_view(MaterialRequisitionAdmin)
    admin.add_view(SupplierAdmin)
    admin.add_view(ProjectAdmin)
    admin.add_view(SiteEngineerAdmin)
    admin.add_view(SupervisorAdmin)
    admin.add_view(ForemanAdmin)
    admin.add_view(NannyLogAdmin)