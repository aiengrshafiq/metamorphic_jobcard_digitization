# app/api/endpoints/pages.py
from fastapi import APIRouter, Depends, Request # <--- MAKE SURE 'Request' IS IMPORTED
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload, selectinload
from app.api.endpoints.lpo.lpo import get_next_lpo_number
import yaml
from pathlib import Path
import os
from sqlalchemy import or_

from app.api import deps
from app import models
from app import design_models
from app.design_models import DesignTaskStatus
from app.utils import generate_job_card_number

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- Safe Configuration Loading ---
def _load_config() -> dict:
    path = Path(os.getenv("APP_CONFIG_PATH", "config.yaml"))
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Warning: Config file at {path} not found.")
        return {}
app_config = _load_config()
# --- End Config Loading ---

# --- Protected Page Routes (Using the new dependency) ---

@router.get("/", response_class=HTMLResponse, tags=["Pages"])
async def dashboard(context: dict = Depends(deps.get_template_context),db: Session = Depends(deps.get_db)):
    if isinstance(context, RedirectResponse):
        return context
    
    context["page_title"] = "Dashboard"
    # --- NEW LOGIC TO FETCH PENDING JOB CARDS ---
    current_user = context["user"]
    user_roles = context["user_roles"]
    
    # Define roles that need to see their pending job cards
    field_roles = {'Supervisor/Site Officer', 'Foreman/Duty Officer'}
    
    # Check if the user has one of the field roles
    if any(role in user_roles for role in field_roles):
        # Query for job cards that are 'Pending' and assigned to this user
        pending_job_cards = db.query(models.JobCard).filter(
            models.JobCard.status == 'Pending',
            or_(
                models.JobCard.supervisor_user_id == current_user.id,
                models.JobCard.foreman_user_id == current_user.id
            )
        ).options(
            joinedload(models.JobCard.project) # Load project info efficiently
        ).order_by(models.JobCard.date_issued.desc()).all()
        
        # Add the list to the context
        context["pending_job_cards"] = pending_job_cards
    # ----------------------------------------------
     # --- NEW: DESIGN TEAM MEMBER PERFORMANCE STATS LOGIC ---
    design_team_roles = {'Design Team Member', 'Technical Engineer', 'Document Controller'}
    if any(role in user_roles for role in design_team_roles):
        # Find all completed tasks with scores for this user
        scored_tasks = db.query(design_models.DesignTask).join(
            design_models.DesignScore
        ).filter(
            design_models.DesignTask.owner_id == current_user.id,
            design_models.DesignTask.status.in_([
                DesignTaskStatus.SUBMITTED, DesignTaskStatus.VERIFIED, DesignTaskStatus.DONE
            ])
        ).all()

        if scored_tasks:
            total_tasks = len(scored_tasks)
            on_time_tasks = sum(1 for task in scored_tasks if task.score.lateness_days == 0)
            total_score = sum(task.score.score for task in scored_tasks)
            
            context["on_time_rate"] = round((on_time_tasks / total_tasks) * 100)
            context["avg_score"] = round(total_score / total_tasks)
        else:
            context["on_time_rate"] = 100
            context["avg_score"] = 100
    # ----------------------------------------------------
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/job-card-form", response_class=HTMLResponse, tags=["Pages"])
async def read_job_card_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context

    # --- MODIFIED QUERIES ---
    # Fetch USERS with the role 'Site Engineer' instead of the old SiteEngineer table
    site_engineers = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.SITE_ENGINEER).all()
    supervisors = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.SUPERVISOR).all()
    foremen = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.FOREMAN).all()
    # ------------------------

    context.update({
        "page_title": "Metamorphic • Job Card (Assignment)",
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
        "site_engineers": site_engineers,
        "supervisors": supervisors,
        "foremen": foremen,
        "site_locations": app_config.get('site_locations', []),
        "units": app_config.get('units', []),
        "assigned_crew_options": app_config.get('assigned_crew_options', []),
        "initial_job_card_no": generate_job_card_number(db, app_config.get('site_locations', [''])[0])
    })
    return templates.TemplateResponse("form_a.html", context)


