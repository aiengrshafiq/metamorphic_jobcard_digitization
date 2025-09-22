# app/api/endpoints/notifications.py
import asyncio
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app import models

router = APIRouter()

async def notification_generator(request: Request, db: Session, current_user: models.User):
    """
    This generator function now yields both the count and the list of
    recent unread notifications.
    """
    last_count = -1
    while True:
        if await request.is_disconnected():
            break

        # Query for unread notifications
        unread_notifications = db.query(models.Notification).filter(
            models.Notification.user_id == current_user.id,
            models.Notification.is_read == False
        ).order_by(models.Notification.created_at.desc()).all()

        unread_count = len(unread_notifications)

        if unread_count != last_count:
            # Prepare the list of recent notifications (e.g., top 5)
            recent_notifications_data = [
                {"id": n.id, "message": n.message, "link": n.link}
                for n in unread_notifications[:5]
            ]
            
            # Send both count and the list of recent items
            yield f"data: {json.dumps({'count': unread_count, 'notifications': recent_notifications_data})}\n\n"
            last_count = unread_count

        await asyncio.sleep(5)

@router.get("/stream", tags=["Notifications"])
async def stream_notifications(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user_from_cookie)
):
    """
    Establishes an SSE connection to stream notification counts.
    """
    if not isinstance(current_user, models.User):
        return {"status": "unauthorized"} # Or handle redirect
    return StreamingResponse(notification_generator(request, db, current_user), media_type="text/event-stream")


@router.post("/mark-as-read", tags=["Notifications"])
def mark_notifications_as_read(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Marks all of a user's notifications as read."""
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"message": "Notifications marked as read"}