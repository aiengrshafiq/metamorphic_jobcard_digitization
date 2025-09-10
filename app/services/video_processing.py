# app/services/video_processing.py
import os
import uuid
import tempfile
import openai
from azure.storage.blob import BlobServiceClient
from sqlalchemy.orm import Session

from app.models import ToolboxVideo
from app.core.database import SessionLocal

def process_video_and_update_db(
    video_id: int, 
    file_contents: bytes,
    azure_conn_string: str,
    openai_api_key: str
):
    """
    Background task to upload video, transcribe, and summarize.
    """
    db: Session = SessionLocal()
    video_record = db.query(ToolboxVideo).filter(ToolboxVideo.id == video_id).first()
    if not video_record:
        db.close()
        return

    openai.api_key = openai_api_key
    temp_file_path = None
    try:
        video_record.processing_status = 'processing'
        db.commit()

        # 1. Upload to Azure Blob
        blob_service_client = BlobServiceClient.from_connection_string(azure_conn_string)
        container_name = "toolbox-videos"
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()
        
        blob_name = f"{uuid.uuid4()}.webm"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.upload_blob(file_contents, overwrite=True)
        video_record.blob_url = blob_client.url

        # 2. Transcribe with OpenAI
        transcript_text = ""
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
            temp_file.write(file_contents)
            temp_file_path = temp_file.name
        
        with open(temp_file_path, "rb") as audio_file:
            transcription = openai.audio.transcriptions.create(model="whisper-1", file=audio_file)
            transcript_text = transcription.text
        
        video_record.transcript = transcript_text

        # 3. Summarize with OpenAI
        if transcript_text:
            completion = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Summarize this toolbox talk into key bullet points."},
                    {"role": "user", "content": transcript_text}
                ]
            )
            video_record.summary = completion.choices[0].message.content
        
        video_record.processing_status = 'completed'
    except Exception as e:
        video_record.processing_status = 'failed'
        print(f"Error processing video {video_id}: {e}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        db.commit()
        db.close()