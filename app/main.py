from fastapi import FastAPI, Request, Depends, Form, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, Select, func
from sqlalchemy.orm import Session, joinedload, selectinload
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from typing import List, Optional
from datetime import date
import yaml
import os
import uuid
import tempfile
import openai
import json
from azure.storage.blob import BlobServiceClient

# --- THIS IS THE NEW IMPORT ---
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.database import engine, get_db
from app.core.config import settings
from app.models import (
    Base, JobCard, Task, Project, SiteEngineer, Supervisor, Foreman, 
    DutyOfficerProgress, SiteOfficerReport, MaterialRequisition, Supplier, ToolboxVideo, SiteImage
)

# --- App and Admin Panel Setup ---
app = FastAPI(title="Metamorphic Job Card App")
# --- THIS IS THE FIX ---
# This middleware tells the app to trust the proxy headers from Azure
# and build URLs with https:// when appropriate.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
templates = Jinja2Templates(directory="templates")

@app.get("/job-card-tracking", response_class=HTMLResponse)
async def job_card_tracking(request: Request, db: Session = Depends(get_db)):
    """Serves the Job Card Tracking page."""
    job_cards = db.query(JobCard).options(
        joinedload(JobCard.project), 
        selectinload(JobCard.tasks)
    ).order_by(JobCard.id.desc()).all()

    context = {
        "request": request,
        "page_title": "Job Card Tracking",
        "job_cards": job_cards,
        "task_statuses": app_config['task_statuses']
    }
    return templates.TemplateResponse("job_card_tracking.html", context)