@router.get("/duty-officer-form", response_class=HTMLResponse, tags=["Pages"])
async def read_duty_officer_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
        
    # --- V3 DATA FILTERING LOGIC ---
    # Base query for Job Cards
    job_cards_query = db.query(models.JobCard).options(joinedload(models.JobCard.project))

    # Check if the user is privileged (can see everything)
    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    is_privileged = bool(privileged_roles.intersection(context["user_roles"]))

    # If the user is NOT privileged, filter the job cards query
    if not is_privileged:
        current_user_id = context["user"].id
        job_cards_query = job_cards_query.filter(
            # A foreman should only see job cards they are assigned to
            models.JobCard.foreman_user_id == current_user_id
        )
    
    # Execute the final query
    job_cards = job_cards_query.order_by(models.JobCard.id.desc()).all()

    # Fetch USERS with the role 'Foreman/Duty Officer' for the signature dropdown
    foremen = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.FOREMAN).all()
    # ------------------------------------

    context.update({
        "page_title": "Metamorphic • Duty Officer Progress",
        "job_cards": job_cards, # Pass the potentially filtered list
        "foremen": foremen,     # Pass the list of users
        "equipment_conditions": app_config.get('equipment_conditions', []),
        "sub_contractor_coordinations": app_config.get('sub_contractor_coordinations', []),
        "delivery_statuses": app_config.get('delivery_statuses', []),
        "sop_statuses": app_config.get('sop_statuses', []),
    })
    return templates.TemplateResponse("form_b.html", context)


@router.get("/site-officer-form", response_class=HTMLResponse, tags=["Pages"])
async def read_site_officer_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
        
    # --- V3 DATA FILTERING LOGIC ---
    job_cards_query = db.query(models.JobCard).options(joinedload(models.JobCard.project))

    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    is_privileged = bool(privileged_roles.intersection(context["user_roles"]))

    # If the user is NOT privileged, filter the job cards to only show their own
    if not is_privileged:
        current_user_id = context["user"].id
        job_cards_query = job_cards_query.filter(
            # A supervisor should only see job cards they are assigned to
            models.JobCard.supervisor_user_id == current_user_id
        )
    
    job_cards = job_cards_query.order_by(models.JobCard.id.desc()).all()

    # Fetch USERS for the dropdowns based on their roles
    supervisors = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.SUPERVISOR).all()
    foremen = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.FOREMAN).all()
    # ------------------------------------

    context.update({
        "page_title": "Metamorphic • Sites Officers Daily Progress Report",
        "site_locations": app_config.get('site_locations', []),
        "supervisors": supervisors, # Pass the list of supervisor users
        "foremen": foremen,         # Pass the list of foreman users
        "job_cards": job_cards,     # Pass the filtered list of job cards
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
        "subcontractor_coordination_c": app_config.get('subcontractor_coordination_c', []),
        "site_condition_options": app_config.get('site_condition_options', []),
        "overall_site_health_options": app_config.get('overall_site_health_options', []),
        "yes_no_help_options": app_config.get('yes_no_help_options', []),
    })
    return templates.TemplateResponse("form_c.html", context)


