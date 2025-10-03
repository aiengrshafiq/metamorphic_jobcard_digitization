# app/utils.py
from datetime import date
from sqlalchemy.orm import Session
from app.models import JobCard
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
)
from urllib.parse import urlparse, unquote, quote
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas
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



def generate_sas_url(blob_url: str) -> str:
    """
    Generates a SAS token for a given Azure Blob URL to grant temporary access.
    Fixes: use decoded blob name for signing to avoid signature mismatch.
    """
    if not blob_url or not settings.AZURE_STORAGE_CONNECTION_STRING:
        return blob_url

    try:
        bsc = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)

        # 1) Decode the path so the blob name is the actual stored name (with spaces, parentheses, etc.)
        parts = urlparse(blob_url)
        decoded_path = unquote(parts.path).lstrip('/')   # <-- important!
        container_name, blob_name = decoded_path.split('/', 1)

        # 2) Get an account key from the client credential
        cred = bsc.credential
        account_name = bsc.account_name
        account_key = getattr(cred, "account_key", None) or getattr(cred, "key", None)
        if not account_key:
            # If your connection string is SAS-based, you cannot mint a new SAS with an account key.
            # Switch to user-delegation SAS (AAD) or use an account-key connection string.
            raise RuntimeError("No account key available. Use an account-key connection string or user-delegation SAS.")

        sas = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,  # raw, **not** URL-encoded
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            start=datetime.utcnow() - timedelta(minutes=5),
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

        # 3) Rebuild a browser-safe URL (re-encode the blob name for the URL)
        encoded_blob_name = quote(blob_name, safe="/")
        return f"https://{account_name}.blob.core.windows.net/{container_name}/{encoded_blob_name}?{sas}"

    except Exception as e:
        print(f"CRITICAL: Error generating SAS URL: {e}")
        return blob_url


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