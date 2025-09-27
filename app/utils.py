# app/utils.py
from datetime import date
from sqlalchemy.orm import Session
from app.models import JobCard
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
from urllib.parse import urlparse
from app.core.config import settings
import base64
from pathlib import Path

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


# Then, add this new function to the bottom of utils.py
def generate_sas_url(blob_url: str) -> str:
    """
    Generates a SAS token for a given Azure Blob URL to grant temporary access.
    """
    if not blob_url or not settings.AZURE_STORAGE_CONNECTION_STRING:
        return blob_url # Return original URL if config is missing

    try:
        # Parse the connection string to get the account key
        conn_parts = {part.split('=', 1)[0]: part.split('=', 1)[1] for part in settings.AZURE_STORAGE_CONNECTION_STRING.split(';')}
        account_key = conn_parts.get('AccountKey')

        # Parse the blob URL to get its components
        url_parts = urlparse(blob_url)
        account_name = url_parts.netloc.split('.')[0]
        container_name, blob_name = url_parts.path.strip('/').split('/', 1)

        if not all([account_key, account_name, container_name, blob_name]):
            return blob_url # Return original if parsing fails

        # Generate a SAS token that is valid for 1 hour
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        
        return f"{blob_url}?{sas_token}"
    except Exception as e:
        print(f"Error generating SAS URL: {e}")
        return blob_url # Fallback to the original URL on error


# Add this new function to the bottom of the file
def image_to_data_uri(filepath: str) -> str | None:
    """Reads an image file and returns it as a Base64 data URI."""
    try:
        path = Path(filepath)
        if not path.is_file():
            return None
        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            mime_type = f"image/{path.suffix.lstrip('.')}"
            return f"data:{mime_type};base64,{encoded_string}"
    except Exception:
        return None