@router.get("/job-card-tracking", response_class=HTMLResponse, tags=["Pages"])
async def job_card_tracking(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
    
    # Base query
    
    query = db.query(models.JobCard).filter(
        models.JobCard.status.in_(['Pending', 'Processing'])
    ).options(
        joinedload(models.JobCard.project), 
        selectinload(models.JobCard.tasks)
    )

    # Check if the user is privileged (can see everything)
    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    is_privileged = bool(privileged_roles.intersection(context["user_roles"]))

    # If the user is NOT privileged, filter the query
    if not is_privileged:
        current_user_id = context["user"].id
        query = query.filter(
            or_(
                models.JobCard.site_engineer_user_id == current_user_id,
                models.JobCard.supervisor_user_id == current_user_id,
                models.JobCard.foreman_user_id == current_user_id
            )
        )
    
    job_cards = query.order_by(models.JobCard.id.desc()).all()
    
    context.update({
        "page_title": "Pending Job Cards", # Renamed for clarity
        "job_cards": job_cards,
        "task_statuses": app_config.get('task_statuses', [])
    })
    return templates.TemplateResponse("job_card_tracking.html", context)


@router.get("/material-requisition-form", response_class=HTMLResponse, tags=["Pages"])
async def read_material_requisition_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
        
    all_materials = db.query(models.Material).order_by(models.Material.name).all()
    all_users = db.query(models.User).filter(models.User.is_active == True).order_by(models.User.name).all()
    #all_users = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.SUPERVISOR).all()

    context.update({
        "page_title": "Material Requisition Form",
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
        "supervisors": all_users,
        "material_types": app_config.get('material_types', []),
        "urgency_levels": app_config.get('urgency_levels', []),
        "materials": all_materials,
    })
    
    return templates.TemplateResponse("material_requisition_form.html", context)


@router.get("/approvals", response_class=HTMLResponse, tags=["Pages"])
async def approvals_page(context: dict = Depends(deps.get_template_context)):
    if isinstance(context, RedirectResponse):
        return context
        
    context["page_title"] = "My Approvals"
    return templates.TemplateResponse("approvals.html", context)


# --- Public Page Routes (No login required) ---

@router.get("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page(request: Request): # <--- CORRECTED: Was 'dict', now 'Request'
    """Serves the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse, tags=["Pages"])
async def register_page(request: Request, db: Session = Depends(deps.get_db)): # <--- CORRECTED: Was 'dict', now 'Request'
    """Serves the user registration page and provides a list of roles."""
    available_roles = db.query(models.Role).filter(models.Role.name != 'Super Admin').all()
    return templates.TemplateResponse(
        "register.html", 
        {"request": request, "roles": available_roles}
    )

@router.get("/nanny-log-form", response_class=HTMLResponse, tags=["Pages"])
async def nanny_log_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context

    # --- THIS IS THE CORRECTED QUERY ---
    # We add .join(models.User.roles) to link the User and Role tables before filtering.
    all_users = db.query(models.User).join(models.User.roles).filter(
        models.Role.name == models.UserRole.USER,
        models.User.is_active == True
    ).order_by(models.User.name).all()
    # ------------------------------------
        
    context.update({
        "page_title": "Daily Nanny Log",
        "nannies": all_users,
    })
    return templates.TemplateResponse("nanny_log.html", context)

    

@router.get("/requisition-details/{req_id}", response_class=HTMLResponse, tags=["Pages"])
async def requisition_details_page(
    req_id: int,
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
        
    context["page_title"] = f"Requisition Details #{req_id}"
    context["req_id"] = req_id # Pass the ID to the template
    return templates.TemplateResponse("requisition_details.html", context)


@router.get("/receive-mr-form", response_class=HTMLResponse, tags=["Pages"])
async def receive_mr_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
        
    context.update({
        "page_title": "Receive Material Requisition",
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
    })
    return templates.TemplateResponse("receive_mr.html", context)


@router.get("/duty-officer-reports", response_class=HTMLResponse, tags=["Pages"])
async def duty_officer_reports_list_page(
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
    
    context["page_title"] = "View Progress Reports"
    return templates.TemplateResponse("duty_officer_progress_list.html", context)


@router.get("/duty-officer-reports/{report_id}", response_class=HTMLResponse, tags=["Pages"])
async def duty_officer_report_detail_page(
    report_id: int,
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
        
    context["page_title"] = f"Progress Report #{report_id}"
    context["report_id"] = report_id # Pass the ID to the template
    return templates.TemplateResponse("duty_officer_progress_detail.html", context)


@router.get("/site-officer-reports", response_class=HTMLResponse, tags=["Pages"])
async def site_officer_reports_list_page(
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
    
    context["page_title"] = "View Daily Reports"
    return templates.TemplateResponse("site_officer_report_list.html", context)


@router.get("/site-officer-reports/{report_id}", response_class=HTMLResponse, tags=["Pages"])
async def site_officer_report_detail_page(
    report_id: int,
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
        
    context["page_title"] = f"Daily Report #{report_id}"
    context["report_id"] = report_id
    return templates.TemplateResponse("site_officer_report_detail.html", context)


@router.get("/job-card-details/{jc_id}", response_class=HTMLResponse, tags=["Pages"])
async def job_card_detail_page(
    jc_id: int,
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
        
    context["page_title"] = f"Job Card Details #{jc_id}"
    context["jc_id"] = jc_id
    return templates.TemplateResponse("job_card_detail.html", context)


@router.get("/lpos", response_class=HTMLResponse, tags=["Pages"])
async def list_lpo_page(context: dict = Depends(deps.get_template_context)):
    if isinstance(context, RedirectResponse): return context
    context["page_title"] = "Purchase Orders"
    return templates.TemplateResponse("lpo/list_lpo.html", context)

@router.get("/lpos/new", response_class=HTMLResponse, tags=["Pages"])
async def create_lpo_page(context: dict = Depends(deps.get_template_context), db: Session = Depends(deps.get_db)):
    if isinstance(context, RedirectResponse): return context
    context["page_title"] = "Create Purchase Order"
    context["next_lpo_number"] = get_next_lpo_number(db) # We need to import this function
    context["suppliers"] = db.query(models.Supplier).order_by(models.Supplier.name).all()
    context["projects"] = db.query(models.Project).order_by(models.Project.name).all()
    context["materials"] = db.query(models.Material).order_by(models.Material.name).all()
    context["payment_modes"] = app_config.get('payment_modes', [])
    return templates.TemplateResponse("lpo/create_lpo.html", context)

@router.get("/lpos/{lpo_id}", response_class=HTMLResponse, tags=["Pages"])
async def view_lpo_page(lpo_id: int, context: dict = Depends(deps.get_template_context)):
    if isinstance(context, RedirectResponse): return context
    context["page_title"] = f"Purchase Order #{lpo_id}"
    context["lpo_id"] = lpo_id
    return templates.TemplateResponse("lpo/view_lpo.html", context)



# Start of Design Module Pages
@router.get("/design/projects/completed", response_class=HTMLResponse, tags=["Pages"])
async def completed_design_projects_page(
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
    
    context["page_title"] = "Completed Design Projects"
    return templates.TemplateResponse("design/completed_project_list.html", context)
    
@router.get("/design/projects/new", response_class=HTMLResponse, tags=["Pages"])
async def create_design_project_page(
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
    
    # This page is only for Design Managers
    if "Design Manager" not in context["user_roles"]:
        raise HTTPException(status_code=403, detail="You do not have permission to access this page.")
        
    context["page_title"] = "Create New Design Project"
    return templates.TemplateResponse("design/create_project.html", context)
    

@router.get("/design/my-tasks", response_class=HTMLResponse, tags=["Pages"])
async def my_tasks_page(
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
        
    context["page_title"] = "My Design Tasks"
    return templates.TemplateResponse("design/my_tasks.html", context)


@router.get("/design/projects", response_class=HTMLResponse, tags=["Pages"])
async def design_projects_list_page(
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
    context["page_title"] = "Design Projects"
    return templates.TemplateResponse("design/project_list.html", context)


@router.get("/design/projects/{project_id}", response_class=HTMLResponse, tags=["Pages"])
async def design_project_detail_page(
    project_id: int,
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
        
    context["page_title"] = f"Manage Design Project #{project_id}"
    context["project_id"] = project_id
    
    # Fetch all potential team members
    team_roles = [
        models.UserRole.DESIGN_TEAM_MEMBER,
        models.UserRole.TECH_ENGINEER,
        models.UserRole.DOC_CONTROLLER,
        models.UserRole.DESIGN_MANAGER
    ]
    #team_members_objects = db.query(models.User).join(models.User.roles).filter(models.Role.name.in_(team_roles)).all()

    team_members_objects = db.query(models.User).join(models.User.roles).filter(
        models.Role.name.in_(team_roles),
        models.User.is_active == True
    ).order_by(models.User.name).all()
    
    
    # --- THIS IS THE FIX ---
    # Convert the complex SQLAlchemy objects into a simple list of dictionaries
    team_members_data = [{"id": user.id, "name": user.name} for user in team_members_objects]
    # -----------------------

    # Pass the simple, JSON-serializable list to the template
    context["team_members"] = team_members_data
    
    return templates.TemplateResponse("design/project_detail.html", context)


@router.get("/design/dashboard", response_class=HTMLResponse, tags=["Pages"])
async def design_dashboard_page(
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
    
    # Simple check to ensure only relevant people see this
    allowed_roles = {'Design Manager', 'Admin', 'Super Admin'}
    if not allowed_roles.intersection(context["user_roles"]):
        raise HTTPException(status_code=403, detail="Access denied.")
        
    context["page_title"] = "Design Dashboard"
    return templates.TemplateResponse("design/dashboard.html", context)


@router.get("/job-cards/all", response_class=HTMLResponse, tags=["Pages"])
async def all_job_cards_page(
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
    
    context["page_title"] = "All Completed Job Cards"
    return templates.TemplateResponse("job_cards_all.html", context)


@router.get("/design/tasks/{task_id}", response_class=HTMLResponse, tags=["Pages"])
async def design_task_detail_page(
    task_id: int,
    context: dict = Depends(deps.get_template_context)
):
    if isinstance(context, RedirectResponse):
        return context
        
    context["page_title"] = f"Task Details #{task_id}"
    context["task_id"] = task_id
    return templates.TemplateResponse("design/task_detail.html", context)





