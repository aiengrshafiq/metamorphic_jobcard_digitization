# app/api/endpoints/reports.py
from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional,List
from datetime import date
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app import models

router = APIRouter()

@router.post("/duty-officer-progress/", response_class=JSONResponse, tags=["Reports"])
async def create_duty_officer_progress(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user), # Captures who is submitting
    toolbox_video_id: Optional[str] = Form(None),
    site_image_ids: Optional[str] = Form(None),
    job_card_id: int = Form(...),
    task_id: int = Form(...),
    date_of_work: date = Form(...),
    actual_output: str = Form(...),
    issues_delays: str = Form(...),
    tbt_attendance: str = Form(...),
    tbt_key_points: str = Form(...),
    sm_equipment_inventory: str = Form(...),
    sm_safety_hazards: str = Form(...),
    foreman_user_id: int = Form(...), # UPDATED: Was sm_foreman_signature_id
    mm_deliveries_received: str = Form(...),
    mm_stock_balance: str = Form(...),
    tbt_topic_discussed: Optional[str] = Form(None),
    sm_equipment_condition: Optional[str] = Form(None),
    sm_equipment_transfer: Optional[str] = Form(None),
    sm_remarks: Optional[str] = Form(None),
    sm_sub_contractor_coordination: Optional[str] = Form(None),
    sm_coordination_issues: Optional[str] = Form(None),
    sm_ppe_check: bool = Form(False),
    sm_photos_on_whatsapp: bool = Form(False),
    mm_rejection_reason: Optional[str] = Form(None),
    mm_material_transfers: Optional[str] = Form(None),
    kt_sops_explained: Optional[str] = Form(None),
    kt_help_required_details: Optional[str] = Form(None),
    kt_critical_actions_required: Optional[str] = Form(None)
):
    try:
        progress_report = models.DutyOfficerProgress(
            # --- V3 FIELD UPDATES ---
            created_by_id=current_user.id,
            foreman_user_id=foreman_user_id,
            sm_foreman_signature_id=1, # Placeholder for old required field
            # --------------------------
            job_card_id=job_card_id, task_id=task_id, date_of_work=date_of_work,
            actual_output=actual_output, issues_delays=issues_delays, tbt_attendance=tbt_attendance,
            tbt_topic_discussed=tbt_topic_discussed, tbt_key_points=tbt_key_points,
            sm_equipment_inventory=sm_equipment_inventory, sm_equipment_condition=sm_equipment_condition,
            sm_equipment_transfer=sm_equipment_transfer, sm_remarks=sm_remarks,
            sm_sub_contractor_coordination=sm_sub_contractor_coordination,
            sm_coordination_issues=sm_coordination_issues, sm_ppe_check=sm_ppe_check,
            sm_safety_hazards=sm_safety_hazards, sm_photos_on_whatsapp=sm_photos_on_whatsapp,
            mm_deliveries_received=mm_deliveries_received,
            mm_rejection_reason=mm_rejection_reason, mm_stock_balance=mm_stock_balance,
            mm_material_transfers=mm_material_transfers, kt_sops_explained=kt_sops_explained,
            kt_help_required_details=kt_help_required_details,
            kt_critical_actions_required=kt_critical_actions_required
        )
        db.add(progress_report)
        db.flush()

        video_id = int(toolbox_video_id) if toolbox_video_id and toolbox_video_id.isdigit() else None
        if video_id:
            video = db.query(models.ToolboxVideo).filter(models.ToolboxVideo.id == video_id).first()
            if video:
                video.duty_officer_progress_id = progress_report.id

        if site_image_ids:
            image_id_list = [int(id_str) for id_str in site_image_ids.split(',') if id_str.isdigit()]
            db.query(models.SiteImage).filter(models.SiteImage.id.in_(image_id_list)).update(
                {"duty_officer_progress_id": progress_report.id}, synchronize_session=False
            )

        db.commit()
        return JSONResponse(status_code=200, content={"message": "Progress report submitted successfully!"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An unexpected error occurred: {e}"})


@router.post("/site-officer-reports/", response_class=JSONResponse, tags=["Reports"])
async def create_site_officer_report(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user), # Captures who is submitting
    toolbox_video_id: Optional[str] = Form(None),
    site_image_ids: Optional[str] = Form(None),
    date: date = Form(...),
    site_location: Optional[str] = Form(None),
    # UPDATED: Accept the new user IDs from the form
    
    site_officer_user_id: Optional[str] = Form(None),
    duty_officer_user_id: Optional[str] = Form(None),
    job_card_ids: List[int] = Form(...),
    # ... all other form fields remain the same ...
    tbt_attendance: Optional[str] = Form(None), tbt_topic_discussed: Optional[str] = Form(None),
    tbt_key_points: Optional[str] = Form(None), form_b_completed_check: bool = Form(False),
    dependency_notes: Optional[str] = Form(None), progress_pictures_check: bool = Form(False),
    sm_manpower_availability: Optional[str] = Form(None), sm_subcontractor_coordination: Optional[str] = Form(None),
    sm_coordination_issues: Optional[str] = Form(None), sm_other_notes: Optional[str] = Form(None),
    material_requisition_project_id: Optional[str] = Form(None), commercial_delivery_check: bool = Form(False),
    delivery_comments: Optional[str] = Form(None), qc_steps_explained: bool = Form(False),
    qc_steps_details: Optional[str] = Form(None), qc_drawing_mismatches: Optional[str] = Form(None),
    re_delays_flagged_reason: Optional[str] = Form(None), re_support_needed: Optional[str] = Form(None),
    hs_waste_management: Optional[str] = Form(None), hs_waste_management_comments: Optional[str] = Form(None),
    hs_walkways_clear: Optional[str] = Form(None), hs_material_storage: Optional[str] = Form(None),
    hs_ppe_compliance: bool = Form(False), hs_incidents_near_misses: Optional[str] = Form(None),
    hs_safety_comments: Optional[str] = Form(None), sa_overall_site_health: Optional[str] = Form(None),
    sa_immediate_actions: Optional[str] = Form(None), sa_responsible_person: Optional[str] = Form(None),
    sa_action_deadline: Optional[date] = Form(None), sa_critical_actions: Optional[str] = Form(None),
    sa_approved_drawings_check: Optional[str] = Form(None), sa_drawing_help_details: Optional[str] = Form(None)
):
    try:
        # --- MANUALLY CONVERT STRINGS TO INTEGERS ---
        # This gives us full control and prevents validation errors.
        site_officer_id_int = int(site_officer_user_id) if site_officer_user_id else None
        duty_officer_id_int = int(duty_officer_user_id) if duty_officer_user_id else None
        mr_project_id_int = int(material_requisition_project_id) if material_requisition_project_id else None
        # -------------------------------------------
        report = models.SiteOfficerReport(
            # --- V3 FIELD UPDATES ---
            created_by_id=current_user.id,
            site_officer_user_id=site_officer_id_int,
            duty_officer_user_id=duty_officer_id_int,
            site_officer_id=1, # Placeholder for old required field
            duty_officer_id=1,  # Placeholder for old required field
            # --------------------------
            date=date, site_location=site_location,
            # ... all other fields are the same ...
            tbt_attendance=tbt_attendance, tbt_topic_discussed=tbt_topic_discussed,
            tbt_key_points=tbt_key_points, form_b_completed_check=form_b_completed_check,
            dependency_notes=dependency_notes, progress_pictures_check=progress_pictures_check,
            sm_manpower_availability=sm_manpower_availability,
            sm_subcontractor_coordination=sm_subcontractor_coordination,
            sm_coordination_issues=sm_coordination_issues, sm_other_notes=sm_other_notes,
            material_requisition_project_id=mr_project_id_int,
            commercial_delivery_check=commercial_delivery_check, delivery_comments=delivery_comments,
            qc_steps_explained=qc_steps_explained, qc_steps_details=qc_steps_details,
            qc_drawing_mismatches=qc_drawing_mismatches, re_delays_flagged_reason=re_delays_flagged_reason,
            re_support_needed=re_support_needed, hs_waste_management=hs_waste_management,
            hs_waste_management_comments=hs_waste_management_comments,
            hs_walkways_clear=hs_walkways_clear, hs_material_storage=hs_material_storage,
            hs_ppe_compliance=hs_ppe_compliance, hs_incidents_near_misses=hs_incidents_near_misses,
            hs_safety_comments=hs_safety_comments, sa_overall_site_health=sa_overall_site_health,
            sa_immediate_actions=sa_immediate_actions, sa_responsible_person=sa_responsible_person,
            sa_action_deadline=sa_action_deadline, sa_critical_actions=sa_critical_actions,
            sa_approved_drawings_check=sa_approved_drawings_check, sa_drawing_help_details=sa_drawing_help_details
        )

        # --- NEW LOGIC TO LINK MULTIPLE JOB CARDS ---
        if job_card_ids:
            job_cards_to_link = db.query(models.JobCard).filter(models.JobCard.id.in_(job_card_ids)).all()
            report.job_cards.extend(job_cards_to_link)
        # --------------------------------------------
        db.add(report)
        db.flush()

        video_id = int(toolbox_video_id) if toolbox_video_id and toolbox_video_id.isdigit() else None
        if video_id:
            video = db.query(models.ToolboxVideo).filter(models.ToolboxVideo.id == video_id).first()
            if video:
                video.site_officer_report_id = report.id

        if site_image_ids:
            image_id_list = [int(id_str) for id_str in site_image_ids.split(',') if id_str.isdigit()]
            db.query(models.SiteImage).filter(models.SiteImage.id.in_(image_id_list)).update(
                {"site_officer_report_id": report.id}, synchronize_session=False
            )

        db.commit()
        return JSONResponse(status_code=200, content={"message": "Site Officer daily report submitted successfully!"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An unexpected error occurred: {e}"})