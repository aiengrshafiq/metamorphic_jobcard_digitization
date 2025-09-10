# app/utils.py
from datetime import date
from sqlalchemy.orm import Session
from app.models import JobCard

def generate_job_card_number(db: Session, site_location: str) -> str:
    """Generates a new, sequential job card number for a given site and date."""
    today = date.today()
    date_str = today.strftime("%Y%m%d")
    site_code = site_location[:3].upper() if site_location else "XXX"

    # Find the last job card for this site code and date
    last_job_card = db.query(JobCard).filter(
        JobCard.job_card_no.like(f"{site_code}-{date_str}-%")
    ).order_by(JobCard.job_card_no.desc()).first()

    if last_job_card:
        last_seq = int(last_job_card.job_card_no.split("-")[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1

    return f"{site_code}-{date_str}-{new_seq:03d}"