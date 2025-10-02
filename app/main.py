# app/main.py
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqladmin import Admin

from app.core.database import engine
from app.core.config import settings
from app.admin import MyAuthBackend, create_admin_views

# Import all the routers
from app.api.endpoints import pages, job_cards, reports, procurement, uploads, users, approvals, nanny_log, requisition_details, material_receipts, duty_officer_reports, site_officer_reports, job_card_details, notifications,materials as materials_router 
from app.auth.router import router as auth_router
from app.api.endpoints.suppliers import router as suppliers_router



from app.api.endpoints.design.design_projects import router as design_router
from app.api.endpoints.design.tasks import router as design_tasks_router
from app.api.endpoints.design.dashboard import router as design_dashboard_router
from app.api.endpoints.design.phases import router as design_phases_router


from app.api.endpoints.lpo.lpo import router as lpo_router




app = FastAPI(title="Metamorphic Job Card App V2")

# --- Setup Admin Panel ---
# Note: Ensure SECRET_KEY is set in your .env file for session management
authentication_backend = MyAuthBackend(secret_key=settings.SECRET_KEY)
#admin = Admin(app, engine, authentication_backend=authentication_backend)
admin = Admin(app, engine, authentication_backend=authentication_backend, templates_dir="templates/admin")
create_admin_views(admin)
# -------------------------

# --- Exception Handler and Middleware (from your old main.py) ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("\n--- DETAILED VALIDATION ERROR ---")
    print(json.dumps(exc.errors(), indent=4))
    print("--- END OF ERROR ---")
    error_messages = "; ".join([f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()])
    return JSONResponse(
        status_code=422,
        content={"message": f"Invalid form data. Please check the fields. Details: {error_messages}"}
    )

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "upgrade-insecure-requests"
    return response
# -----------------------------------------------------------------

# --- Include all API Routers ---
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(pages.router, tags=["Pages"]) # Root-level pages
app.include_router(job_cards.router, prefix="/job-cards", tags=["Job Cards"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(procurement.router, prefix="/procurement", tags=["Procurement"])
app.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["Approvals"])
app.include_router(nanny_log.router, prefix="/nanny-log", tags=["Nanny Log"])
app.include_router(requisition_details.router, prefix="/api/requisition-details", tags=["Requisition Details"])
app.include_router(material_receipts.router, prefix="/api/material-receipts", tags=["Material Receipts"])
app.include_router(duty_officer_reports.router, prefix="/api/duty-officer-reports", tags=["Duty Officer Reports"])
app.include_router(site_officer_reports.router, prefix="/api/site-officer-reports", tags=["Site Officer Reports"])
app.include_router(job_card_details.router, prefix="/api/job-card-details", tags=["Job Card Details"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(materials_router.router, prefix="/api/materials", tags=["Materials"])
app.include_router(suppliers_router, prefix="/api/suppliers", tags=["Suppliers"])
# -------------------------------

app.include_router(lpo_router, prefix="/api/lpos", tags=["LPO"])

app.include_router(design_router, prefix="/api/design", tags=["Design"])
app.include_router(design_tasks_router, prefix="/api/design/tasks", tags=["My Tasks"])
app.include_router(design_dashboard_router, prefix="/api/design/dashboard", tags=["Design Dashboard"])
app.include_router(design_phases_router, prefix="/api/design/phases", tags=["Design Phases"])


@app.get("/health", tags=["System"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}