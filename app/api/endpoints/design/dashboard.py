# app/api/endpoints/design/dashboard.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, case
from datetime import datetime, timedelta
from datetime import date

from app.api import deps
from app import models, design_models

router = APIRouter()

@router.get("/", tags=["Design Dashboard"])
def get_dashboard_stats(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Aggregates all necessary data for the Design Manager's dashboard.
    """
    user_roles = {role.name for role in current_user.roles}
    if "Design Manager" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized.")

    # 1. Get At-Risk Tasks (overdue and still open)
    at_risk_tasks = db.query(design_models.DesignTask).options(
        joinedload(design_models.DesignTask.owner),
        joinedload(design_models.DesignTask.phase).joinedload(design_models.DesignPhase.project)
    ).filter(
        design_models.DesignTask.due_date < date.today(),
        design_models.DesignTask.status == 'Open'
    ).order_by(design_models.DesignTask.due_date.asc()).all()

    # 2. Get Team Productivity Stats (for all design team members)
    team_roles = [
        models.UserRole.DESIGN_TEAM_MEMBER,
        models.UserRole.TECH_ENGINEER,
        models.UserRole.DOC_CONTROLLER
    ]
    team_members = db.query(models.User).join(models.User.roles).filter(models.Role.name.in_(team_roles)).all()
    
    productivity_stats = []
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    for member in team_members:
        # Using SQLAlchemy's func for aggregation is highly efficient
        stats = db.query(
            func.count(design_models.DesignTask.id).label("total_tasks"),
            func.sum(case((design_models.DesignScore.lateness_days == 0, 1), else_=0)).label("on_time_tasks"),
            func.avg(design_models.DesignScore.score).label("avg_score")
        ).join(
            design_models.DesignScore
        ).filter(
            design_models.DesignTask.owner_id == member.id,
            design_models.DesignTask.submitted_at >= thirty_days_ago
        ).one()
        
        productivity_stats.append({
            "user_name": member.name,
            "on_time_rate": (stats.on_time_tasks / stats.total_tasks * 100) if stats.total_tasks > 0 else 100,
            "avg_score": stats.avg_score if stats.avg_score else 100,
            "throughput": stats.total_tasks
        })

    return {
        "at_risk_tasks": at_risk_tasks,
        "team_productivity": sorted(productivity_stats, key=lambda x: x['avg_score'], reverse=True)
    }