@app.post("/api/tasks/{task_id}/update-status", response_class=JSONResponse)
async def update_task_status(task_id: int, db: Session = Depends(get_db), status: str = Form(...)):
    # Step 1: Find the specific task and its parent job card
    task = db.query(Task).filter(Task.id == task_id).options(joinedload(Task.job_card)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Step 2: Update the task's status and save the change
    task.status = status
    db.commit()

    # Step 3: After saving, perform a fresh check on the parent job card's tasks
    job_card = task.job_card
    
    # This is the corrected logic:
    # Count how many of the job card's tasks are NOT "Done" by querying the database directly.
    pending_or_processing_tasks_count = db.query(Task).filter(
        Task.job_card_id == job_card.id,
        Task.status != 'Done'
    ).count()

    job_card_status_changed = False
    # If the count of unfinished tasks is zero, all tasks must be done.
    if pending_or_processing_tasks_count == 0:
        if job_card.status != 'Done':
            job_card.status = 'Done'
            job_card_status_changed = True
    else:
        # If any task is not Done, ensure the job card is marked as Pending.
        if job_card.status == 'Done':
            job_card.status = 'Pending'
            job_card_status_changed = True
    
    if job_card_status_changed:
        db.commit()
        db.refresh(job_card) # Refresh to get the latest state

    return {
        "message": f"Task {task_id} status updated to {status}",
        "job_card_id": job_card.id,
        "job_card_status": job_card.status if job_card_status_changed else None
    }

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("\n--- DETAILED VALIDATION ERROR ---")
    print(json.dumps(exc.errors(), indent=4))
    print("--- END OF ERROR ---")
    # You can customize the user-facing message if you want
    error_messages = "; ".join([f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()])
    return JSONResponse(status_code=422, content={"message": f"Invalid form data. Please check the fields. Details: {error_messages}"})

# --- Azure & OpenAI Client Setup ---
AZURE_STORAGE_CONNECTION_STRING = settings.AZURE_STORAGE_CONNECTION_STRING
if not AZURE_STORAGE_CONNECTION_STRING:
    print("CRITICAL WARNING: AZURE_STORAGE_CONNECTION_STRING is not set. Video/Image uploads will fail.")
if settings.OPENAI_API_KEY:
    openai.api_key = settings.OPENAI_API_KEY
else:
    print("CRITICAL WARNING: OPENAI_API_KEY is not set. Transcription/summary will fail.")

class MyAuthBackend(AuthenticationBackend):
    async def login(self, request: Request) -> bool: return True
    async def logout(self, request: Request) -> bool: return True
    async def authenticate(self, request: Request) -> bool: return True

authentication_backend = MyAuthBackend(secret_key="your_secret_key")
admin = Admin(app, engine, authentication_backend=authentication_backend)

# --- Admin Panel Views ---
# ... (All admin views are unchanged)
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
    column_list = [MaterialRequisition.id, MaterialRequisition.mr_number, MaterialRequisition.request_date, "project", "status"]
    column_formatters = {"project": lambda m, a: m.project.name if m.project else ""}
    name_plural = "Material Requisitions"
class SupplierAdmin(ModelView, model=Supplier):
    column_list = [Supplier.id, Supplier.name, Supplier.email, Supplier.phone]
    name_plural = "Suppliers"
class ProjectAdmin(ModelView, model=Project):
    column_list = [Project.id, Project.name]
    column_details_list = [Project.id, Project.name, Project.job_cards, Project.site_officer_reports, Project.material_requisitions]
class SupervisorAdmin(ModelView, model=Supervisor):
    column_list = [Supervisor.id, Supervisor.name]
    column_details_list = [Supervisor.id, Supervisor.name, Supervisor.job_cards, Supervisor.site_officer_reports, Supervisor.material_requisitions]
class ForemanAdmin(ModelView, model=Foreman):
    column_list = [Foreman.id, Foreman.name]
    column_details_list = [Foreman.id, Foreman.name, Foreman.job_cards, Foreman.progress_reports, Foreman.site_officer_reports]
class SiteEngineerAdmin(ModelView, model=SiteEngineer):
    column_list = [SiteEngineer.id, SiteEngineer.name]
    column_details_list = [SiteEngineer.id, SiteEngineer.name, SiteEngineer.job_cards]

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
# --- End of Admin Panel ---

with open("config.yaml", "r") as f: app_config = yaml.safe_load(f)

def generate_job_card_number(db: Session, site_location: str) -> str:
    today, date_str = date.today(), date.today().strftime("%Y%m%d")
    site_code = site_location[:3].upper() if site_location else "XXX"
    last_job_card = db.query(JobCard).filter(JobCard.job_card_no.like(f"{site_code}-{date_str}-%")).order_by(JobCard.job_card_no.desc()).first()
    new_seq = int(last_job_card.job_card_no.split("-")[-1]) + 1 if last_job_card else 1
    return f"{site_code}-{date_str}-{new_seq:03d}"

def process_video_and_update_db(video_id: int, file_contents: bytes):
    # ... (This function is unchanged)
    db = next(get_db())
    video_record = db.query(ToolboxVideo).filter(ToolboxVideo.id == video_id).first()
    if not video_record: 
        db.close()
        return
    temp_file_path = None
    try:
        video_record.processing_status = 'processing'
        db.commit()
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container_name = "toolbox-videos"
        try:
            container_client = blob_service_client.get_container_client(container_name)
            if not container_client.exists(): container_client.create_container()
        except Exception as e:
            print(f"Could not create or get container: {e}")
            raise
        blob_name = f"{uuid.uuid4()}.webm"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.upload_blob(file_contents, overwrite=True)
        video_record.blob_url = blob_client.url
        transcript_text = ""
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
            temp_file.write(file_contents)
            temp_file_path = temp_file.name
        with open(temp_file_path, "rb") as audio_file:
            transcription = openai.audio.transcriptions.create(model="whisper-1", file=audio_file)
            transcript_text = transcription.text
        video_record.transcript = transcript_text
        if transcript_text:
            completion = openai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": "You are a helpful assistant. Summarize the following toolbox talk transcript into a few key bullet points."}, {"role": "user", "content": transcript_text}])
            video_record.summary = completion.choices[0].message.content
        video_record.processing_status = 'completed'
    except Exception as e:
        video_record.processing_status = 'failed'
        print(f"Error processing video {video_id}: {e}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path): os.remove(temp_file_path)
        db.commit()
        db.close()

# --- Main Page Endpoints ---
# ... (All GET endpoints are unchanged)
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request): return templates.TemplateResponse("dashboard.html", {"request": request, "page_title": "Dashboard"})
@app.get("/job-card-form", response_class=HTMLResponse)
async def read_job_card_form(request: Request, db: Session = Depends(get_db)):
    context = {"request": request, "page_title": "Metamorphic • Job Card (Assignment)", "projects": db.query(Project).order_by(Project.name).all(), "site_engineers": db.query(SiteEngineer).order_by(SiteEngineer.name).all(), "supervisors": db.query(Supervisor).order_by(Supervisor.name).all(), "foremen": db.query(Foreman).order_by(Foreman.name).all(), "site_locations": app_config['site_locations'], "units": app_config['units'], "assigned_crew_options": app_config['assigned_crew_options'], "initial_job_card_no": generate_job_card_number(db, app_config['site_locations'][0])}
    return templates.TemplateResponse("form_a.html", context)
@app.get("/duty-officer-form", response_class=HTMLResponse)
async def read_duty_officer_form(request: Request, db: Session = Depends(get_db)):
    context = {"request": request, "page_title": "Metamorphic • Duty Officer Progress", "job_cards": db.query(JobCard).options(joinedload(JobCard.project)).order_by(JobCard.id.desc()).all(), "foremen": db.query(Foreman).order_by(Foreman.name).all(), "equipment_conditions": app_config['equipment_conditions'], "sub_contractor_coordinations": app_config['sub_contractor_coordinations'], "delivery_statuses": app_config['delivery_statuses'], "sop_statuses": app_config['sop_statuses'],}
    return templates.TemplateResponse("form_b.html", context)
@app.get("/site-officer-form", response_class=HTMLResponse)
async def read_site_officer_form(request: Request, db: Session = Depends(get_db)):
    context = {"request": request, "page_title": "Metamorphic • Sites Officers Daily Progress Report", "site_locations": app_config['site_locations'], "supervisors": db.query(Supervisor).order_by(Supervisor.name).all(), "foremen": db.query(Foreman).order_by(Foreman.name).all(), "job_cards": db.query(JobCard).options(joinedload(JobCard.project)).order_by(JobCard.id.desc()).all(), "projects": db.query(Project).order_by(Project.name).all(), "subcontractor_coordination_c": app_config['subcontractor_coordination_c'], "site_condition_options": app_config['site_condition_options'], "overall_site_health_options": app_config['overall_site_health_options'], "yes_no_help_options": app_config['yes_no_help_options'],}
    return templates.TemplateResponse("form_c.html", context)
@app.get("/material-requisition-form", response_class=HTMLResponse)
async def read_material_requisition_form(request: Request, db: Session = Depends(get_db)):
    context = {"request": request, "page_title": "Material Requisition Form", "projects": db.query(Project).order_by(Project.name).all(), "supervisors": db.query(Supervisor).order_by(Supervisor.name).all(), "material_types": app_config['material_types'], "urgency_levels": app_config['urgency_levels'],}
    return templates.TemplateResponse("material_requisition_form.html", context)
@app.get("/procurement/material-requisitions", response_class=HTMLResponse)
async def list_material_requisitions(request: Request, db: Session = Depends(get_db)):
    requisitions = db.query(MaterialRequisition).filter(MaterialRequisition.status == 'Pending').options(joinedload(MaterialRequisition.project), joinedload(MaterialRequisition.requested_by)).order_by(MaterialRequisition.request_date).all()
    return templates.TemplateResponse("procurement_list.html", {"request": request, "page_title": "Procurement Dashboard", "requisitions": requisitions})
@app.get("/procurement/material-requisition/{req_id}", response_class=HTMLResponse)
async def process_material_requisition_form(req_id: int, request: Request, db: Session = Depends(get_db)):
    req = db.query(MaterialRequisition).options(joinedload(MaterialRequisition.project), joinedload(MaterialRequisition.requested_by)).filter(MaterialRequisition.id == req_id).first()
    if not req: raise HTTPException(status_code=404, detail="Requisition not found")
    context = {"request": request, "page_title": f"Process Requisition #{req.id}", "req": req, "suppliers": db.query(Supplier).order_by(Supplier.name).all(), "approval_statuses": app_config['approval_statuses'], "requisition_statuses": app_config['requisition_statuses'],}
    return templates.TemplateResponse("procurement_update.html", context)

# --- API Endpoints ---
@app.post("/duty-officer-progress/", response_class=JSONResponse)
async def create_duty_officer_progress(db: Session = Depends(get_db), 
    # CORRECTED: Changed type hint from Optional[int] to Optional[str]
    toolbox_video_id: Optional[str] = Form(None), 
    site_image_ids: Optional[str] = Form(None), 
    job_card_id: int = Form(...), task_id: int = Form(...), date_of_work: date = Form(...), actual_output: str = Form(...), issues_delays: str = Form(...), tbt_attendance: str = Form(...), tbt_key_points: str = Form(...), sm_equipment_inventory: str = Form(...), sm_safety_hazards: str = Form(...), sm_foreman_signature_id: int = Form(...), mm_deliveries_received: str = Form(...), mm_stock_balance: str = Form(...), tbt_topic_discussed: Optional[str] = Form(None), sm_equipment_condition: Optional[str] = Form(None), sm_equipment_transfer: Optional[str] = Form(None), sm_remarks: Optional[str] = Form(None), sm_sub_contractor_coordination: Optional[str] = Form(None), sm_coordination_issues: Optional[str] = Form(None), sm_ppe_check: bool = Form(False), sm_photos_on_whatsapp: bool = Form(False), mm_rejection_reason: Optional[str] = Form(None), mm_material_transfers: Optional[str] = Form(None), kt_sops_explained: Optional[str] = Form(None), kt_help_required_details: Optional[str] = Form(None), kt_critical_actions_required: Optional[str] = Form(None)
):
    try:
        progress_report = DutyOfficerProgress(job_card_id=job_card_id, task_id=task_id, date_of_work=date_of_work, actual_output=actual_output, issues_delays=issues_delays, tbt_attendance=tbt_attendance, tbt_topic_discussed=tbt_topic_discussed, tbt_key_points=tbt_key_points, sm_equipment_inventory=sm_equipment_inventory, sm_equipment_condition=sm_equipment_condition, sm_equipment_transfer=sm_equipment_transfer, sm_remarks=sm_remarks, sm_sub_contractor_coordination=sm_sub_contractor_coordination, sm_coordination_issues=sm_coordination_issues, sm_ppe_check=sm_ppe_check, sm_safety_hazards=sm_safety_hazards, sm_photos_on_whatsapp=sm_photos_on_whatsapp, sm_foreman_signature_id=sm_foreman_signature_id, mm_deliveries_received=mm_deliveries_received, mm_rejection_reason=mm_rejection_reason, mm_stock_balance=mm_stock_balance, mm_material_transfers=mm_material_transfers, kt_sops_explained=kt_sops_explained, kt_help_required_details=kt_help_required_details, kt_critical_actions_required=kt_critical_actions_required)
        db.add(progress_report)
        db.flush()
        
        # CORRECTED: Convert to int only if the string contains digits
        video_id = int(toolbox_video_id) if toolbox_video_id and toolbox_video_id.isdigit() else None
        if video_id:
            video = db.query(ToolboxVideo).filter(ToolboxVideo.id == video_id).first()
            if video: video.duty_officer_progress_id = progress_report.id
        
        if site_image_ids:
            image_id_list = [int(id_str) for id_str in site_image_ids.split(',') if id_str.isdigit()]
            db.query(SiteImage).filter(SiteImage.id.in_(image_id_list)).update({"duty_officer_progress_id": progress_report.id}, synchronize_session=False)
        
        db.commit()
        return JSONResponse(status_code=200, content={"message": "Progress report submitted successfully!"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An unexpected error occurred: {e}"})

@app.post("/site-officer-reports/", response_class=JSONResponse)
async def create_site_officer_report(db: Session = Depends(get_db), 
    # CORRECTED: Changed type hint from Optional[int] to Optional[str]
    toolbox_video_id: Optional[str] = Form(None), 
    site_image_ids: Optional[str] = Form(None), 
    date: date = Form(...), site_location: str = Form(...), site_officer_id: int = Form(...), duty_officer_id: int = Form(...), tbt_attendance: Optional[str] = Form(None), tbt_topic_discussed: Optional[str] = Form(None), tbt_key_points: Optional[str] = Form(None), job_card_id: int = Form(...), form_b_completed_check: bool = Form(False), dependency_notes: Optional[str] = Form(None), progress_pictures_check: bool = Form(False), sm_manpower_availability: Optional[str] = Form(None), sm_subcontractor_coordination: Optional[str] = Form(None), sm_coordination_issues: Optional[str] = Form(None), sm_other_notes: Optional[str] = Form(None), material_requisition_project_id: Optional[int] = Form(None), commercial_delivery_check: bool = Form(False), delivery_comments: Optional[str] = Form(None), qc_steps_explained: bool = Form(False), qc_steps_details: Optional[str] = Form(None), qc_drawing_mismatches: Optional[str] = Form(None), re_delays_flagged_reason: Optional[str] = Form(None), re_support_needed: Optional[str] = Form(None), hs_waste_management: Optional[str] = Form(None), hs_waste_management_comments: Optional[str] = Form(None), hs_walkways_clear: Optional[str] = Form(None), hs_material_storage: Optional[str] = Form(None), hs_ppe_compliance: bool = Form(False), hs_incidents_near_misses: Optional[str] = Form(None), hs_safety_comments: Optional[str] = Form(None), sa_overall_site_health: Optional[str] = Form(None), sa_immediate_actions: Optional[str] = Form(None), sa_responsible_person: Optional[str] = Form(None), sa_action_deadline: Optional[date] = Form(None), sa_critical_actions: Optional[str] = Form(None), sa_approved_drawings_check: Optional[str] = Form(None), sa_drawing_help_details: Optional[str] = Form(None)
):
    try:
        report = SiteOfficerReport(date=date, site_location=site_location, site_officer_id=site_officer_id, duty_officer_id=duty_officer_id, tbt_attendance=tbt_attendance, tbt_topic_discussed=tbt_topic_discussed, tbt_key_points=tbt_key_points, job_card_id=job_card_id, form_b_completed_check=form_b_completed_check, dependency_notes=dependency_notes, progress_pictures_check=progress_pictures_check, sm_manpower_availability=sm_manpower_availability, sm_subcontractor_coordination=sm_subcontractor_coordination, sm_coordination_issues=sm_coordination_issues, sm_other_notes=sm_other_notes, material_requisition_project_id=material_requisition_project_id, commercial_delivery_check=commercial_delivery_check, delivery_comments=delivery_comments, qc_steps_explained=qc_steps_explained, qc_steps_details=qc_steps_details, qc_drawing_mismatches=qc_drawing_mismatches, re_delays_flagged_reason=re_delays_flagged_reason, re_support_needed=re_support_needed, hs_waste_management=hs_waste_management, hs_waste_management_comments=hs_waste_management_comments, hs_walkways_clear=hs_walkways_clear, hs_material_storage=hs_material_storage, hs_ppe_compliance=hs_ppe_compliance, hs_incidents_near_misses=hs_incidents_near_misses, hs_safety_comments=hs_safety_comments, sa_overall_site_health=sa_overall_site_health, sa_immediate_actions=sa_immediate_actions, sa_responsible_person=sa_responsible_person, sa_action_deadline=sa_action_deadline, sa_critical_actions=sa_critical_actions, sa_approved_drawings_check=sa_approved_drawings_check, sa_drawing_help_details=sa_drawing_help_details)
        db.add(report)
        db.flush()
        
        # CORRECTED: Convert to int only if the string contains digits
        video_id = int(toolbox_video_id) if toolbox_video_id and toolbox_video_id.isdigit() else None
        if video_id:
            video = db.query(ToolboxVideo).filter(ToolboxVideo.id == video_id).first()
            if video: video.site_officer_report_id = report.id
        
        if site_image_ids:
            image_id_list = [int(id_str) for id_str in site_image_ids.split(',') if id_str.isdigit()]
            db.query(SiteImage).filter(SiteImage.id.in_(image_id_list)).update({"site_officer_report_id": report.id}, synchronize_session=False)
        
        db.commit()
        return JSONResponse(status_code=200, content={"message": "Site Officer daily report submitted successfully!"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An unexpected error occurred: {e}"})

@app.post("/api/images/upload", response_class=JSONResponse)
async def upload_images(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    if not AZURE_STORAGE_CONNECTION_STRING:
        raise HTTPException(status_code=500, detail="Azure Storage not configured on the server.")
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container_name = "site-images"
    try:
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not access storage container: {e}")
    image_ids = []
    for file in files:
        try:
            file_contents = await file.read()
            safe_filename = "".join(c for c in file.filename if c.isalnum() or c in ('.', '_')).rstrip()
            blob_name = f"{uuid.uuid4()}-{safe_filename}"
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            blob_client.upload_blob(file_contents, overwrite=True)
            new_image = SiteImage(blob_url=blob_client.url, file_name=file.filename)
            db.add(new_image)
            db.commit()
            db.refresh(new_image)
            image_ids.append(new_image.id)
        except Exception as e:
            db.rollback()
            return JSONResponse(status_code=500, content={"message": f"Failed to upload {file.filename}: {e}"})
    return {"message": "Images uploaded successfully", "image_ids": image_ids}

# ... (rest of API endpoints are unchanged)
@app.post("/job-cards/", response_class=JSONResponse)
async def create_job_card(db: Session = Depends(get_db), project_id: int = Form(...), job_card_no: str = Form(...), date_issued: date = Form(...), site_location: str = Form(...), site_engineer_id: int = Form(...), supervisor_id: int = Form(...), foreman_id: int = Form(...), task_details: List[str] = Form(...), quantity: List[Optional[str]] = Form(...), units: List[Optional[str]] = Form(...), priority: List[Optional[int]] = Form(...), start_date: List[Optional[date]] = Form(...), end_date: List[Optional[date]] = Form(...), assigned_crew: List[Optional[str]] = Form(...)):
    if db.query(JobCard).filter(JobCard.job_card_no == job_card_no).first(): return JSONResponse(status_code=400, content={"message": f"Job Card No '{job_card_no}' already exists."})
    try:
        new_job_card = JobCard(project_id=project_id, job_card_no=job_card_no, date_issued=date_issued, site_location=site_location, site_engineer_id=site_engineer_id, supervisor_id=supervisor_id, foreman_id=foreman_id)
        db.add(new_job_card)
        db.flush() 
        for i in range(len(task_details)):
            if not task_details[i].strip(): continue
            new_task = Task(job_card_id=new_job_card.id, task_details=task_details[i], quantity=float(quantity[i]) if quantity[i] and quantity[i].strip() else None, units=units[i], priority=priority[i] if priority[i] else 3, start_date=start_date[i], end_date=end_date[i], assigned_crew=assigned_crew[i])
            db.add(new_task)
        db.commit()
        return JSONResponse(status_code=200, content={"message": "Job Card created successfully!", "next_job_card_no": generate_job_card_number(db, site_location)})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An error occurred: {e}"})
@app.post("/material-requisitions/", response_class=JSONResponse)
async def create_material_requisition(db: Session = Depends(get_db), request_date: date = Form(...), project_id: int = Form(...), requested_by_id: int = Form(...), material_type: str = Form(...), material_with_quantity: str = Form(...), urgency: str = Form(...), required_delivery_date: date = Form(...)):
    try:
        requisition = MaterialRequisition(request_date=request_date, project_id=project_id, requested_by_id=requested_by_id, material_type=material_type, material_with_quantity=material_with_quantity, urgency=urgency, required_delivery_date=required_delivery_date)
        db.add(requisition)
        db.commit()
        return JSONResponse(status_code=200, content={"message": "Material requisition submitted successfully!"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An unexpected error occurred: {e}"})
@app.post("/api/material-requisitions/{req_id}", response_class=JSONResponse)
async def update_material_requisition(req_id: int, db: Session = Depends(get_db), supplier_id: int = Form(...), status: str = Form(...), lpo_number: Optional[str] = Form(None), pm_approval: Optional[str] = Form(None), qs_approval: Optional[str] = Form(None), payment_status: Optional[str] = Form(None), remarks: Optional[str] = Form(None)):
    req = db.query(MaterialRequisition).filter(MaterialRequisition.id == req_id).first()
    if not req: raise HTTPException(status_code=404, detail="Requisition not found")
    try:
        if not req.mr_number:
            last_mr = db.query(func.max(MaterialRequisition.mr_number)).scalar()
            next_mr_num = 56 if not last_mr else int(last_mr.split('-')[1]) + 1
            req.mr_number = f"MR-{next_mr_num:06d}"
        req.supplier_id = supplier_id
        req.lpo_number = lpo_number
        req.pm_approval = pm_approval
        req.qs_approval = qs_approval
        req.payment_status = payment_status
        req.remarks = remarks
        req.status = status
        db.commit()
        return JSONResponse(status_code=200, content={"message": f"Requisition {req.mr_number} updated successfully!"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An unexpected error occurred: {e}"})
@app.post("/api/videos/upload", response_class=JSONResponse)
async def upload_video(background_tasks: BackgroundTasks, db: Session = Depends(get_db), video: UploadFile = File(...)):
    if not AZURE_STORAGE_CONNECTION_STRING:
        raise HTTPException(status_code=500, detail="Azure Storage not configured on the server.")
    file_contents = await video.read()
    new_video_record = ToolboxVideo()
    db.add(new_video_record)
    db.commit()
    db.refresh(new_video_record)
    background_tasks.add_task(process_video_and_update_db, new_video_record.id, file_contents)
    return {"message": "Video upload started. Processing in the background.", "video_id": new_video_record.id}
@app.get("/api/generate-job-card-no")
async def get_new_job_card_no(site_location: str, db: Session = Depends(get_db)):
    if not site_location: raise HTTPException(status_code=400, detail="Site location is required.")
    return {"job_card_no": generate_job_card_number(db, site_location)}
@app.get("/api/job-cards/{job_card_id}/tasks", response_class=JSONResponse)
async def get_job_card_tasks(job_card_id: int, db: Session = Depends(get_db)):
    tasks = db.query(Task).filter(Task.job_card_id == job_card_id).all()
    if not tasks: raise HTTPException(status_code=404, detail="No tasks found for this Job Card.")
    return [{"id": task.id, "task_details": task.task_details} for task in tasks]

